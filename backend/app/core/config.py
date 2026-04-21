"""
NoteForge Application Configuration

Centralized settings management using pydantic-settings.
All values are loaded from environment variables with sensible defaults.
"""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
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
    ollama_primary_model: str = "qwen2.5"
    ollama_fallback_model: str = "mistral"
    ollama_timeout: int = 120
    ollama_max_tokens: int = 4096
    ollama_temperature: float = 0.3

    # ── CORS ─────────────────────────────────────────────────────
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    @property
    def ollama_generate_url(self) -> str:
        """Full URL for the Ollama generate endpoint."""
        return f"{self.ollama_base_url}/api/generate"


# Singleton instance — import this everywhere
settings = Settings()
