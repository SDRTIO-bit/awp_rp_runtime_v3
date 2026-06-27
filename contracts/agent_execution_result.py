"""AgentExecutionResult — result of running a single sub-agent task.

schemaId: awp.rp.agent-execution-result.v1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent_suggestion import AgentSuggestion

SCHEMA_ID = "awp.rp.agent-execution-result.v1"
SCHEMA_VERSION = 1


@dataclass
class AgentExecutionResult:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    task_run_id: str = ""
    task_id: str = ""
    role: str = ""
    trace_id: str = ""

    success: bool = False
    suggestions: list[AgentSuggestion] = field(default_factory=list)
    error_message: str = ""
    degraded: bool = False  # True if task partially succeeded

    tokens_used: int = 0
    tool_calls_made: int = 0
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "task_run_id": self.task_run_id, "task_id": self.task_id,
            "role": self.role, "trace_id": self.trace_id,
            "success": self.success,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "error_message": self.error_message, "degraded": self.degraded,
            "tokens_used": self.tokens_used, "tool_calls_made": self.tool_calls_made,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentExecutionResult:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            task_run_id=data.get("task_run_id", ""),
            task_id=data.get("task_id", ""),
            role=data.get("role", ""),
            trace_id=data.get("trace_id", ""),
            success=data.get("success", False),
            suggestions=[AgentSuggestion.from_dict(s) for s in data.get("suggestions", [])],
            error_message=data.get("error_message", ""),
            degraded=data.get("degraded", False),
            tokens_used=data.get("tokens_used", 0),
            tool_calls_made=data.get("tool_calls_made", 0),
            duration_ms=data.get("duration_ms", 0),
        )
