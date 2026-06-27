"""HistoryRecallRequest — request for the History/Recall Agent.

schemaId: awp.rp.history-recall-request.v1

Scoped to cardId + sessionId. All fields are explicitly bounded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .recall_focus import RecallKind

SCHEMA_ID = "awp.rp.history-recall-request.v1"
SCHEMA_VERSION = 1


@dataclass
class HistoryRecallRequest:
    """Request for the History/Recall Agent."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    request_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    task_run_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # Focus
    focus_entities: list[str] = field(default_factory=list)
    focus_aliases: list[str] = field(default_factory=list)
    recall_kinds: list[RecallKind] = field(default_factory=list)
    query_hints: str = ""

    # Budget
    max_evidence_items: int = 20
    max_tool_calls: int = 7
    budget: dict[str, Any] = field(default_factory=lambda: {"max_tokens": 2000, "timeout_ms": 30000})
    deadline: str = ""

    # Constraints
    required_facts: list[str] = field(default_factory=list)
    must_not_infer: list[str] = field(default_factory=lambda: [
        "未被证据支持的事实不得当成事实输出",
    ])

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "task_run_id": self.task_run_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "focus_entities": list(self.focus_entities),
            "focus_aliases": list(self.focus_aliases),
            "recall_kinds": [k.value for k in self.recall_kinds],
            "query_hints": self.query_hints,
            "max_evidence_items": self.max_evidence_items,
            "max_tool_calls": self.max_tool_calls,
            "budget": dict(self.budget),
            "deadline": self.deadline,
            "required_facts": list(self.required_facts),
            "must_not_infer": list(self.must_not_infer),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryRecallRequest:
        kinds = []
        for k in data.get("recall_kinds", []):
            try:
                kinds.append(RecallKind(k))
            except ValueError:
                pass
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            request_id=data.get("request_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            task_run_id=data.get("task_run_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            focus_entities=list(data.get("focus_entities", [])),
            focus_aliases=list(data.get("focus_aliases", [])),
            recall_kinds=kinds,
            query_hints=data.get("query_hints", ""),
            max_evidence_items=data.get("max_evidence_items", 20),
            max_tool_calls=data.get("max_tool_calls", 7),
            budget=dict(data.get("budget", {"max_tokens": 2000, "timeout_ms": 30000})),
            deadline=data.get("deadline", ""),
            required_facts=list(data.get("required_facts", [])),
            must_not_infer=list(data.get("must_not_infer", [
                "未被证据支持的事实不得当成事实输出",
            ])),
            created_at=data.get("created_at", ""),
        )
