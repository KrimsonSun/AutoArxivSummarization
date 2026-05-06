"""Google Gemini client (handoff §5.3, §4.1).

Uses the new ``google-genai`` SDK (not the legacy ``google-generativeai``).
Gemini supports JSON-mode + response schema natively, which gives us schema-
validated JSON without prompt-engineering tricks.
"""
from __future__ import annotations

import json
from typing import Type, TypeVar

from google import genai
from google.genai import types as gtypes
from pydantic import BaseModel

from src.config.settings import settings
from src.llm_clients.base import LLMClient, LLMError

T = TypeVar("T", bound=BaseModel)

_CONTEXT_WINDOWS: dict[str, int] = {
    "gemini-1.5-flash": 1_000_000,
    "gemini-1.5-pro": 2_000_000,
    "gemini-2.0-flash": 1_000_000,
    "gemini-2.5-flash": 1_000_000,
    "gemini-2.5-pro": 1_000_000,
    "gemini-3-flash-preview": 1_000_000,
    "gemini-3.1-pro-preview": 1_000_000,
}


class GoogleClient(LLMClient):
    def __init__(self, model: str, temperature: float = 0.7) -> None:
        super().__init__()
        api_key = (
            settings.GOOGLE_API_KEY.get_secret_value()
            or ("DEV_PLACEHOLDER" if settings.dev_mode else "")
        )
        if not api_key:
            from src.config.settings import ConfigurationError
            raise ConfigurationError("GOOGLE_API_KEY is empty and DEV_MODE is off.")

        client_kwargs = {"api_key": api_key}
        # Note: google-genai handles base_url through HTTP options if needed.
        # Most users won't need this; OpenAI-compatible aggregators expose
        # Gemini under their own provider path.
        self._client = genai.Client(**client_kwargs)
        self._model = model
        self._temperature = temperature

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        for prefix, n in _CONTEXT_WINDOWS.items():
            if self._model.startswith(prefix):
                return n
        return 1_000_000

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[T],
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> T:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=gtypes.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self._temperature if temperature is None else temperature,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )
        except Exception as e:
            raise LLMError(f"Google call failed: {e}") from e

        # Token accounting
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            self.usage.add(
                prompt=getattr(usage, "prompt_token_count", 0) or 0,
                completion=getattr(usage, "candidates_token_count", 0) or 0,
            )

        # Prefer the SDK-parsed object when available; otherwise parse text.
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, response_schema):
            return parsed
        text = response.text or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Google returned non-JSON content (model={self._model}): {text[:300]}"
            ) from e
        try:
            return response_schema.model_validate(data)
        except Exception as e:
            raise LLMError(
                f"Schema validation failed for {response_schema.__name__}: {e}\n"
                f"Raw content: {text[:500]}"
            ) from e

    async def healthcheck(self) -> bool:
        try:
            r = await self._client.aio.models.generate_content(
                model=self._model,
                contents="Reply with the single word: ok",
                config=gtypes.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=10,
                ),
            )
            return "ok" in (r.text or "").lower()
        except Exception as e:
            raise LLMError(f"Google healthcheck failed: {e}") from e
