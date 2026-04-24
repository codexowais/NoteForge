"""
NoteForge Database Module

SQLite database management using aiosqlite.
Handles connection lifecycle and schema initialization.
"""

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

# Database file lives alongside the backend directory
DB_PATH = Path(__file__).resolve().parent.parent.parent / "noteforge.db"


async def init_db() -> None:
    """Create tables if they don't exist."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id              TEXT PRIMARY KEY,
                video_id        TEXT NOT NULL,
                youtube_url     TEXT NOT NULL,
                title           TEXT NOT NULL,
                summary         TEXT NOT NULL,
                topics          TEXT NOT NULL DEFAULT '[]',
                definitions     TEXT NOT NULL DEFAULT '[]',
                formulas        TEXT NOT NULL DEFAULT '[]',
                examples        TEXT NOT NULL DEFAULT '[]',
                key_takeaways   TEXT NOT NULL DEFAULT '[]',
                interview_questions TEXT NOT NULL DEFAULT '[]',
                resources       TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at DESC)"
        )
        await db.commit()
        logger.info("Database initialized at %s", DB_PATH)


async def get_connection() -> aiosqlite.Connection:
    """Open a new database connection with Row factory enabled."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    return db
