"""AgentTaskEnvelope — the strict envelope given to each sub-agent.

schemaId: awp.rp.agent-task-envelope.v1

Sub-agents can ONLY read what's in their envelope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.agent-task-envelope.v1"
SCHEMA_VERSION = 1

# Budget sub-structure
@dataclass(frozen=True)
class TaskBudget:
    max_tokens: int = 700
    timeout_ms: int = 30000
    max_tool_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"max_tokens": self.max_tokens, "timeout_ms": self.timeout_ms,
                "max_tool_calls": self.max_tool_calls}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskBudget:
        return cls(
            max_tokens=data.get("max_tokens", 700),
            timeout_ms=data.get("timeout_ms", 30000),
            max_tool_calls=data.get("max_tool_calls", 0),
        )


@dataclass(frozen=True)
class AgentTaskEnvelope:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    task_run_id: str = ""
    trace_id: str = ""
    task_id: str = ""
    role: str = ""
    card_id: str = ""
    session_id: str = ""
    snapshot_id: str = ""
    brief_id: str = ""

    # Allowed data (already cropped by inputFieldAllowlist)
    allowed_snapshot_data: dict[str, Any] = field(default_factory=dict)
    player_input: str = ""

    # Permissions
    allowed_tools: list[str] = field(default_factory=list)  # V1 default: empty
    budget: TaskBudget = field(default_factory=TaskBudget)
    deadline: str = ""
    expected_suggestion_kinds: list[str] = field(default_factory=list)
    policy_version: str = "v1"

    # Hard prohibitions
    prohibitions: list[str] = field(default_factory=lambda: [
        "Cannot write to CardState",
        "Cannot write to TurnRecord",
        "Cannot write to ActiveMemory",
        "Cannot write to RAGMemory",
        "Cannot delegate to sub-agents",
        "Cannot generate player-visible final text",
        "Cannot access database connections",
        "Cannot register new tools",
        "Cannot call Director or Pool",
    ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "task_run_id": self.task_run_id, "trace_id": self.trace_id,
            "task_id": self.task_id, "role": self.role,
            "card_id": self.card_id, "session_id": self.session_id,
            "snapshot_id": self.snapshot_id, "brief_id": self.brief_id,
            "allowed_snapshot_data": self.allowed_snapshot_data,
            "player_input": self.player_input,
            "allowed_tools": self.allowed_tools,
            "budget": self.budget.to_dict(),
            "deadline": self.deadline,
            "expected_suggestion_kinds": self.expected_suggestion_kinds,
            "policy_version": self.policy_version,
            "prohibitions": self.prohibitions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTaskEnvelope:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            task_run_id=data.get("task_run_id", ""),
            trace_id=data.get("trace_id", ""),
            task_id=data.get("task_id", ""),
            role=data.get("role", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            brief_id=data.get("brief_id", ""),
            allowed_snapshot_data=data.get("allowed_snapshot_data", {}),
            player_input=data.get("player_input", ""),
            allowed_tools=data.get("allowed_tools", []),
            budget=TaskBudget.from_dict(data.get("budget", {})),
            deadline=data.get("deadline", ""),
            expected_suggestion_kinds=data.get("expected_suggestion_kinds", []),
            policy_version=data.get("policy_version", "v1"),
            prohibitions=data.get("prohibitions", [
                "Cannot write to CardState", "Cannot write to TurnRecord",
                "Cannot write to ActiveMemory", "Cannot write to RAGMemory",
                "Cannot delegate to sub-agents", "Cannot generate player-visible final text",
                "Cannot access database connections", "Cannot register new tools",
                "Cannot call Director or Pool",
            ]),
        )
