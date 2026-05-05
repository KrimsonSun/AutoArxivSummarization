"""Abstract LLMClient (handoff §4.1)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMUsage:
    """Token usage accounting. Aggregated across all calls in a pipeline run."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    def add(self, prompt: int, completion: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.calls += 1


class LLMError(RuntimeError):
    """All LLM provider errors are wrapped as this for the pipeline layer."""


class LLMClient(ABC):
    """Provider-agnostic structured-output LLM client.

    Each concrete subclass speaks one provider's SDK and converts the
    response into a typed Pydantic model. All clients share the contract:

    -  ``generate`` returns a ``response_schema`` instance or raises ``LLMError``.
    -  Implementations must NOT catch & swallow errors silently — the
       pipeline relies on exceptions to drive retry / fallback logic.
    -  Token usage is recorded on ``self.usage`` so the pipeline can
       aggregate across all clients at the end.
    """

    def __init__(self) -> None:
        self.usage = LLMUsage()

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[T],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> T: ...

    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @property
    @abstractmethod
    def context_window(self) -> int: ...

    @abstractmethod
    async def healthcheck(self) -> bool:
        """Cheap liveness check (handoff §5.4). Returns True or raises LLMError."""
        ...
