"""MemoryRetentionDecision — deterministic retention / eviction decisions.

schemaId: awp.rp.memory-retention-decision.v1

When the active slot is full (15), a deterministic policy evicts the lowest-
priority records. No random eviction, no LLM silent overwrite.

Priority to KEEP:
  unresolved promises, relationship shifts, secrets/misunderstandings,
  emotional trends directly affecting behavior, explicit unfinished player
  goals, high-importance scene pressure with source evidence.
Priority to EVICT:
  resolved, expired, highly duplicative of new memory, no entity refs,
  low importance, long unrecalled, explicitly conflicting with CardState.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .active_memory import ActiveMemoryRecord

SCHEMA_ID = "awp.rp.memory-retention-decision.v1"
SCHEMA_VERSION = 1


class RetentionAction(str, Enum):
    KEEP = "keep"
    EVICT = "evict"
    MERGE = "merge"
    SUPERSEDE = "supersede"


@dataclass(frozen=True)
class RetentionDecision:
    """Decision for a single active memory during a retention pass."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    memory_id: str = ""
    action: str = RetentionAction.KEEP.value
    reason: str = ""
    score: float = 0.0  # higher = keep
    merge_target_id: str = ""  # when action=merge/supersede

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "memory_id": self.memory_id,
            "action": self.action,
            "reason": self.reason,
            "score": self.score,
            "merge_target_id": self.merge_target_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetentionDecision:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            memory_id=data.get("memory_id", ""),
            action=data.get("action", RetentionAction.KEEP.value),
            reason=data.get("reason", ""),
            score=data.get("score", 0.0),
            merge_target_id=data.get("merge_target_id", ""),
        )


@dataclass(frozen=True)
class MemoryRetentionResult:
    """Outcome of a retention pass over the active slot."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    card_id: str = ""
    session_id: str = ""
    turn_id: str = ""
    decisions: list[RetentionDecision] = field(default_factory=list)
    evicted_ids: list[str] = field(default_factory=list)
    merged_ids: list[str] = field(default_factory=list)
    final_active_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "decisions": [d.to_dict() for d in self.decisions],
            "evicted_ids": list(self.evicted_ids),
            "merged_ids": list(self.merged_ids),
            "final_active_count": self.final_active_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryRetentionResult:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            turn_id=data.get("turn_id", ""),
            decisions=[RetentionDecision.from_dict(d) for d in data.get("decisions", [])],
            evicted_ids=list(data.get("evicted_ids", [])),
            merged_ids=list(data.get("merged_ids", [])),
            final_active_count=data.get("final_active_count", 0),
        )


# Re-export for typing convenience.
__all__ = [
    "SCHEMA_ID", "SCHEMA_VERSION",
    "RetentionAction", "RetentionDecision", "MemoryRetentionResult",
    "ActiveMemoryRecord",
]
