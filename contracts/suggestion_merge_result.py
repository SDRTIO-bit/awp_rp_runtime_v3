"""SuggestionMergeResult — result of merging sub-agent suggestions.

schemaId: awp.rp.suggestion-merge-result.v1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .agent_suggestion import AgentSuggestion

SCHEMA_ID = "awp.rp.suggestion-merge-result.v1"
SCHEMA_VERSION = 1


class MergeDecision(str, Enum):
    ADOPTED = "adopted"
    IGNORED = "ignored"
    CONFLICT = "conflict"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class MergeItem:
    suggestion_id: str = ""
    task_id: str = ""
    role: str = ""
    decision: MergeDecision = MergeDecision.IGNORED
    reason: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    resolution: str = ""  # How conflict was resolved
    priority_score: float = 0.0

    # Backward compat: store the full suggestion
    suggestion: AgentSuggestion | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "task_id": self.task_id, "role": self.role,
            "decision": self.decision.value,
            "reason": self.reason, "evidence_refs": self.evidence_refs,
            "resolution": self.resolution, "priority_score": self.priority_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergeItem:
        return cls(
            suggestion_id=data.get("suggestion_id", ""),
            task_id=data.get("task_id", ""),
            role=data.get("role", ""),
            decision=MergeDecision(data.get("decision", "ignored")),
            reason=data.get("reason", ""),
            evidence_refs=data.get("evidence_refs", []),
            resolution=data.get("resolution", ""),
            priority_score=data.get("priority_score", 0.0),
        )


@dataclass
class SuggestionMergeResult:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    merge_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    brief_id: str = ""
    plan_id: str = ""

    adopted: list[MergeItem] = field(default_factory=list)
    ignored: list[MergeItem] = field(default_factory=list)
    conflicts: list[MergeItem] = field(default_factory=list)
    degraded_tasks: list[str] = field(default_factory=list)
    failed_tasks: list[str] = field(default_factory=list)

    writer_guidance: list[str] = field(default_factory=list)
    state_proposal_hints: list[dict[str, Any]] = field(default_factory=list)
    memory_proposal_hints: list[dict[str, Any]] = field(default_factory=list)

    created_at: str = ""

    # Backward compat
    @property
    def items(self) -> list[MergeItem]:
        return self.adopted + self.ignored + self.conflicts

    @property
    def adopted_count(self) -> int:
        return len(self.adopted)

    @property
    def ignored_count(self) -> int:
        return len(self.ignored)

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    def get_adopted(self) -> list[MergeItem]:
        return self.adopted

    def get_ignored(self) -> list[MergeItem]:
        return self.ignored

    def get_conflicts(self) -> list[MergeItem]:
        return self.conflicts

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "merge_id": self.merge_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "brief_id": self.brief_id,
            "plan_id": self.plan_id,
            "adopted": [i.to_dict() for i in self.adopted],
            "ignored": [i.to_dict() for i in self.ignored],
            "conflicts": [i.to_dict() for i in self.conflicts],
            "degraded_tasks": self.degraded_tasks,
            "failed_tasks": self.failed_tasks,
            "writer_guidance": self.writer_guidance,
            "state_proposal_hints": self.state_proposal_hints,
            "memory_proposal_hints": self.memory_proposal_hints,
            "created_at": self.created_at,
            # backward compat
            "adopted_count": self.adopted_count,
            "ignored_count": self.ignored_count,
            "conflict_count": self.conflict_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SuggestionMergeResult:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            merge_id=data.get("merge_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            brief_id=data.get("brief_id", ""),
            plan_id=data.get("plan_id", ""),
            adopted=[MergeItem.from_dict(i) for i in data.get("adopted", [])],
            ignored=[MergeItem.from_dict(i) for i in data.get("ignored", [])],
            conflicts=[MergeItem.from_dict(i) for i in data.get("conflicts", [])],
            degraded_tasks=data.get("degraded_tasks", []),
            failed_tasks=data.get("failed_tasks", []),
            writer_guidance=data.get("writer_guidance", []),
            state_proposal_hints=data.get("state_proposal_hints", []),
            memory_proposal_hints=data.get("memory_proposal_hints", []),
            created_at=data.get("created_at", ""),
        )
