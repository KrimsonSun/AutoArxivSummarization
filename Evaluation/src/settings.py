"""Centralized credentials. Mirrors RefinedSummarization/src/config/settings.py
so the same OPENAI_API_KEY / OPENAI_BASE_URL swap pattern works."""
from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ENV = _PROJECT_ROOT / ".env"


def _find_repo_root_env() -> Path | None:
    """Walk up to the nearest .git ancestor and return its sibling .env if any.

    Lets all sibling subprojects (Evaluation, RefinedSummarization,
    Refine-OneVision-Summary) share a single repo-root .env. Project-local
    .env still takes precedence (loaded later → overrides)."""
    cur = _PROJECT_ROOT
    for _ in range(8):
        if (cur / ".git").exists():
            cand = cur / ".env"
            return cand if cand.exists() else None
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


_REPO_ENV = _find_repo_root_env()
_ENV_FILES: tuple[str, ...] = tuple(
    str(p) for p in (_REPO_ENV, _PROJECT_ENV) if p is not None and p.exists()
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES or None,
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
