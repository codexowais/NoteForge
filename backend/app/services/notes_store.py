"""
Notes Storage Service

CRUD operations for persisting generated notes in SQLite.
All complex fields (topics, definitions, etc.) are stored as JSON strings.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

from app.db.database import DB_PATH

logger = logging.getLogger(__name__)

_JSON_FIELDS = [
    "topics", "definitions", "formulas", "examples",
    "key_takeaways", "interview_questions", "resources",
]


async def save_note(
    video_id: str,
    youtube_url: str,
    notes_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Persist a generated note to the database.

    Args:
        video_id: YouTube video ID.
        youtube_url: Original YouTube URL.
        notes_data: Formatted notes dict (from GenerateNotesResponse).

    Returns:
        Full saved note dict including id and created_at.
    """
    note_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """
            INSERT INTO notes
                (id, video_id, youtube_url, title, summary,
                 topics, definitions, formulas, examples,
                 key_takeaways, interview_questions, resources,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                video_id,
                youtube_url,
                notes_data.get("title", "Untitled"),
                notes_data.get("summary", ""),
                json.dumps(notes_data.get("topics", [])),
                json.dumps(notes_data.get("definitions", [])),
                json.dumps(notes_data.get("formulas", [])),
                json.dumps(notes_data.get("examples", [])),
                json.dumps(notes_data.get("key_takeaways", [])),
                json.dumps(notes_data.get("interview_questions", [])),
                json.dumps(notes_data.get("resources", [])),
                now,
                now,
            ),
        )
        await db.commit()

    logger.info("Saved note %s for video %s", note_id, video_id)

    # Return the full note
    result = {
        "id": note_id,
        "video_id": video_id,
        "youtube_url": youtube_url,
        "created_at": now,
        **notes_data,
    }
    return result


async def list_notes() -> list[dict[str, Any]]:
    """Return metadata for all saved notes, newest first."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, video_id, youtube_url, title, created_at "
            "FROM notes ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_note(note_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single note by ID with all JSON fields parsed."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        )
        row = await cursor.fetchone()

    if not row:
        return None

    note = dict(row)
    for field in _JSON_FIELDS:
        note[field] = json.loads(note[field])
    return note


async def delete_note(note_id: str) -> bool:
    """Delete a note by ID. Returns True if a row was deleted."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "DELETE FROM notes WHERE id = ?", (note_id,)
        )
        await db.commit()
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info("Deleted note %s", note_id)
    return deleted
