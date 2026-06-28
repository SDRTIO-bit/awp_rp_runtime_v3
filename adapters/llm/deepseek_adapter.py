"""DeepSeek Provider Adapter -- supports both OpenAI and Anthropic endpoints.

Auto-detects endpoint from DEEPSEEK_BASE_URL:
  - https://api.deepseek.com/anthropic -> Anthropic SDK
  - https://api.deepseek.com (or /v1)  -> OpenAI SDK

Director uses function calling (OpenAI) or tool_use (Anthropic) for
structured output. Writer uses standard text generation.
Models: deepseek-v4-pro (director), deepseek-v4-flash (writer).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from .base import BaseLlmAdapter
from ...contracts.provider_request import (
    ProviderUsage, ProviderFailure, ProviderAttemptReceipt,
    FailureCode,
)
from ...runtime.provider_env_guard import get_deepseek_api_key, get_deepseek_base_url


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


# OpenAI function calling tool schema
DIRECTOR_TOOL_OPENAI = {
    "type": "function",
    "function": {
        "name": "submit_director_plan",
        "description": "Submit the narrative director plan for this RP turn",
        "parameters": {
            "type": "object",
            "properties": {
                "turn_goal": {"type": "string", "description": "What should happen in this turn"},
                "scene_focus": {"type": "string", "description": "Current scene focus"},
                "writer_constraints": {"type": "array", "items": {"type": "string"}},
                "narrative_opportunities": {"type": "array", "items": {"type": "string"}},
                "risk_flags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["turn_goal", "scene_focus"]
        }
    }
}

# Anthropic tool schema
DIRECTOR_TOOL_ANTHROPIC = {
    "name": "submit_director_plan",
    "description": "Submit the narrative director plan for this RP turn",
    "input_schema": {
        "type": "object",
        "properties": {
            "turn_goal": {"type": "string", "description": "What should happen in this turn"},
            "scene_focus": {"type": "string", "description": "Current scene focus"},
            "writer_constraints": {"type": "array", "items": {"type": "string"}},
            "narrative_opportunities": {"type": "array", "items": {"type": "string"}},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["turn_goal", "scene_focus"]
    }
}


class DeepSeekAdapter(BaseLlmAdapter):
    """DeepSeek provider adapter supporting both OpenAI and Anthropic endpoints."""

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
        self._use_anthropic = False

    def _init_client(self):
        """Detect endpoint and initialize appropriate client."""
        if self._client is not None:
            return
        api_key = get_deepseek_api_key()
        base_url = get_deepseek_base_url()
        self._use_anthropic = "/anthropic" in base_url

        if self._use_anthropic:
            import anthropic
            import httpx
            import certifi
            self._client = anthropic.Anthropic(
                api_key=api_key,
                base_url=base_url,
                timeout=self._timeout,
                max_retries=self._max_retries,
                http_client=httpx.Client(verify=certifi.where()),
            )
        else:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )

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
        if not max_tokens:
            max_tokens = self._default_max_tokens
        use_model = model or self._model
        request_id = _id("preq", f"{turn_id}:{attempt_id}:{self._call_count}")
        started_at = _now()
        start_time = time.time()

        try:
            self._init_client()

            if self._use_anthropic:
                text, usage = self._call_anthropic_text(prompt, max_tokens, use_model)
            else:
                text, usage = self._call_openai_text(prompt, max_tokens, use_model)

            self._call_count += 1
            latency_ms = int((time.time() - start_time) * 1000)
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
                failure=failure.to_dict() if failure else {},
            )
            self._receipts.append(receipt)
            return text, receipt

        except Exception as e:
            return self._handle_error(e, request_id, use_model, provider_role,
                                       workflow_run_id, trace_id, turn_id, attempt_id,
                                       started_at, start_time)

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
        if not max_tokens:
            max_tokens = self._default_max_tokens
        use_model = model or self._model
        request_id = _id("preq", f"{turn_id}:{attempt_id}:{self._call_count}")
        started_at = _now()
        start_time = time.time()

        try:
            self._init_client()

            if self._use_anthropic:
                parsed, usage = self._call_anthropic_structured(prompt, max_tokens, use_model)
            else:
                parsed, usage = self._call_openai_structured(prompt, max_tokens, use_model)

            self._call_count += 1
            latency_ms = int((time.time() - start_time) * 1000)
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
                failure=failure.to_dict() if failure else {},
            )
            self._receipts.append(receipt)
            return parsed, receipt

        except Exception as e:
            text, receipt = self._handle_error(
                e, request_id, use_model, provider_role,
                workflow_run_id, trace_id, turn_id, attempt_id,
                started_at, start_time
            )
            return {}, receipt

    # ── Anthropic SDK calls ──────────────────────────────────────────────

    def _call_anthropic_text(self, prompt: str, max_tokens: int, model: str) -> tuple[str, ProviderUsage]:
        msg = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in msg.content:
            if hasattr(block, "text"):
                text += block.text
        usage = ProviderUsage(
            prompt_tokens=msg.usage.input_tokens if msg.usage else 0,
            completion_tokens=msg.usage.output_tokens if msg.usage else 0,
            total_tokens=(msg.usage.input_tokens + msg.usage.output_tokens) if msg.usage else 0,
            model=model,
        )
        return text, usage

    def _call_anthropic_structured(self, prompt: str, max_tokens: int, model: str) -> tuple[dict, ProviderUsage]:
        msg = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.3,
            system="You are a narrative director for an interactive role-play session. "
                   "Analyze the scene and call the submit_director_plan tool with your plan.",
            messages=[{"role": "user", "content": prompt}],
            tools=[DIRECTOR_TOOL_ANTHROPIC],
            tool_choice={"type": "tool", "name": "submit_director_plan"},
        )
        parsed = {}
        for block in msg.content:
            if hasattr(block, "type") and block.type == "tool_use":
                parsed = block.input
                break
        # Fallback: try text as JSON
        if not parsed:
            for block in msg.content:
                if hasattr(block, "text") and block.text.strip():
                    try:
                        parsed = json.loads(block.text.strip())
                    except json.JSONDecodeError:
                        pass
                    break
        usage = ProviderUsage(
            prompt_tokens=msg.usage.input_tokens if msg.usage else 0,
            completion_tokens=msg.usage.output_tokens if msg.usage else 0,
            total_tokens=(msg.usage.input_tokens + msg.usage.output_tokens) if msg.usage else 0,
            model=model,
        )
        return parsed, usage

    # ── OpenAI SDK calls ─────────────────────────────────────────────────

    def _call_openai_text(self, prompt: str, max_tokens: int, model: str) -> tuple[str, ProviderUsage]:
        resp = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.8,
        )
        text = resp.choices[0].message.content or "" if resp.choices else ""
        usage = ProviderUsage(
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
            total_tokens=resp.usage.total_tokens if resp.usage else 0,
            model=model,
        )
        return text, usage

    def _call_openai_structured(self, prompt: str, max_tokens: int, model: str) -> tuple[dict, ProviderUsage]:
        resp = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a narrative director for an interactive role-play session. "
                                               "Analyze the scene and call the submit_director_plan function with your plan."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
            tools=[DIRECTOR_TOOL_OPENAI],
            tool_choice={"type": "function", "function": {"name": "submit_director_plan"}},
        )
        parsed = {}
        if resp.choices:
            message = resp.choices[0].message
            if message.tool_calls:
                try:
                    parsed = json.loads(message.tool_calls[0].function.arguments)
                except json.JSONDecodeError:
                    pass
            if not parsed and message.content:
                try:
                    parsed = json.loads(message.content.strip())
                except json.JSONDecodeError:
                    pass
        usage = ProviderUsage(
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
            total_tokens=resp.usage.total_tokens if resp.usage else 0,
            model=model,
        )
        return parsed, usage

    # ── Error handling ───────────────────────────────────────────────────

    def _handle_error(self, e, request_id, model, provider_role,
                      workflow_run_id, trace_id, turn_id, attempt_id,
                      started_at, start_time):
        self._call_count += 1
        latency_ms = int((time.time() - start_time) * 1000)
        code, msg = self._map_exception(e)
        failure = ProviderFailure(
            failure_code=code, failure_message=msg,
            retry_count=self._max_retries,
            is_retryable=code in (FailureCode.RATE_LIMITED, FailureCode.SERVER_ERROR,
                                   FailureCode.NETWORK_TIMEOUT, FailureCode.CONNECTION_ERROR),
        )
        receipt = ProviderAttemptReceipt(
            receipt_id=_id("prrec", request_id),
            provider_role=provider_role,
            provider_request_id=request_id,
            model=model,
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

    @staticmethod
    def _map_exception(e: Exception) -> tuple[str, str]:
        # Try anthropic first
        try:
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
        except ImportError:
            pass

        # Try openai
        try:
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
        except ImportError:
            pass

        return FailureCode.CANCELLED, f"{type(e).__name__}: {str(e)[:150]}"
