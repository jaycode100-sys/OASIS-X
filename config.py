"""Centralised configuration via pydantic-settings (.env / env vars)."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Server ──
    PORT: int = 8080
    HOST: str = "0.0.0.0"

    # ── Authentication ──
    OASIS_SECRET_KEY: str = "change-me-to-a-random-secret-key"
    OASIS_ALGORITHM: str = "HS256"
    OASIS_TOKEN_EXPIRY_HOURS: int = 24

    # ── Database ──
    OASIS_DB_DIR: str = ""
    OASIS_DB_PATH: str = ""

    # ── Ollama ──
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT: int = 180
    SWIFT_LLM_MODEL: str = "swift-fhs"
    CHAT_MODEL: str = "nexus-chat"

    # ── Logging ──
    LOG_LEVEL: str = "info"

    def model_post_init(self, _context) -> None:
        # Resolve DB paths relative to project root
        root = Path(__file__).resolve().parent
        if not self.OASIS_DB_DIR:
            appdata = Path(os.environ.get("APPDATA", str(root / "data"))) / "OASIS-X"
            self.OASIS_DB_DIR = str(appdata)
        if not self.OASIS_DB_PATH:
            self.OASIS_DB_PATH = os.path.join(self.OASIS_DB_DIR, "oasis.db")


settings = Settings()
