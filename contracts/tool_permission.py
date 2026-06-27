"""ToolPermission — permission check result for a tool call.

schemaId: awp.rp.tool-permission.v1

Used by ToolPermissionPolicy to determine if a tool call is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.tool-permission.v1"
SCHEMA_VERSION = 1


@dataclass
class ToolPermission:
    """Permission check result for a tool call."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    permission_id: str = ""
    tool_id: str = ""
    request_id: str = ""

    # Scope
    card_id: str = ""
    session_id: str = ""

    # Result
    allowed: bool = False
    reason: str = ""

    # Constraints applied
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "permission_id": self.permission_id,
            "tool_id": self.tool_id,
            "request_id": self.request_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "allowed": self.allowed,
            "reason": self.reason,
            "constraints": self.constraints,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolPermission:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            permission_id=data.get("permission_id", ""),
            tool_id=data.get("tool_id", ""),
            request_id=data.get("request_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            allowed=data.get("allowed", False),
            reason=data.get("reason", ""),
            constraints=data.get("constraints", []),
        )
