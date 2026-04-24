"""
NoteForge — AI-Powered Lecture Intelligence System

FastAPI application entry point.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.db.database import init_db

# ── Logging ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

# ── Application ──────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "NoteForge transforms YouTube lectures into structured, "
        "revision-ready study notes using local LLM inference via Ollama."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────

app.include_router(router, prefix="/api/v1", tags=["Notes"])


# ── Frontend Serving ─────────────────────────────────────────────

# Serve static assets (CSS, JS, images)
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


@app.get("/", tags=["Root"])
async def serve_frontend():
    """Serve the NoteForge web UI."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


# ── Startup ──────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize database and log configuration on startup."""
    await init_db()
    logger.info("=" * 60)
    logger.info("  %s v%s starting up", settings.app_name, settings.app_version)
    logger.info("  Ollama URL: %s", settings.ollama_base_url)
    logger.info("  Primary model: %s", settings.ollama_primary_model)
    logger.info("  Fallback model: %s", settings.ollama_fallback_model)
    logger.info("  Frontend: %s", FRONTEND_DIR)
    logger.info("  Debug mode: %s", settings.debug)
    logger.info("=" * 60)
