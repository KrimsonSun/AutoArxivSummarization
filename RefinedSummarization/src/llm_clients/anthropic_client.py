"""Anthropic Claude client (handoff §5.3, §4.1).

Uses tool-calling for guaranteed JSON output: we declare the response schema
as a tool, force Claude to call that tool, and parse the tool input as our
Pydantic model. This is the canonical pattern from Anthropic's structured-
output guide and is more reliable than regex-extracting JSON from prose.
"""
from __future__ import annotations

from typing import Type, TypeVar

from anthropic import APIError, AsyncAnthropic
from pydantic import BaseModel

from src.config.settings import settings
from src.llm_clients.base import LLMClient, LLMError

T = TypeVar("T", bound=BaseModel)

_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-3-5-sonnet": 200_000,
    "claude-3-5-haiku": 200_000,
    "claude-3-opus": 200_000,
    "claude-sonnet-4": 200_000,
    "claude-sonnet-4-5": 200_000,
}


class AnthropicClient(LLMClient):
    def __init__(self, model: str, temperature: float = 0.7) -> None:
        super().__init__()
        api_key = (
            settings.ANTHROPIC_API_KEY.get_secret_value()
            or ("DEV_PLACEHOLDER" if settings.dev_mode else "")
        )
        if not api_key:
            from src.config.settings import ConfigurationError
            raise ConfigurationError("ANTHROPIC_API_KEY is empty and DEV_MODE is off.")

        kwargs = {"api_key": api_key, "timeout": 120.0}
        if settings.ANTHROPIC_BASE_URL:
            kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
        self._client = AsyncAnthropic(**kwargs)
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
        return 200_000

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[T],
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> T:
        # Build a tool with the response schema; force Claude to call it.
        tool = {
            "name": "emit_response",
            "description": (
                f"Return the response as a {response_schema.__name__} object. "
                "Always call this tool — never reply in plain text."
            ),
            "input_schema": _ensure_object_schema(response_schema.model_json_schema()),
        }
        try:
            r = await self._client.messages.create(
                model=self._model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=self._temperature if temperature is None else temperature,
                max_tokens=max_tokens,
                tools=[tool],
                tool_choice={"type": "tool", "name": "emit_response"},
            )
        except APIError as e:
            raise LLMError(f"Anthropic APIError: {e}") from e
        except Exception as e:
            raise LLMError(f"Anthropic call failed: {e}") from e

        # Extract the tool_use block.
        tool_input = None
        for block in r.content:
            if getattr(block, "type", None) == "tool_use":
                tool_input = block.input
                break
        if tool_input is None:
            raise LLMError(
                f"Anthropic did not return a tool_use block. "
                f"Stop reason: {r.stop_reason}"
            )

        usage = getattr(r, "usage", None)
        if usage is not None:
            self.usage.add(
                prompt=getattr(usage, "input_tokens", 0) or 0,
                completion=getattr(usage, "output_tokens", 0) or 0,
            )

        try:
            return response_schema.model_validate(tool_input)
        except Exception as e:
            raise LLMError(
                f"Schema validation failed for {response_schema.__name__}: {e}\n"
                f"Tool input: {str(tool_input)[:500]}"
            ) from e

    async def healthcheck(self) -> bool:
        try:
            r = await self._client.messages.create(
                model=self._model,
                messages=[{"role": "user", "content": "Reply with: ok"}],
                max_tokens=10,
                temperature=0.0,
            )
            text = "".join(
                getattr(b, "text", "") for b in r.content if getattr(b, "type", "") == "text"
            ).lower()
            return "ok" in text
        except Exception as e:
            raise LLMError(f"Anthropic healthcheck failed: {e}") from e


def _ensure_object_schema(schema: dict) -> dict:
    """Anthropic tools require top-level type=object."""
    if schema.get("type") != "object":
        # Wrap non-object schemas (rare) in an object with a 'value' field.
        return {"type": "object", "properties": {"value": schema}, "required": ["value"]}
    return schema
