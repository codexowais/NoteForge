"""
NoteForge API Routes

All HTTP endpoints for the notes generation system.
"""

import logging
import time

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.models.note import (
    ErrorResponse,
    GenerateNotesRequest,
    HealthResponse,
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
)
from app.services.youtube import (
    InvalidURLError,
    TranscriptUnavailableError,
    get_transcript_from_url,
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
        video_id, transcript = get_transcript_from_url(request.youtube_url)
        logger.info(
            "Transcript extracted [video=%s, length=%d chars]",
            video_id,
            len(transcript),
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
        raw_notes = await generate_notes(transcript)
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
        logger.error("Formatting failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM produced invalid output: {e}",
        )

    # ── Step 4: Save to database ─────────────────────────────────
    saved = await db_save_note(
        video_id=video_id,
        youtube_url=request.youtube_url,
        notes_data=formatted_notes.model_dump(),
    )

    elapsed = time.time() - start_time
    logger.info(
        "Notes generated and saved [video=%s, id=%s, time=%.2fs]",
        video_id,
        saved["id"],
        elapsed,
    )

    return saved


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
