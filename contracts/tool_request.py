"""ToolRequest — a validated tool request sent to the ToolGateway.

schemaId: awp.rp.tool-request.v1

This is the sanitized, budget-checked, permission-checked version
of a PlannedToolRequest. Created by the ToolGateway before execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.tool-request.v1"
SCHEMA_VERSION = 1


@dataclass
class ToolRequest:
    """A validated tool request ready for execution."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    request_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""

    # Tool
    tool_id: str = ""
    sanitized_input: dict[str, Any] = field(default_factory=dict)

    # Budget
    token_budget: int = 1000
    deadline_ms: int = 30000

    # Permission
    permission_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "tool_id": self.tool_id,
            "sanitized_input": self.sanitized_input,
            "token_budget": self.token_budget,
            "deadline_ms": self.deadline_ms,
            "permission_ref": self.permission_ref,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolRequest:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            request_id=data.get("request_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            tool_id=data.get("tool_id", ""),
            sanitized_input=data.get("sanitized_input", {}),
            token_budget=data.get("token_budget", 1000),
            deadline_ms=data.get("deadline_ms", 30000),
            permission_ref=data.get("permission_ref", ""),
        )
