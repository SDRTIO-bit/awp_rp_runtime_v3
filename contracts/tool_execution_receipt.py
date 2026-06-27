"""ToolExecutionReceipt — audit receipt for a tool execution.

schemaId: awp.rp.tool-execution-receipt.v1

Written to the trace for every tool call, regardless of success/failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.tool-execution-receipt.v1"
SCHEMA_VERSION = 1


@dataclass
class ToolExecutionReceipt:
    """Audit receipt for a tool execution."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    receipt_id: str = ""
    request_id: str = ""
    result_id: str = ""
    trace_id: str = ""

    # Tool
    tool_id: str = ""

    # Execution
    status: str = ""
    duration_ms: int = 0
    token_usage: int = 0

    # Permission
    permission_allowed: bool = False
    permission_reason: str = ""

    # Budget
    budget_before: int = 0
    budget_after: int = 0

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "result_id": self.result_id,
            "trace_id": self.trace_id,
            "tool_id": self.tool_id,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "token_usage": self.token_usage,
            "permission_allowed": self.permission_allowed,
            "permission_reason": self.permission_reason,
            "budget_before": self.budget_before,
            "budget_after": self.budget_after,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolExecutionReceipt:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            receipt_id=data.get("receipt_id", ""),
            request_id=data.get("request_id", ""),
            result_id=data.get("result_id", ""),
            trace_id=data.get("trace_id", ""),
            tool_id=data.get("tool_id", ""),
            status=data.get("status", ""),
            duration_ms=data.get("duration_ms", 0),
            token_usage=data.get("token_usage", 0),
            permission_allowed=data.get("permission_allowed", False),
            permission_reason=data.get("permission_reason", ""),
            budget_before=data.get("budget_before", 0),
            budget_after=data.get("budget_after", 0),
            created_at=data.get("created_at", ""),
        )
