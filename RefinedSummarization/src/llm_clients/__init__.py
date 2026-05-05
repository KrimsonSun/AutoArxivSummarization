from src.llm_clients.anthropic_client import AnthropicClient
from src.llm_clients.base import LLMClient, LLMError
from src.llm_clients.google_client import GoogleClient
from src.llm_clients.openai_client import OpenAIClient

__all__ = [
    "AnthropicClient",
    "GoogleClient",
    "LLMClient",
    "LLMError",
    "OpenAIClient",
]


def make_client(provider: str, model: str, temperature: float = 0.7) -> LLMClient:
    """Factory mapping ``provider`` strings from config → concrete client."""
    p = provider.lower()
    if p == "openai":
        return OpenAIClient(model=model, temperature=temperature)
    if p == "anthropic":
        return AnthropicClient(model=model, temperature=temperature)
    if p == "google":
        return GoogleClient(model=model, temperature=temperature)
    raise ValueError(f"Unknown provider: {provider!r}")
