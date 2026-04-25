"""
Ollama Summarizer Service

Handles LLM inference via Ollama's local HTTP API.
Supports primary/fallback model switching, timeout handling,
and JSON response extraction.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Load prompt templates once at module level
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "notes_prompt.txt"
_PROMPT_TEMPLATE: str = _PROMPT_PATH.read_text(encoding="utf-8")

_QUIZ_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "quiz_prompt.txt"
_QUIZ_PROMPT_TEMPLATE: str = _QUIZ_PROMPT_PATH.read_text(encoding="utf-8")


class OllamaServiceError(Exception):
    """Base exception for Ollama inference failures."""

    pass


class OllamaConnectionError(OllamaServiceError):
    """Raised when Ollama server is unreachable."""

    pass


class OllamaInferenceError(OllamaServiceError):
    """Raised when model inference fails or returns invalid output."""

    pass


async def check_ollama_health() -> str:
    """
    Ping the Ollama server to verify availability.

    Returns:
        "connected" if reachable, "disconnected" otherwise.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(settings.ollama_base_url)
            return "connected" if response.status_code == 200 else "disconnected"
    except Exception:
        return "disconnected"


def _build_prompt(transcript: str) -> str:
    """Inject transcript into the prompt template."""
    return _PROMPT_TEMPLATE.replace("{transcript}", transcript)


def _extract_json(raw_text: str) -> dict[str, Any]:
    """
    Extract and parse JSON from LLM response text.

    Handles cases where the model wraps JSON in markdown code fences
    or includes preamble text.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        first_newline = text.index("\n")
        text = text[first_newline + 1 :]
        # Remove closing fence
        if text.endswith("```"):
            text = text[:-3].strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: find first { and last } and parse that slice
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise OllamaInferenceError(
        "LLM response is not valid JSON. "
        f"First 500 chars: {raw_text[:500]}"
    )


async def _call_ollama(
    prompt: str,
    model: str,
    timeout: Optional[float] = None,
) -> str:
    """
    Send a prompt to Ollama and return the raw response text.

    Args:
        prompt: The full prompt string.
        model: Ollama model name.
        timeout: Request timeout in seconds.

    Returns:
        Raw text response from the model.
    """
    if timeout is None:
        timeout = float(settings.ollama_timeout)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    logger.info("Sending inference request to Ollama [model=%s]", model)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                settings.ollama_generate_url,
                json=payload,
            )
            response.raise_for_status()
    except httpx.ConnectError as e:
        raise OllamaConnectionError(
            f"Cannot connect to Ollama at {settings.ollama_base_url}. "
            "Ensure Ollama is running: `ollama serve`"
        ) from e
    except httpx.TimeoutException as e:
        raise OllamaInferenceError(
            f"Ollama request timed out after {timeout}s for model {model}. "
            "Try a shorter transcript or increase OLLAMA_TIMEOUT."
        ) from e
    except httpx.HTTPStatusError as e:
        raise OllamaInferenceError(
            f"Ollama returned HTTP {e.response.status_code} for model {model}: "
            f"{e.response.text[:300]}"
        ) from e
    except httpx.RequestError as e:
        raise OllamaInferenceError(
            f"Ollama request failed for model {model}: {e}"
        ) from e

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        raise OllamaInferenceError(
            f"Ollama returned invalid JSON for model {model}: "
            f"{response.text[:300]}"
        ) from e

    raw_response = data.get("response", "")

    if not raw_response.strip():
        raise OllamaInferenceError(
            f"Ollama returned an empty response for model {model}."
        )

    logger.info(
        "Received response from Ollama [model=%s, chars=%d]",
        model,
        len(raw_response),
    )

    return raw_response


async def generate_notes(transcript: str) -> dict[str, Any]:
    """
    Generate structured notes from a transcript using Ollama.

    Tries the primary model first, falls back to the secondary model
    if the primary fails.

    Args:
        transcript: Full lecture transcript text.

    Returns:
        Parsed JSON dict of structured notes.

    Raises:
        OllamaConnectionError: If Ollama server is unreachable.
        OllamaInferenceError: If both models fail to produce valid output.
    """
    prompt = _build_prompt(transcript)

    # ── Try primary model ────────────────────────────────────────
    try:
        raw = await _call_ollama(prompt, settings.ollama_primary_model)
        return _extract_json(raw)
    except OllamaConnectionError:
        raise  # Don't fallback if server is down entirely
    except OllamaServiceError as e:
        logger.warning(
            "Primary model [%s] failed: %s — trying fallback [%s]",
            settings.ollama_primary_model,
            e,
            settings.ollama_fallback_model,
        )

    # ── Try fallback model ───────────────────────────────────────
    try:
        raw = await _call_ollama(prompt, settings.ollama_fallback_model)
        return _extract_json(raw)
    except OllamaServiceError as e:
        raise OllamaInferenceError(
            f"Both models failed. Primary [{settings.ollama_primary_model}] "
            f"and fallback [{settings.ollama_fallback_model}] "
            f"could not generate valid notes. Last error: {e}"
        )


async def generate_quiz(notes_content: str) -> dict[str, Any]:
    """
    Generate quiz questions from structured note content using Ollama.

    Args:
        notes_content: Stringified notes content for quiz generation.

    Returns:
        Parsed JSON dict with quiz questions.

    Raises:
        OllamaConnectionError: If Ollama server is unreachable.
        OllamaInferenceError: If both models fail.
    """
    prompt = _QUIZ_PROMPT_TEMPLATE.replace("{notes_content}", notes_content)

    # ── Try primary model ────────────────────────────────────────
    try:
        raw = await _call_ollama(prompt, settings.ollama_primary_model)
        return _extract_json(raw)
    except OllamaConnectionError:
        raise
    except OllamaServiceError as e:
        logger.warning(
            "Primary model [%s] failed for quiz: %s — trying fallback [%s]",
            settings.ollama_primary_model,
            e,
            settings.ollama_fallback_model,
        )

    # ── Try fallback model ───────────────────────────────────────
    try:
        raw = await _call_ollama(prompt, settings.ollama_fallback_model)
        return _extract_json(raw)
    except OllamaServiceError as e:
        raise OllamaInferenceError(
            f"Both models failed to generate quiz. Last error: {e}"
        )
