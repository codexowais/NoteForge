"""
NoteForge API Routes

All HTTP endpoints for the notes generation system.
"""

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.models.note import (
    BatchGenerateRequest,
    BatchGenerateResponse,
    BatchItemResult,
    ErrorResponse,
    GenerateNotesRequest,
    HealthResponse,
    QuizResponse,
    QuizQuestion,
    SavedNoteMetadata,
    SavedNoteResponse,
)
from app.services.formatter import FormatterError, format_notes
from app.services.notes_store import (
    delete_note as db_delete_note,
    get_note as db_get_note,
    list_notes as db_list_notes,
    save_note as db_save_note,
)
from app.services.summarizer import (
    OllamaConnectionError,
    OllamaInferenceError,
    check_ollama_health,
    generate_notes,
    generate_quiz,
)
from app.services.youtube import (
    InvalidURLError,
    TranscriptUnavailableError,
    get_transcript_from_url,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _note_response_debug_payload(note: dict[str, Any]) -> dict[str, Any]:
    """Small log-only snapshot that confirms frontend-facing fields exist."""
    return {
        "id": note.get("id"),
        "video_id": note.get("video_id"),
        "title_present": bool(note.get("title")),
        "summary_chars": len(note.get("summary") or ""),
        "topics": len(note.get("topics") or []),
        "formulas": len(note.get("formulas") or []),
        "examples": len(note.get("examples") or []),
        "resources": len(note.get("resources") or []),
    }


# ── Health Check ─────────────────────────────────────────────────


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Verify API and Ollama connectivity.",
)
async def health_check():
    """Return system health including Ollama connection status."""
    ollama_status = await check_ollama_health()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        ollama_status=ollama_status,
    )


# ── Generate Notes ───────────────────────────────────────────────


@router.post(
    "/generate-notes",
    response_model=SavedNoteResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
        502: {"model": ErrorResponse, "description": "Ollama service error"},
        504: {"model": ErrorResponse, "description": "Ollama timeout"},
    },
    summary="Generate structured lecture notes",
    description=(
        "Accepts a YouTube URL, extracts the transcript, "
        "generates comprehensive structured notes using a local LLM, "
        "and persists the result."
    ),
)
async def generate_notes_endpoint(request: GenerateNotesRequest):
    """
    Full pipeline: YouTube URL → Transcript → LLM → Structured Notes → Save.
    """
    start_time = time.time()

    # ── Step 1: Extract transcript ───────────────────────────────
    try:
        video_id, transcript = get_transcript_from_url(
            request.youtube_url,
            language=request.language,
        )
        logger.info(
            "Transcript extracted [video=%s, length=%d chars, lang=%s]",
            video_id,
            len(transcript),
            request.language or "auto",
        )
    except InvalidURLError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except TranscriptUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # ── Step 2: Generate notes via Ollama ────────────────────────
    try:
        logger.info(
            "Starting notes generation [video=%s, transcript_chars=%d]",
            video_id,
            len(transcript),
        )
        raw_notes = await generate_notes(transcript)
        logger.debug(
            "Raw notes parsed from LLM [video=%s, keys=%s]",
            video_id,
            sorted(raw_notes.keys()),
        )
    except OllamaConnectionError as e:
        logger.error("Ollama connection failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )
    except OllamaInferenceError as e:
        logger.error("Ollama inference failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )

    # ── Step 3: Format and validate response ─────────────────────
    try:
        formatted_notes = format_notes(raw_notes)
    except FormatterError as e:
        logger.error(
            "Formatting failed [video=%s, raw_keys=%s]: %s",
            video_id,
            sorted(raw_notes.keys()) if isinstance(raw_notes, dict) else "n/a",
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM produced invalid output: {e}",
        )

    # ── Step 4: Save to database ─────────────────────────────────
    try:
        saved = await db_save_note(
            video_id=video_id,
            youtube_url=request.youtube_url,
            notes_data=formatted_notes.model_dump(),
        )
    except Exception as e:
        logger.exception("Failed to save generated notes [video=%s]", video_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save generated notes: {e}",
        )

    elapsed = time.time() - start_time
    logger.info(
        "Notes generated and saved [video=%s, id=%s, time=%.2fs, response=%s]",
        video_id,
        saved["id"],
        elapsed,
        json.dumps(_note_response_debug_payload(saved)),
    )

    return saved


# ── Batch Generate ───────────────────────────────────────────────


@router.post(
    "/batch-generate",
    response_model=BatchGenerateResponse,
    summary="Generate notes for multiple YouTube URLs",
    description=(
        "Processes multiple YouTube URLs sequentially. "
        "Each URL goes through the full pipeline independently. "
        "Partial failures don't block other URLs."
    ),
)
async def batch_generate_endpoint(request: BatchGenerateRequest):
    """Process multiple YouTube URLs and return results for each."""
    results = []
    succeeded = 0
    failed = 0

    for url in request.youtube_urls:
        try:
            # Extract transcript
            video_id, transcript = get_transcript_from_url(
                url, language=request.language
            )

            # Generate notes
            logger.info(
                "Batch: starting notes generation [video=%s, transcript_chars=%d]",
                video_id,
                len(transcript),
            )
            raw_notes = await generate_notes(transcript)
            logger.debug(
                "Batch: raw notes parsed [video=%s, keys=%s]",
                video_id,
                sorted(raw_notes.keys()),
            )
            formatted_notes = format_notes(raw_notes)

            # Save
            saved = await db_save_note(
                video_id=video_id,
                youtube_url=url,
                notes_data=formatted_notes.model_dump(),
            )

            results.append(
                BatchItemResult(
                    youtube_url=url,
                    status="success",
                    note=SavedNoteResponse(**saved),
                )
            )
            succeeded += 1
            logger.info(
                "Batch: generated notes for %s [response=%s]",
                url,
                json.dumps(_note_response_debug_payload(saved)),
            )

        except Exception as e:
            results.append(
                BatchItemResult(
                    youtube_url=url,
                    status="error",
                    error=str(e),
                )
            )
            failed += 1
            logger.warning("Batch: failed for %s — %s", url, e)

    return BatchGenerateResponse(
        total=len(request.youtube_urls),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


# ── List Notes ───────────────────────────────────────────────────


@router.get(
    "/notes",
    response_model=list[SavedNoteMetadata],
    summary="List all saved notes",
    description="Returns metadata for all saved notes, newest first.",
)
async def list_notes_endpoint():
    """Return metadata list of all saved notes."""
    return await db_list_notes()


# ── Get Note ─────────────────────────────────────────────────────


@router.get(
    "/notes/{note_id}",
    response_model=SavedNoteResponse,
    summary="Get a note by ID",
    description="Returns the full note content by its ID.",
)
async def get_note_endpoint(note_id: str):
    """Retrieve a single note with all content."""
    note = await db_get_note(note_id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note {note_id} not found.",
        )
    return note


# ── Delete Note ──────────────────────────────────────────────────


@router.delete(
    "/notes/{note_id}",
    summary="Delete a note",
    description="Permanently delete a note by ID.",
)
async def delete_note_endpoint(note_id: str):
    """Delete a note from the database."""
    deleted = await db_delete_note(note_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note {note_id} not found.",
        )
    return {"status": "deleted", "id": note_id}


# ── Quiz Generation ─────────────────────────────────────────────


@router.post(
    "/notes/{note_id}/quiz",
    response_model=QuizResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Note not found"},
        502: {"model": ErrorResponse, "description": "Ollama service error"},
    },
    summary="Generate a quiz from a saved note",
    description="Uses the LLM to create MCQ quiz questions from the note content.",
)
async def generate_quiz_endpoint(note_id: str):
    """Generate interactive quiz questions from a saved note."""

    # Fetch the note
    note = await db_get_note(note_id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note {note_id} not found.",
        )

    # Build a textual summary of the note for the quiz prompt
    notes_text = f"Title: {note['title']}\n\nSummary: {note['summary']}\n\n"

    if note.get("topics"):
        notes_text += "Topics:\n"
        for t in note["topics"]:
            if isinstance(t, dict):
                notes_text += f"- {t.get('title', '')}: {t.get('content', '')}\n"

    if note.get("definitions"):
        notes_text += "\nDefinitions:\n"
        for d in note["definitions"]:
            if isinstance(d, dict):
                notes_text += f"- {d.get('term', '')}: {d.get('definition', '')}\n"

    if note.get("key_takeaways"):
        notes_text += "\nKey Takeaways:\n"
        for kt in note["key_takeaways"]:
            notes_text += f"- {kt}\n"

    if note.get("formulas"):
        notes_text += "\nFormulas:\n"
        for f in note["formulas"]:
            notes_text += f"- {f}\n"

    if note.get("examples"):
        notes_text += "\nExamples:\n"
        for ex in note["examples"]:
            notes_text += f"- {ex}\n"

    # Generate quiz via LLM
    try:
        raw_quiz = await generate_quiz(notes_text)
    except OllamaConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )
    except OllamaInferenceError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )

    # Parse questions
    raw_questions = raw_quiz.get("questions", [])
    questions = []
    for q in raw_questions:
        if isinstance(q, dict):
            try:
                questions.append(
                    QuizQuestion(
                        question=q.get("question", ""),
                        options=q.get("options", ["A", "B", "C", "D"]),
                        correct_index=q.get("correct_index", 0),
                        explanation=q.get("explanation", ""),
                    )
                )
            except Exception:
                continue  # Skip malformed questions

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM failed to generate valid quiz questions.",
        )

    return QuizResponse(
        note_id=note_id,
        note_title=note["title"],
        questions=questions,
    )
