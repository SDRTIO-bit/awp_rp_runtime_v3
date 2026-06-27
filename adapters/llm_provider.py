"""LLM Provider interface.

Abstract interface for LLM backends. Implementations may use
OpenAI, Anthropic, local models, or fakes for testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProviderInterface(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from a prompt."""
        ...

    @abstractmethod
    def generate_structured(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        """Generate structured output matching a JSON schema."""
        ...
