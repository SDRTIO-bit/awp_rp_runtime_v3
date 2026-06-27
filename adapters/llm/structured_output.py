"""Structured output utilities for LLM adapters.

Provides schema validation and retry logic for structured outputs.
"""

from __future__ import annotations

import json
from typing import Any

from .base import BaseLlmAdapter, StructuredOutputError


def generate_with_retry(
    adapter: BaseLlmAdapter,
    prompt: str,
    schema: dict[str, Any],
    max_retries: int = 2,
    max_tokens: int = 4000,
) -> dict[str, Any]:
    """Generate structured output with retry on schema mismatch.

    Raises StructuredOutputError if all retries fail.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = adapter.generate_structured(prompt, schema, max_tokens)
            # Basic validation: check required fields
            if "type" in schema and schema["type"] == "object":
                if "required" in schema:
                    for field in schema["required"]:
                        if field not in result:
                            raise StructuredOutputError(
                                f"Missing required field: {field}",
                                raw_output=json.dumps(result),
                            )
            return result
        except StructuredOutputError as e:
            last_error = e
            if attempt < max_retries:
                continue
            raise

    raise last_error or StructuredOutputError("All retries failed")
