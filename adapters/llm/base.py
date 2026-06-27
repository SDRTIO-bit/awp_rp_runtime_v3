"""Base LLM adapter interface.

All LLM adapters must implement this interface.
Director, Writer, and Reviser can use different adapter instances.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseLlmAdapter(ABC):
    """Abstract base class for LLM adapters.

    All LLM adapters (fake, OpenAI-compatible, etc.) must implement this.
    """

    @abstractmethod
    def generate_text(self, prompt: str, max_tokens: int = 4000) -> str:
        """Generate text from a prompt."""
        ...

    @abstractmethod
    def generate_structured(
        self, prompt: str, schema: dict[str, Any], max_tokens: int = 4000
    ) -> dict[str, Any]:
        """Generate structured output matching a JSON schema.

        Raises StructuredOutputError if the output doesn't match the schema.
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name for tracing."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this adapter is available and configured."""
        ...


class StructuredOutputError(Exception):
    """Raised when structured output doesn't match the expected schema."""
    def __init__(self, message: str, raw_output: str = ""):
        self.raw_output = raw_output
        super().__init__(message)
