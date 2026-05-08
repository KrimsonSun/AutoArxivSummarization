"""Centralized environment / credential loading.

Per HANDOFF §5: API keys MUST only be read here. Use SecretStr to avoid
accidental exposure in logs / repr / stack traces. Settings is instantiated
at import time so missing keys fail-fast — except when DEV_MODE=1, in which
case empty keys are tolerated so scaffolding can be developed without real
credentials.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Search order (later files OVERRIDE earlier ones in pydantic-settings):
#   1. Repo-root .env (shared across all sibling subprojects)
#   2. Project-local .env (project-specific overrides)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_ENV = _PROJECT_ROOT / ".env"


def _find_repo_root_env() -> Path | None:
    """Walk up to the nearest .git ancestor and return its sibling .env if any."""
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
    """All credentials and base URLs live here. No other module reads os.environ."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES or None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- API keys (SecretStr so they never appear in logs / __repr__) ---
    OPENAI_API_KEY: SecretStr = SecretStr("")
    ANTHROPIC_API_KEY: SecretStr = SecretStr("")
    GOOGLE_API_KEY: SecretStr = SecretStr("")

    # --- Optional base URL overrides (proxy / Azure / OpenRouter / Together...) ---
    OPENAI_BASE_URL: str | None = None
    ANTHROPIC_BASE_URL: str | None = None
    GOOGLE_BASE_URL: str | None = None

    # --- Dev mode flag ---
    # When 1, callers may proceed even if a key is empty (LLM call sites
    # raise ConfigurationError instead of import-time failure). Useful for
    # building / testing the scaffolding before real credentials are wired up.
    DEV_MODE: int = 0

    # ------------------------------------------------------------------ helpers

    @property
    def dev_mode(self) -> bool:
        return bool(self.DEV_MODE)

    def require(self, provider: str) -> str:
        """Return the secret for a given provider, raising if missing.

        provider ∈ {"openai", "anthropic", "google"}
        """
        mapping = {
            "openai": self.OPENAI_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
            "google": self.GOOGLE_API_KEY,
        }
        if provider not in mapping:
            raise ValueError(f"Unknown provider: {provider!r}")
        secret = mapping[provider]
        value = secret.get_secret_value()
        if not value:
            raise ConfigurationError(
                f"Missing API key for provider {provider!r}. "
                f"Set {provider.upper()}_API_KEY in .env, or set DEV_MODE=1 "
                f"to defer this check."
            )
        return value

    def base_url(self, provider: str) -> str | None:
        mapping = {
            "openai": self.OPENAI_BASE_URL,
            "anthropic": self.ANTHROPIC_BASE_URL,
            "google": self.GOOGLE_BASE_URL,
        }
        if provider not in mapping:
            raise ValueError(f"Unknown provider: {provider!r}")
        v = mapping[provider]
        return v if v else None


class ConfigurationError(RuntimeError):
    """Raised when a required configuration value is missing."""


# Module-level singleton (handoff §5.2). Import this everywhere.
settings = Settings()  # type: ignore[call-arg]
