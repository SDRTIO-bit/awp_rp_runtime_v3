"""DeepSeek Provider Adapter via Anthropic API format.

Uses the official anthropic SDK targeting DeepSeek's Anthropic-compatible
endpoint (https://api.deepseek.com/anthropic).

Director uses tool_use for reliable structured output.
Writer uses standard text generation.
NEVER logs or stores the API key in traces/reports.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from .base import BaseLlmAdapter, StructuredOutputError
from ...contracts.provider_request import (
    ProviderUsage, ProviderFailure, ProviderAttemptReceipt,
    ProviderResponse, FailureCode,
)
from ...runtime.provider_env_guard import get_deepseek_api_key, get_deepseek_base_url


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


# Director tool schema — forces structured JSON output via tool_use
DIRECTOR_TOOL = {
    "name": "submit_director_plan",
    "description": "Submit the narrative director plan for this turn",
    "input_schema": {
        "type": "object",
        "properties": {
            "turn_goal": {
                "type": "string",
                "description": "What should happen in this turn"
            },
            "scene_focus": {
                "type": "string",
                "description": "Current scene focus"
            },
            "writer_constraints": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Constraints for the writer"
            },
            "narrative_opportunities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Narrative opportunities to explore"
            },
            "risk_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Risk flags to avoid"
            }
        },
        "required": ["turn_goal", "scene_focus"]
    }
}


class DeepSeekAdapter(BaseLlmAdapter):
    """Real DeepSeek provider adapter via Anthropic API.

    Uses anthropic SDK for reliable HTTP handling.
    Director uses tool_use for guaranteed structured output.
    Requires DEEPSEEK_API_KEY environment variable.
    """

    def __init__(
        self,
        model: str = "deepseek-v4-pro",
        default_max_tokens: int = 2000,
        timeout_seconds: int = 120,
        max_retries: int = 2,
    ):
        self._model = model
        self._default_max_tokens = default_max_tokens
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._call_count = 0
        self._total_tokens = 0
        self._receipts: list[ProviderAttemptReceipt] = []
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Anthropic client for DeepSeek."""
        if self._client is None:
            import anthropic
            api_key = get_deepseek_api_key()
            # DeepSeek Anthropic endpoint
            base_url = os.environ.get(
                "DEEPSEEK_BASE_URL",
                "https://api.deepseek.com/anthropic"
            )
            self._client = anthropic.Anthropic(
                api_key=api_key,
                base_url=base_url,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )
        return self._client

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def is_available(self) -> bool:
        try:
            get_deepseek_api_key()
            return True
        except RuntimeError:
            return False

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def total_tokens_used(self) -> int:
        return self._total_tokens

    @property
    def receipts(self) -> list[ProviderAttemptReceipt]:
        return list(self._receipts)

    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 0,
        provider_role: str = "writer",
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
        model: str = "",
    ) -> tuple[str, ProviderAttemptReceipt]:
        """Generate text from a prompt.

        Returns (text, receipt).
        On failure, returns ("", receipt_with_failure).
        """
        if not max_tokens:
            max_tokens = self._default_max_tokens
        use_model = model or self._model

        request_id = _id("preq", f"{turn_id}:{attempt_id}:{self._call_count}")
        started_at = _now()
        start_time = time.time()

        try:
            client = self._get_client()
            message = client.messages.create(
                model=use_model,
                max_tokens=max_tokens,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}],
            )

            self._call_count += 1
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract text from content blocks
            text = ""
            for block in message.content:
                if hasattr(block, "text"):
                    text += block.text

            # Extract usage
            usage = ProviderUsage(
                prompt_tokens=message.usage.input_tokens if message.usage else 0,
                completion_tokens=message.usage.output_tokens if message.usage else 0,
                total_tokens=(
                    (message.usage.input_tokens + message.usage.output_tokens)
                    if message.usage else 0
                ),
                model=use_model,
            )
            self._total_tokens += usage.total_tokens

            success = bool(text.strip())
            failure = None
            if not success:
                failure = ProviderFailure(
                    failure_code=FailureCode.EMPTY_RESPONSE,
                    failure_message="Empty content in response",
                    retry_count=0,
                )

            receipt = ProviderAttemptReceipt(
                receipt_id=_id("prrec", request_id),
                provider_role=provider_role,
                provider_request_id=request_id,
                model=use_model,
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                turn_id=turn_id,
                attempt_id=attempt_id,
                started_at=started_at,
                finished_at=_now(),
                latency_ms=latency_ms,
                success=success,
                usage=usage.to_dict(),
                retry_count=0,
                failure=failure.to_dict() if failure else {},
            )
            self._receipts.append(receipt)
            return text, receipt

        except Exception as e:
            self._call_count += 1
            latency_ms = int((time.time() - start_time) * 1000)

            code, msg = self._map_exception(e)

            failure = ProviderFailure(
                failure_code=code,
                failure_message=msg,
                retry_count=self._max_retries,
                is_retryable=code in (
                    FailureCode.RATE_LIMITED, FailureCode.SERVER_ERROR,
                    FailureCode.NETWORK_TIMEOUT, FailureCode.CONNECTION_ERROR,
                ),
            )
            receipt = ProviderAttemptReceipt(
                receipt_id=_id("prrec", request_id),
                provider_role=provider_role,
                provider_request_id=request_id,
                model=use_model,
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                turn_id=turn_id,
                attempt_id=attempt_id,
                started_at=started_at,
                finished_at=_now(),
                latency_ms=latency_ms,
                success=False,
                failure=failure.to_dict(),
                retry_count=self._max_retries,
            )
            self._receipts.append(receipt)
            return "", receipt

    def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int = 0,
        provider_role: str = "director",
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
        model: str = "",
    ) -> tuple[dict[str, Any], ProviderAttemptReceipt]:
        """Generate structured JSON via tool_use.

        Uses Anthropic's tool_use feature to guarantee structured output.
        The model MUST call submit_director_plan with the required schema.
        Returns (parsed_data, receipt).
        On failure, returns ({}, receipt_with_failure).
        """
        if not max_tokens:
            max_tokens = self._default_max_tokens
        use_model = model or self._model

        request_id = _id("preq", f"{turn_id}:{attempt_id}:{self._call_count}")
        started_at = _now()
        start_time = time.time()

        try:
            client = self._get_client()
            message = client.messages.create(
                model=use_model,
                max_tokens=max_tokens,
                temperature=0.3,
                system="You are a narrative director for an interactive role-play session. "
                       "Analyze the scene and call the submit_director_plan tool with your plan.",
                messages=[{"role": "user", "content": prompt}],
                tools=[DIRECTOR_TOOL],
                tool_choice={"type": "tool", "name": "submit_director_plan"},
            )

            self._call_count += 1
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract tool_use result
            parsed = {}
            for block in message.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    parsed = block.input
                    break

            # Fallback: try text content as JSON
            if not parsed:
                for block in message.content:
                    if hasattr(block, "text") and block.text.strip():
                        try:
                            cleaned = block.text.strip()
                            if cleaned.startswith("```"):
                                lines = cleaned.split("\n")
                                cleaned = "\n".join(lines[1:])
                                if cleaned.endswith("```"):
                                    cleaned = cleaned[:-3]
                                cleaned = cleaned.strip()
                            parsed = json.loads(cleaned)
                        except json.JSONDecodeError:
                            pass
                        break

            usage = ProviderUsage(
                prompt_tokens=message.usage.input_tokens if message.usage else 0,
                completion_tokens=message.usage.output_tokens if message.usage else 0,
                total_tokens=(
                    (message.usage.input_tokens + message.usage.output_tokens)
                    if message.usage else 0
                ),
                model=use_model,
            )
            self._total_tokens += usage.total_tokens

            success = bool(parsed)
            failure = None
            if not success:
                failure = ProviderFailure(
                    failure_code=FailureCode.EMPTY_RESPONSE,
                    failure_message="No tool_use or valid JSON in response",
                    retry_count=0,
                )

            receipt = ProviderAttemptReceipt(
                receipt_id=_id("prrec", request_id),
                provider_role=provider_role,
                provider_request_id=request_id,
                model=use_model,
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                turn_id=turn_id,
                attempt_id=attempt_id,
                started_at=started_at,
                finished_at=_now(),
                latency_ms=latency_ms,
                success=success,
                usage=usage.to_dict(),
                retry_count=0,
                failure=failure.to_dict() if failure else {},
            )
            self._receipts.append(receipt)
            return parsed, receipt

        except Exception as e:
            self._call_count += 1
            latency_ms = int((time.time() - start_time) * 1000)

            code, msg = self._map_exception(e)

            failure = ProviderFailure(
                failure_code=code,
                failure_message=msg,
                retry_count=self._max_retries,
                is_retryable=code in (
                    FailureCode.RATE_LIMITED, FailureCode.SERVER_ERROR,
                    FailureCode.NETWORK_TIMEOUT, FailureCode.CONNECTION_ERROR,
                ),
            )
            receipt = ProviderAttemptReceipt(
                receipt_id=_id("prrec", request_id),
                provider_role=provider_role,
                provider_request_id=request_id,
                model=use_model,
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                turn_id=turn_id,
                attempt_id=attempt_id,
                started_at=started_at,
                finished_at=_now(),
                latency_ms=latency_ms,
                success=False,
                failure=failure.to_dict(),
                retry_count=self._max_retries,
            )
            self._receipts.append(receipt)
            return {}, receipt

    @staticmethod
    def _map_exception(e: Exception) -> tuple[str, str]:
        """Map anthropic SDK exceptions to FailureCode."""
        import anthropic

        if isinstance(e, anthropic.APITimeoutError):
            return FailureCode.NETWORK_TIMEOUT, "Request timed out"
        elif isinstance(e, anthropic.APIConnectionError):
            return FailureCode.CONNECTION_ERROR, str(e)[:200]
        elif isinstance(e, anthropic.RateLimitError):
            return FailureCode.RATE_LIMITED, "Rate limited"
        elif isinstance(e, anthropic.APIStatusError):
            return FailureCode.SERVER_ERROR, f"HTTP {e.status_code}"
        elif isinstance(e, anthropic.BadRequestError):
            return FailureCode.INVALID_JSON, str(e)[:200]
        else:
            return FailureCode.CANCELLED, f"{type(e).__name__}: {str(e)[:150]}"
