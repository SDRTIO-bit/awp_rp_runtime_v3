"""ToolResult — the result of a single tool execution.

schemaId: awp.rp.tool-result.v1

Produced by the ToolGateway after executing a tool.
Must have verifiable sourceRefs and a length-limited summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.tool-result.v1"
SCHEMA_VERSION = 1


class ToolResultStatus:
    SUCCESS = "success"
    FAILED = "failed"
    DEGRADED = "degraded"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass
class ToolResult:
    """Result of a single tool execution."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    result_id: str = ""
    request_id: str = ""
    trace_id: str = ""

    # Tool
    tool_id: str = ""

    # Result
    status: str = ToolResultStatus.FAILED
    summary: str = ""  # Length-limited summary
    structured_data: dict[str, Any] = field(default_factory=dict)

    # Evidence and provenance
    evidence: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)

    # Metrics
    duration_ms: int = 0
    token_usage: int = 0

    # Failure
    failure_reason: str = ""

    # Timestamp
    created_at: str = ""

    def is_success(self) -> bool:
        return self.status == ToolResultStatus.SUCCESS

    def is_failed(self) -> bool:
        return self.status in (
            ToolResultStatus.FAILED,
            ToolResultStatus.TIMEOUT,
            ToolResultStatus.PERMISSION_DENIED,
            ToolResultStatus.BUDGET_EXCEEDED,
        )

    def is_degraded(self) -> bool:
        return self.status == ToolResultStatus.DEGRADED

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "tool_id": self.tool_id,
            "status": self.status,
            "summary": self.summary,
            "structured_data": self.structured_data,
            "evidence": self.evidence,
            "source_refs": self.source_refs,
            "duration_ms": self.duration_ms,
            "token_usage": self.token_usage,
            "failure_reason": self.failure_reason,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolResult:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            result_id=data.get("result_id", ""),
            request_id=data.get("request_id", ""),
            trace_id=data.get("trace_id", ""),
            tool_id=data.get("tool_id", ""),
            status=data.get("status", ToolResultStatus.FAILED),
            summary=data.get("summary", ""),
            structured_data=data.get("structured_data", {}),
            evidence=data.get("evidence", []),
            source_refs=data.get("source_refs", []),
            duration_ms=data.get("duration_ms", 0),
            token_usage=data.get("token_usage", 0),
            failure_reason=data.get("failure_reason", ""),
            created_at=data.get("created_at", ""),
        )
