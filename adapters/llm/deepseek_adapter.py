"""DeepSeek Provider Adapter -- real LLM calls via OpenAI-compatible API.

This adapter makes actual HTTP calls to DeepSeek.
It NEVER logs or stores the API key in traces/reports.
All errors produce structured ProviderFailure, never raw exceptions.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
import urllib.error
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


class DeepSeekAdapter(BaseLlmAdapter):
    """Real DeepSeek provider adapter.

    Uses OpenAI-compatible chat completions API.
    Requires DEEPSEEK_API_KEY environment variable.
    """

    def __init__(
        self,
        model: str = "deepseek-chat",
        default_max_tokens: int = 2000,
        timeout_seconds: int = 60,
        max_retries: int = 1,
    ):
        self._model = model
        self._default_max_tokens = default_max_tokens
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._call_count = 0
        self._total_tokens = 0
        self._receipts: list[ProviderAttemptReceipt] = []

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
    ) -> tuple[str, ProviderAttemptReceipt]:
        """Generate text from a prompt.

        Returns (text, receipt).
        On failure, returns ("", receipt_with_failure).
        """
        if not max_tokens:
            max_tokens = self._default_max_tokens

        request_id = _id("preq", f"{turn_id}:{attempt_id}:{self._call_count}")
        started_at = _now()
        start_time = time.time()

        last_failure = None
        for retry in range(self._max_retries + 1):
            try:
                api_key = get_deepseek_api_key()
                base_url = get_deepseek_base_url()

                # Build request payload (OpenAI-compatible format)
                payload = {
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.8,
                }

                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    f"{base_url}/chat/completions",
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))

                self._call_count += 1
                latency_ms = int((time.time() - start_time) * 1000)

                # Extract response
                choices = body.get("choices", [])
                if not choices:
                    last_failure = ProviderFailure(
                        failure_code=FailureCode.EMPTY_RESPONSE,
                        failure_message="No choices in response",
                        retry_count=retry,
                    )
                    continue

                text = choices[0].get("message", {}).get("content", "")
                if not text.strip():
                    last_failure = ProviderFailure(
                        failure_code=FailureCode.EMPTY_RESPONSE,
                        failure_message="Empty content in response",
                        retry_count=retry,
                    )
                    continue

                finish_reason = choices[0].get("finish_reason", "stop")

                # Extract usage
                usage_data = body.get("usage", {})
                usage = ProviderUsage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                    model=self._model,
                )
                self._total_tokens += usage.total_tokens

                receipt = ProviderAttemptReceipt(
                    receipt_id=_id("prrec", request_id),
                    provider_role=provider_role,
                    provider_request_id=request_id,
                    model=self._model,
                    workflow_run_id=workflow_run_id,
                    trace_id=trace_id,
                    turn_id=turn_id,
                    attempt_id=attempt_id,
                    started_at=started_at,
                    finished_at=_now(),
                    latency_ms=latency_ms,
                    success=True,
                    usage=usage.to_dict(),
                    retry_count=retry,
                )
                self._receipts.append(receipt)
                return text, receipt

            except urllib.error.HTTPError as e:
                self._call_count += 1
                latency_ms = int((time.time() - start_time) * 1000)
                status_code = e.code

                if status_code == 429:
                    code = FailureCode.RATE_LIMITED
                    retryable = True
                elif 500 <= status_code < 600:
                    code = FailureCode.SERVER_ERROR
                    retryable = True
                else:
                    code = FailureCode.SERVER_ERROR
                    retryable = False

                last_failure = ProviderFailure(
                    failure_code=code,
                    failure_message=f"HTTP {status_code}",
                    status_code=status_code,
                    retry_count=retry,
                    is_retryable=retryable,
                )

                if not retryable or retry >= self._max_retries:
                    break

            except urllib.error.URLError as e:
                self._call_count += 1
                latency_ms = int((time.time() - start_time) * 1000)
                last_failure = ProviderFailure(
                    failure_code=FailureCode.CONNECTION_ERROR,
                    failure_message=str(e.reason)[:200],
                    retry_count=retry,
                    is_retryable=True,
                )
                if retry >= self._max_retries:
                    break

            except TimeoutError:
                self._call_count += 1
                latency_ms = int((time.time() - start_time) * 1000)
                last_failure = ProviderFailure(
                    failure_code=FailureCode.NETWORK_TIMEOUT,
                    failure_message=f"Timeout after {self._timeout}s",
                    retry_count=retry,
                    is_retryable=True,
                )
                if retry >= self._max_retries:
                    break

            except Exception as e:
                self._call_count += 1
                latency_ms = int((time.time() - start_time) * 1000)
                last_failure = ProviderFailure(
                    failure_code=FailureCode.CANCELLED,
                    failure_message=type(e).__name__,
                    retry_count=retry,
                    is_retryable=False,
                )
                break

        # All retries exhausted
        receipt = ProviderAttemptReceipt(
            receipt_id=_id("prrec", request_id),
            provider_role=provider_role,
            provider_request_id=request_id,
            model=self._model,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
            started_at=started_at,
            finished_at=_now(),
            latency_ms=int((time.time() - start_time) * 1000),
            success=False,
            failure=last_failure.to_dict() if last_failure else {},
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
    ) -> tuple[dict[str, Any], ProviderAttemptReceipt]:
        """Generate structured JSON from a prompt.

        Returns (parsed_data, receipt).
        On failure, returns ({}, receipt_with_failure).
        """
        if not max_tokens:
            max_tokens = self._default_max_tokens

        request_id = _id("preq", f"{turn_id}:{attempt_id}:{self._call_count}")
        started_at = _now()
        start_time = time.time()

        # Add JSON instruction to prompt
        json_instruction = (
            "\n\nPlease respond with valid JSON only. "
            "Do not include any text before or after the JSON object."
        )
        full_prompt = prompt + json_instruction

        last_failure = None
        for retry in range(self._max_retries + 1):
            try:
                api_key = get_deepseek_api_key()
                base_url = get_deepseek_base_url()

                payload = {
                    "model": self._model,
                    "messages": [{"role": "user", "content": full_prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.3,  # Lower temp for structured output
                }

                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    f"{base_url}/chat/completions",
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))

                self._call_count += 1
                latency_ms = int((time.time() - start_time) * 1000)

                choices = body.get("choices", [])
                if not choices:
                    last_failure = ProviderFailure(
                        failure_code=FailureCode.EMPTY_RESPONSE,
                        failure_message="No choices in response",
                        retry_count=retry,
                    )
                    continue

                raw_text = choices[0].get("message", {}).get("content", "")
                if not raw_text.strip():
                    last_failure = ProviderFailure(
                        failure_code=FailureCode.EMPTY_RESPONSE,
                        failure_message="Empty content in response",
                        retry_count=retry,
                    )
                    continue

                # Try to parse JSON
                try:
                    # Strip markdown code fences if present
                    cleaned = raw_text.strip()
                    if cleaned.startswith("```"):
                        lines = cleaned.split("\n")
                        cleaned = "\n".join(lines[1:])
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        cleaned = cleaned.strip()

                    parsed = json.loads(cleaned)
                except json.JSONDecodeError:
                    last_failure = ProviderFailure(
                        failure_code=FailureCode.INVALID_JSON,
                        failure_message="Response is not valid JSON",
                        retry_count=retry,
                        is_retryable=True,
                    )
                    if retry >= self._max_retries:
                        break
                    continue

                # Validate schema (basic check: required keys present)
                if schema and isinstance(schema, dict):
                    required_keys = schema.get("required", [])
                    if isinstance(required_keys, list):
                        missing = [k for k in required_keys if k not in parsed]
                        if missing:
                            last_failure = ProviderFailure(
                                failure_code=FailureCode.SCHEMA_MISMATCH,
                                failure_message=f"Missing keys: {missing}",
                                retry_count=retry,
                                is_retryable=True,
                            )
                            if retry >= self._max_retries:
                                break
                            continue

                usage_data = body.get("usage", {})
                usage = ProviderUsage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                    model=self._model,
                )
                self._total_tokens += usage.total_tokens

                receipt = ProviderAttemptReceipt(
                    receipt_id=_id("prrec", request_id),
                    provider_role=provider_role,
                    provider_request_id=request_id,
                    model=self._model,
                    workflow_run_id=workflow_run_id,
                    trace_id=trace_id,
                    turn_id=turn_id,
                    attempt_id=attempt_id,
                    started_at=started_at,
                    finished_at=_now(),
                    latency_ms=latency_ms,
                    success=True,
                    usage=usage.to_dict(),
                    retry_count=retry,
                )
                self._receipts.append(receipt)
                return parsed, receipt

            except urllib.error.HTTPError as e:
                self._call_count += 1
                status_code = e.code
                if status_code == 429:
                    code = FailureCode.RATE_LIMITED
                    retryable = True
                elif 500 <= status_code < 600:
                    code = FailureCode.SERVER_ERROR
                    retryable = True
                else:
                    code = FailureCode.SERVER_ERROR
                    retryable = False

                last_failure = ProviderFailure(
                    failure_code=code,
                    failure_message=f"HTTP {status_code}",
                    status_code=status_code,
                    retry_count=retry,
                    is_retryable=retryable,
                )
                if not retryable or retry >= self._max_retries:
                    break

            except urllib.error.URLError as e:
                self._call_count += 1
                last_failure = ProviderFailure(
                    failure_code=FailureCode.CONNECTION_ERROR,
                    failure_message=str(e.reason)[:200],
                    retry_count=retry,
                    is_retryable=True,
                )
                if retry >= self._max_retries:
                    break

            except TimeoutError:
                self._call_count += 1
                last_failure = ProviderFailure(
                    failure_code=FailureCode.NETWORK_TIMEOUT,
                    failure_message=f"Timeout after {self._timeout}s",
                    retry_count=retry,
                    is_retryable=True,
                )
                if retry >= self._max_retries:
                    break

            except Exception as e:
                self._call_count += 1
                last_failure = ProviderFailure(
                    failure_code=FailureCode.CANCELLED,
                    failure_message=type(e).__name__,
                    retry_count=retry,
                    is_retryable=False,
                )
                break

        receipt = ProviderAttemptReceipt(
            receipt_id=_id("prrec", request_id),
            provider_role=provider_role,
            provider_request_id=request_id,
            model=self._model,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
            started_at=started_at,
            finished_at=_now(),
            latency_ms=int((time.time() - start_time) * 1000),
            success=False,
            failure=last_failure.to_dict() if last_failure else {},
            retry_count=self._max_retries,
        )
        self._receipts.append(receipt)
        return {}, receipt
