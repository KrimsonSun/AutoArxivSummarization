"""Centralized credentials. Mirrors RefinedSummarization/src/config/settings.py
so the same OPENAI_API_KEY / OPENAI_BASE_URL swap pattern works."""
from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    OPENAI_API_KEY: SecretStr = SecretStr("")
    OPENAI_BASE_URL: str | None = None
    DEV_MODE: int = 0

    @property
    def dev_mode(self) -> bool:
        return bool(self.DEV_MODE)


class ConfigurationError(RuntimeError):
    pass


settings = Settings()  # type: ignore[call-arg]
