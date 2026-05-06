"""OpenAI-compatible client.

Uses the official ``openai`` SDK with structured-output ``response_format``.
Setting ``OPENAI_BASE_URL`` redirects all calls to a different OpenAI-API-
compatible endpoint, which means this same client transparently speaks to:

-   OpenAI proper (default)
-   OpenRouter (``https://openrouter.ai/api/v1``)
-   Together AI (``https://api.together.xyz/v1``)
-   DeepInfra (``https://api.deepinfra.com/v1/openai``)
-   Groq (``https://api.groq.com/openai/v1``)
-   Fireworks (``https://api.fireworks.ai/inference/v1``)

That way the open-source model swap is purely a config change (handoff §13.4
and the .env.example notes).
"""
from __future__ import annotations

import json
from typing import Type, TypeVar

from openai import APIError, AsyncOpenAI
from pydantic import BaseModel

from src.config.settings import settings
from src.llm_clients.base import LLMClient, LLMError

T = TypeVar("T", bound=BaseModel)

# Approximate context windows for popular models. Used only for capacity
# planning; the SDK itself enforces the real limits.
_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4o-2024-11-20": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4.1": 1_000_000,
    "o1": 200_000,
    "o3": 200_000,
}


class OpenAIClient(LLMClient):
    def __init__(self, model: str, temperature: float = 0.7) -> None:
        super().__init__()
        # Allow construction in DEV_MODE without a key — calls will fail later.
        api_key = (
            settings.OPENAI_API_KEY.get_secret_value()
            or ("DEV_PLACEHOLDER" if settings.dev_mode else "")
        )
        if not api_key:
            from src.config.settings import ConfigurationError
            raise ConfigurationError("OPENAI_API_KEY is empty and DEV_MODE is off.")

        kwargs = {"api_key": api_key, "timeout": 120.0}
        base_url = settings.OPENAI_BASE_URL
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
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
        return 128_000

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[T],
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> T:
        try:
            # Prefer SDK-native structured outputs when the schema is simple.
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self._temperature if temperature is None else temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except APIError as e:
            raise LLMError(f"OpenAI APIError: {e}") from e
        except Exception as e:  # network, etc.
            raise LLMError(f"OpenAI call failed: {e}") from e

        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.usage.add(
                prompt=getattr(usage, "prompt_tokens", 0) or 0,
                completion=getattr(usage, "completion_tokens", 0) or 0,
            )

        # Open-source models (Llama / Qwen / DeepSeek via OpenRouter) often
        # wrap JSON in markdown code fences (```json ... ``` or ``` ... ```)
        # despite response_format=json_object. Strip them before parsing.
        content = _strip_code_fence(content)
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError(
                f"OpenAI returned non-JSON content (model={self._model}): {content[:300]}"
            ) from e

        try:
            return response_schema.model_validate(data)
        except Exception as e:
            raise LLMError(
                f"Schema validation failed for {response_schema.__name__}: {e}\n"
                f"Raw content: {content[:500]}"
            ) from e

    async def healthcheck(self) -> bool:
        try:
            r = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "Reply with the single word: ok"}],
                max_tokens=5,
                temperature=0.0,
            )
            text = (r.choices[0].message.content or "").strip().lower()
            return "ok" in text
        except Exception as e:
            raise LLMError(f"OpenAI healthcheck failed: {e}") from e


def _strip_code_fence(content: str) -> str:
    """Robustly extract the JSON payload from an LLM response.

    Open-source models on OpenRouter occasionally emit:
    1. Plain JSON                       → return unchanged
    2. ```json\n{...}\n```              → strip the fence
    3. "Here is the JSON: ```{...}```"  → strip preamble + fence
    4. "Sure! {...}"                    → strip preamble

    Strategy: find the first '{' (or '[') and the matching last '}' (or ']'),
    return the substring. This is the most robust thing short of a real
    streaming JSON parser.
    """
    s = content.strip()
    # Strip code fences if present
    if s.startswith("```"):
        first_newline = s.find("\n")
        if first_newline != -1:
            s = s[first_newline + 1:]
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
    # If the body still has preamble text, slice out the JSON region.
    first_brace = min(
        (i for i in (s.find("{"), s.find("[")) if i != -1),
        default=-1,
    )
    last_close = max(s.rfind("}"), s.rfind("]"))
    if first_brace != -1 and last_close > first_brace:
        s = s[first_brace : last_close + 1]
    return s.strip()
