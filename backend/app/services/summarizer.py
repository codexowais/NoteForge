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


def _unwrap_nested(data: dict[str, Any]) -> dict[str, Any]:
    """
    Unwrap common single-key wrapper dicts that LLMs sometimes produce.

    Handles cases like:
      {"notes": {"title": ...}}
      {"response": {"title": ...}}
      {"result": {"title": ...}}
      {"data": {"title": ...}}
      {"lecture_notes": {"title": ...}}
      {"structured_notes": {"title": ...}}
    """
    # Already a valid notes object
    if "title" in data or "summary" in data:
        return data

    # Check common wrapper keys
    wrapper_keys = (
        "notes", "note", "structured_notes", "lecture_notes",
        "response", "result", "data", "output", "content",
    )
    for key in wrapper_keys:
        nested = data.get(key)
        if isinstance(nested, dict):
            logger.debug("Unwrapped LLM output from wrapper key '%s'", key)
            return nested

    # Single-key dict — unwrap whatever it is
    if len(data) == 1:
        only_value = next(iter(data.values()))
        if isinstance(only_value, dict):
            logger.debug("Unwrapped single-key LLM wrapper")
            return only_value

    return data


def _extract_json(raw_text: str) -> dict[str, Any]:
    """
    Extract and parse JSON from LLM response text.

    Handles:
    - Markdown code fences (```json ... ```)
    - Preamble text before JSON
    - Nested wrapper objects
    """
    text = raw_text.strip()

    # Log raw output for debugging
    logger.debug("Raw LLM response (first 800 chars): %s", text[:800])

    # Strip markdown code fences if present
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()

    # Try direct parse first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return _unwrap_nested(parsed)
    except json.JSONDecodeError:
        pass

    # Fallback: find first { and last } and parse that slice
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, dict):
                return _unwrap_nested(parsed)
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
        # Structured schema forces qwen2.5:7b to fill real content into
        # every field instead of returning a generic skeleton.
        "format": {
            "type": "object",
            "properties": {
                "title":   {"type": "string"},
                "summary": {"type": "string"},
                "topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title":   {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["title", "content"]
                    }
                },
                "definitions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "term":       {"type": "string"},
                            "definition": {"type": "string"}
                        },
                        "required": ["term", "definition"]
                    }
                },
                "formulas":      {"type": "array", "items": {"type": "string"}},
                "examples":      {"type": "array", "items": {"type": "string"}},
                "key_takeaways": {"type": "array", "items": {"type": "string"}},
                "interview_questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question":         {"type": "string"},
                            "suggested_answer": {"type": "string"}
                        },
                        "required": ["question", "suggested_answer"]
                    }
                },
                "resources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "link":  {"type": "string"}
                        },
                        "required": ["title"]
                    }
                }
            },
            "required": [
                "title", "summary", "topics", "definitions",
                "formulas", "examples", "key_takeaways",
                "interview_questions", "resources"
            ]
        },
        "options": {
            "temperature": settings.ollama_temperature,
            "num_predict": max(int(settings.ollama_max_tokens), 4096),
        },
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
        parsed = _extract_json(raw)
        logger.debug("Parsed notes JSON keys=%s", sorted(parsed.keys()))
        return parsed
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
        parsed = _extract_json(raw)
        logger.debug("Parsed fallback notes JSON keys=%s", sorted(parsed.keys()))
        return parsed
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