"""OpenAI-compatible LLM client.

Same pattern as RefinedSummarization — OPENAI_BASE_URL override means
OpenRouter / Together / DeepInfra / Groq / vLLM all just work. Only the
OpenAI provider is wired here because the evaluator only needs one client
type (we don't need 3 heterogeneous models for evaluation).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Type, TypeVar

from openai import APIError, AsyncOpenAI
from pydantic import BaseModel

from src.settings import ConfigurationError, settings

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Wrapper for any provider error so the pipeline catches one type."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    def add(self, p: int, c: int) -> None:
        self.prompt_tokens += p
        self.completion_tokens += c
        self.calls += 1


class LLMClient:
    """Lightweight async wrapper around the OpenAI SDK."""

    def __init__(self, model: str, temperature: float = 0.0, max_tokens: int = 1024):
        api_key = (
            settings.OPENAI_API_KEY.get_secret_value()
            or ("DEV_PLACEHOLDER" if settings.dev_mode else "")
        )
        if not api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY is empty and DEV_MODE is off. "
                "Set your OpenRouter key in .env."
            )
        kwargs = {"api_key": api_key, "timeout": 120.0}
        if settings.OPENAI_BASE_URL:
            kwargs["base_url"] = settings.OPENAI_BASE_URL
        self._client = AsyncOpenAI(**kwargs)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self.usage = Usage()

    @property
    def model_id(self) -> str:
        return self._model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self._temperature if temperature is None else temperature,
                max_tokens=self._max_tokens if max_tokens is None else max_tokens,
                response_format={"type": "json_object"},
            )
        except APIError as e:
            raise LLMError(f"OpenAI APIError: {e}") from e
        except Exception as e:
            raise LLMError(f"OpenAI call failed: {e}") from e

        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.usage.add(
                getattr(usage, "prompt_tokens", 0) or 0,
                getattr(usage, "completion_tokens", 0) or 0,
            )

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Non-JSON content (model={self._model}): {content[:300]}"
            ) from e

        try:
            return response_schema.model_validate(data)
        except Exception as e:
            raise LLMError(
                f"Schema validation failed for {response_schema.__name__}: {e}\n"
                f"Raw: {content[:500]}"
            ) from e

    async def healthcheck(self) -> bool:
        try:
            r = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "Reply with: ok"}],
                max_tokens=5,
                temperature=0.0,
            )
            return "ok" in (r.choices[0].message.content or "").lower()
        except Exception as e:
            raise LLMError(f"healthcheck failed: {e}") from e
