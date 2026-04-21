"""
NoteForge — AI-Powered Lecture Intelligence System

FastAPI application entry point.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

# ── Logging ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

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


# ── Root ─────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    """API root — basic service info."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


# ── Startup ──────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Log configuration on startup."""
    logger.info("=" * 60)
    logger.info("  %s v%s starting up", settings.app_name, settings.app_version)
    logger.info("  Ollama URL: %s", settings.ollama_base_url)
    logger.info("  Primary model: %s", settings.ollama_primary_model)
    logger.info("  Fallback model: %s", settings.ollama_fallback_model)
    logger.info("  Debug mode: %s", settings.debug)
    logger.info("=" * 60)
