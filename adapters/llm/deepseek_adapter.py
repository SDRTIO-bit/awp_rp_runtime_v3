"""DeepSeek Provider Adapter -- real LLM calls via OpenAI-compatible API.

Uses the official openai SDK targeting DeepSeek's OpenAI endpoint.
Director uses function calling (tools/tool_choice) for reliable structured output.
Writer uses standard text generation.
Models: deepseek-v4-pro (director), deepseek-v4-flash (writer).
NEVER logs or stores the API key in traces/reports.
"""

from __future__ import annotations

import hashlib
import json
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


# Director tool schema for OpenAI function calling
DIRECTOR_TOOL_OPENAI = {
    "type": "function",
    "function": {
        "name": "submit_director_plan",
        "description": "Submit the narrative director plan for this RP turn",
        "parameters": {
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
}


class DeepSeekAdapter(BaseLlmAdapter):
    """Real DeepSeek provider adapter via OpenAI-compatible API.

    Uses openai SDK for reliable HTTP handling.
    Director uses function calling for guaranteed structured output.
    Requires DEEPSEEK_API_KEY environment variable.
    """

    def __init__(
        self,
        model: str = "deepseek-v4-pro",
        default_max_tokens: int = 2000,
        timeout_seconds: int = 120,
        max_retries: int = 3,
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
        """Lazy-initialize the OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            api_key = get_deepseek_api_key()
            base_url = get_deepseek_base_url()
            self._client = OpenAI(
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
            response = client.chat.completions.create(
                model=use_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.8,
            )

            self._call_count += 1
            latency_ms = int((time.time() - start_time) * 1000)

            text = ""
            finish_reason = "stop"
            if response.choices:
                text = response.choices[0].message.content or ""
                finish_reason = response.choices[0].finish_reason or "stop"

            usage_data = response.usage
            usage = ProviderUsage(
                prompt_tokens=usage_data.prompt_tokens if usage_data else 0,
                completion_tokens=usage_data.completion_tokens if usage_data else 0,
                total_tokens=usage_data.total_tokens if usage_data else 0,
                model=use_model,
            )
            self._total_tokens += usage.total_tokens

            success = bool(text.strip())
            failure = None
            if not success:
                failure = ProviderFailure(
                    failure_code=FailureCode.EMPTY_RESPONSE,
                    failure_message=f"Empty content (finish_reason={finish_reason})",
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
        """Generate structured JSON via function calling.

        Uses OpenAI's tools/tool_choice to force the model to call
        submit_director_plan with the required schema.
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
            response = client.chat.completions.create(
                model=use_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a narrative director for an interactive role-play session. "
                                   "Analyze the scene and call the submit_director_plan function with your plan."
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
                tools=[DIRECTOR_TOOL_OPENAI],
                tool_choice={"type": "function", "function": {"name": "submit_director_plan"}},
            )

            self._call_count += 1
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract tool_call result
            parsed = {}
            if response.choices:
                message = response.choices[0].message
                if message.tool_calls:
                    try:
                        parsed = json.loads(message.tool_calls[0].function.arguments)
                    except json.JSONDecodeError:
                        pass

                # Fallback: try content as JSON
                if not parsed and message.content:
                    try:
                        cleaned = message.content.strip()
                        if cleaned.startswith("```"):
                            lines = cleaned.split("\n")
                            cleaned = "\n".join(lines[1:])
                            if cleaned.endswith("```"):
                                cleaned = cleaned[:-3]
                            cleaned = cleaned.strip()
                        parsed = json.loads(cleaned)
                    except json.JSONDecodeError:
                        pass

            usage_data = response.usage
            usage = ProviderUsage(
                prompt_tokens=usage_data.prompt_tokens if usage_data else 0,
                completion_tokens=usage_data.completion_tokens if usage_data else 0,
                total_tokens=usage_data.total_tokens if usage_data else 0,
                model=use_model,
            )
            self._total_tokens += usage.total_tokens

            success = bool(parsed)
            failure = None
            if not success:
                failure = ProviderFailure(
                    failure_code=FailureCode.EMPTY_RESPONSE,
                    failure_message="No tool_call or valid JSON in response",
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
        """Map openai SDK exceptions to FailureCode."""
        from openai import (
            APIConnectionError, APITimeoutError, RateLimitError,
            APIStatusError, BadRequestError,
        )

        if isinstance(e, APITimeoutError):
            return FailureCode.NETWORK_TIMEOUT, "Request timed out"
        elif isinstance(e, APIConnectionError):
            return FailureCode.CONNECTION_ERROR, str(e)[:200]
        elif isinstance(e, RateLimitError):
            return FailureCode.RATE_LIMITED, "Rate limited"
        elif isinstance(e, APIStatusError):
            return FailureCode.SERVER_ERROR, f"HTTP {e.status_code}"
        elif isinstance(e, BadRequestError):
            return FailureCode.INVALID_JSON, str(e)[:200]
        else:
            return FailureCode.CANCELLED, f"{type(e).__name__}: {str(e)[:150]}"
