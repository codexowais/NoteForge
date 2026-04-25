"""
NoteForge Application Configuration

Centralized settings management using pydantic-settings.
All values are loaded from environment variables with sensible defaults.
"""

from pathlib import Path
from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"


class Settings(BaseSettings):
    """Application-wide configuration loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    app_name: str = "NoteForge"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Ollama ───────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_primary_model: str = DEFAULT_OLLAMA_MODEL
    ollama_fallback_model: str = DEFAULT_OLLAMA_MODEL
    ollama_timeout: int = 120
    ollama_max_tokens: int = 4096
    ollama_temperature: float = 0.3

    # ── CORS ─────────────────────────────────────────────────────
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> bool:
        """Accept deployment-style DEBUG values from process environments."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "production"}:
                return False
        return value

    @field_validator("ollama_base_url")
    @classmethod
    def normalize_ollama_base_url(cls, value: str) -> str:
        """Store the Ollama base URL without a trailing slash."""
        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("OLLAMA_BASE_URL cannot be empty")
        return normalized

    @field_validator("ollama_primary_model", "ollama_fallback_model")
    @classmethod
    def validate_ollama_model(cls, value: str) -> str:
        """Require explicit, non-empty Ollama model names."""
        model = value.strip()
        if not model:
            raise ValueError("Ollama model name cannot be empty")
        return model

    @property
    def ollama_generate_url(self) -> str:
        """Full URL for the Ollama generate endpoint."""
        return f"{self.ollama_base_url}/api/generate"


# Singleton instance — import this everywhere
settings = Settings()
