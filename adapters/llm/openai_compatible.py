"""OpenAI-compatible LLM adapter.

Supports any OpenAI-compatible API endpoint.
API keys are NEVER stored in code, traces, or database.
"""

from __future__ import annotations

import os
import time
from typing import Any

from .base import BaseLlmAdapter, StructuredOutputError


class OpenAICompatibleAdapter(BaseLlmAdapter):
    """OpenAI-compatible LLM adapter.

    Supports any OpenAI-compatible API endpoint.
    API key must be provided via environment variable.
    """

    def __init__(
        self,
        api_key_env: str = "AWP_LLM_API_KEY",
        base_url_env: str = "AWP_LLM_BASE_URL",
        model: str = "gpt-4o-mini",
        default_max_tokens: int = 4000,
    ):
        self._api_key_env = api_key_env
        self._base_url_env = base_url_env
        self._model = model
        self._default_max_tokens = default_max_tokens
        self._call_count = 0
        self._total_tokens_used = 0

    def generate_text(self, prompt: str, max_tokens: int = 4000) -> str:
        """Generate text using OpenAI-compatible API."""
        if not self.is_available:
            raise RuntimeError(
                f"LLM adapter not configured. Set {self._api_key_env} environment variable."
            )

        # In a real implementation, this would call the API
        # For now, raise an error to indicate real LLM is not yet implemented
        raise NotImplementedError(
            "Real OpenAI-compatible LLM adapter not yet implemented. "
            "Use FakeLlmAdapter for testing."
        )

    def generate_structured(
        self, prompt: str, schema: dict[str, Any], max_tokens: int = 4000
    ) -> dict[str, Any]:
        """Generate structured output using OpenAI-compatible API."""
        if not self.is_available:
            raise RuntimeError(
                f"LLM adapter not configured. Set {self._api_key_env} environment variable."
            )

        raise NotImplementedError(
            "Real OpenAI-compatible LLM adapter not yet implemented. "
            "Use FakeLlmAdapter for testing."
        )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def is_available(self) -> bool:
        """Check if API key is configured."""
        api_key = os.environ.get(self._api_key_env, "")
        return bool(api_key)

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def total_tokens_used(self) -> int:
        return self._total_tokens_used
