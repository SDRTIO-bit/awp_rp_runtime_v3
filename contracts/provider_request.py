"""Provider Request/Response/Usage/Failure/AttemptReceipt contracts.

schemaId: awp.rp.provider-request.v1
schemaId: awp.rp.provider-response.v1
schemaId: awp.rp.provider-usage.v1
schemaId: awp.rp.provider-failure.v1
schemaId: awp.rp.provider-attempt-receipt.v1

All provider calls are tracked with full trace correlation.
API keys and raw prompts are NEVER included in these contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

REQUEST_SCHEMA = "awp.rp.provider-request.v1"
RESPONSE_SCHEMA = "awp.rp.provider-response.v1"
USAGE_SCHEMA = "awp.rp.provider-usage.v1"
FAILURE_SCHEMA = "awp.rp.provider-failure.v1"
RECEIPT_SCHEMA = "awp.rp.provider-attempt-receipt.v1"
SCHEMA_VERSION = 1


class ProviderRole(str, Enum):
    """Role of the provider call in the pipeline."""
    DIRECTOR = "director"
    DYNAMIC_AGENT = "dynamic_agent"
    WRITER = "writer"
    REVISER = "reviser"
    QUALITY = "quality"


class ProviderMode(str, Enum):
    """Provider integration mode."""
    WRITER_ONLY = "writer_only"
    DIRECTOR_AND_WRITER = "director_and_writer"
    FULL_PIPELINE = "full_pipeline"


class FailureCode(str, Enum):
    """Structured failure codes for provider calls."""
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    INVALID_JSON = "INVALID_JSON"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    INSUFFICIENT_CONTENT = "INSUFFICIENT_CONTENT"
    CANCELLED = "CANCELLED"
    MAX_RETRIES_EXCEEDED = "MAX_RETRIES_EXCEEDED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    GATE_REJECTED = "GATE_REJECTED"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass(frozen=True)
class ProviderUsage:
    """Token usage summary for a single provider call.

    Never contains the raw prompt or response text.
    """
    schema_id: str = USAGE_SCHEMA
    schema_version: int = SCHEMA_VERSION
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    reasoning_tokens: int = 0
    output_content_chars: int = 0
    reasoning_content_chars: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "prompt_cache_hit_tokens": self.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": self.prompt_cache_miss_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "output_content_chars": self.output_content_chars,
            "reasoning_content_chars": self.reasoning_content_chars,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderUsage:
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            model=data.get("model", ""),
            prompt_cache_hit_tokens=data.get("prompt_cache_hit_tokens", 0),
            prompt_cache_miss_tokens=data.get("prompt_cache_miss_tokens", 0),
            reasoning_tokens=data.get("reasoning_tokens", 0),
            output_content_chars=data.get("output_content_chars", 0),
            reasoning_content_chars=data.get("reasoning_content_chars", 0),
        )


@dataclass(frozen=True)
class ProviderFailure:
    """Structured failure from a provider call.

    Never contains the raw prompt, API key, or card content.
    """
    schema_id: str = FAILURE_SCHEMA
    schema_version: int = SCHEMA_VERSION
    failure_code: str = ""
    failure_message: str = ""
    status_code: int = 0
    retry_count: int = 0
    is_retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
            "status_code": self.status_code,
            "retry_count": self.retry_count,
            "is_retryable": self.is_retryable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderFailure:
        return cls(
            failure_code=data.get("failure_code", ""),
            failure_message=data.get("failure_message", ""),
            status_code=data.get("status_code", 0),
            retry_count=data.get("retry_count", 0),
            is_retryable=data.get("is_retryable", False),
        )


@dataclass(frozen=True)
class ProviderAttemptReceipt:
    """Receipt for a single provider call attempt.

    Links to workflowRunId, traceId, turnId, attemptId.
    Contains usage summary but NEVER the raw prompt or response.
    """
    schema_id: str = RECEIPT_SCHEMA
    schema_version: int = SCHEMA_VERSION
    receipt_id: str = ""
    provider_role: str = ""
    provider_request_id: str = ""
    model: str = ""
    # Trace correlation
    workflow_run_id: str = ""
    trace_id: str = ""
    turn_id: str = ""
    attempt_id: str = ""
    # Timing
    started_at: str = ""
    finished_at: str = ""
    latency_ms: int = 0
    # Outcome
    success: bool = False
    failure: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "provider_role": self.provider_role,
            "provider_request_id": self.provider_request_id,
            "model": self.model,
            "workflow_run_id": self.workflow_run_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "failure": self.failure,
            "usage": self.usage,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderAttemptReceipt:
        return cls(
            receipt_id=data.get("receipt_id", ""),
            provider_role=data.get("provider_role", ""),
            provider_request_id=data.get("provider_request_id", ""),
            model=data.get("model", ""),
            workflow_run_id=data.get("workflow_run_id", ""),
            trace_id=data.get("trace_id", ""),
            turn_id=data.get("turn_id", ""),
            attempt_id=data.get("attempt_id", ""),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            latency_ms=data.get("latency_ms", 0),
            success=data.get("success", False),
            failure=dict(data.get("failure", {})),
            usage=dict(data.get("usage", {})),
            retry_count=data.get("retry_count", 0),
        )


@dataclass(frozen=True)
class ProviderResponse:
    """Response from a successful provider call.

    Contains the generated text (for Writer) or structured data (for Director).
    Never contains the raw prompt.
    """
    schema_id: str = RESPONSE_SCHEMA
    schema_version: int = SCHEMA_VERSION
    provider_request_id: str = ""
    text: str = ""
    structured_data: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    finish_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "provider_request_id": self.provider_request_id,
            "text": self.text,
            "structured_data": dict(self.structured_data),
            "usage": dict(self.usage),
            "model": self.model,
            "finish_reason": self.finish_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderResponse:
        return cls(
            provider_request_id=data.get("provider_request_id", ""),
            text=data.get("text", ""),
            structured_data=dict(data.get("structured_data", {})),
            usage=dict(data.get("usage", {})),
            model=data.get("model", ""),
            finish_reason=data.get("finish_reason", ""),
        )
