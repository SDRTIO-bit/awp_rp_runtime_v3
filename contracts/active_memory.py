"""ActiveMemoryRecord — L2 active plot-attention memory (max 15 per card+session).

schemaId: awp.rp.active-memory.v1

ActiveMemory is a plot-attention slot, NOT a generic summary pool.
Each record binds to at least one source accepted turn and a CardState revision.
Only the ActiveMemoryCommitRuntime may write these records (via MemoryCommitPlan).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.active-memory.v1"
SCHEMA_VERSION = 1

# Default hard limits (also enforced by MemoryPolicy).
MAX_ACTIVE_PER_SCOPE = 15
SUMMARY_MIN_CHARS = 30
SUMMARY_MAX_CHARS = 80


class ActiveMemoryKind(str, Enum):
    """Kind of active plot memory."""
    UNRESOLVED_THREAD = "unresolved_thread"
    PROMISE = "promise"
    SECRET = "secret"
    MISUNDERSTANDING = "misunderstanding"
    RELATIONSHIP_SHIFT = "relationship_shift"
    EMOTIONAL_TREND = "emotional_trend"
    PLAYER_GOAL = "player_goal"
    SCENE_PRESSURE = "scene_pressure"
    FUTURE_HOOK = "future_hook"
    PERSISTENT_FACT_REFERENCE = "persistent_fact_reference"


class ActiveMemoryStatus(str, Enum):
    """Lifecycle status of an active memory."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    EVICTED = "evicted"
    CONFLICTED = "conflicted"


@dataclass(frozen=True)
class ActiveMemoryRecord:
    """A single L2 active plot memory (up to 15 active per card+session).

    `summary` must be 30-80 Unicode chars of concise plot memory — never novel
    prose, never model CoT, never raw card/worldbook/System Prompt text.
    Must bind to >= 1 source turn id and a source CardState revision.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity & isolation
    memory_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # Content (M1 formal name = summary)
    summary: str = ""
    kind: str = ActiveMemoryKind.UNRESOLVED_THREAD.value

    # Entity / source binding
    entity_refs: list[str] = field(default_factory=list)
    source_turn_ids: list[str] = field(default_factory=list)
    source_snapshot_ids: list[str] = field(default_factory=list)
    source_card_state_revision: int = 0

    # Ranking
    importance: float = 0.5
    confidence: float = 0.5

    # Lifecycle
    status: str = ActiveMemoryStatus.ACTIVE.value
    resolved_at: str = ""
    expires_at: str = ""

    # Retention provenance
    retention_reason: str = ""
    merge_reason: str = ""
    eviction_reason: str = ""

    # Timestamps & recall stats
    created_at: str = ""
    updated_at: str = ""
    last_recalled_at: str = ""
    recall_count: int = 0

    # ---- Backward-compat read aliases (old field names -> new fields) ----
    @property
    def content(self) -> str:
        return self.summary

    @property
    def memory_type(self) -> str:
        return self.kind

    @property
    def entities(self) -> list[str]:
        return list(self.entity_refs)

    @property
    def source_turn_id(self) -> str:
        return self.source_turn_ids[0] if self.source_turn_ids else ""

    @property
    def state_version(self) -> int:
        return self.source_card_state_revision

    # ---- Helpers ----
    def is_active(self) -> bool:
        return self.status == ActiveMemoryStatus.ACTIVE.value

    def with_status(self, status: str, reason: str = "") -> ActiveMemoryRecord:
        """Return a copy with a new status (frozen -> replace)."""
        return ActiveMemoryRecord(
            schema_id=self.schema_id, schema_version=self.schema_version,
            memory_id=self.memory_id, card_id=self.card_id, session_id=self.session_id,
            summary=self.summary, kind=self.kind, entity_refs=list(self.entity_refs),
            source_turn_ids=list(self.source_turn_ids),
            source_snapshot_ids=list(self.source_snapshot_ids),
            source_card_state_revision=self.source_card_state_revision,
            importance=self.importance, confidence=self.confidence,
            status=status, resolved_at=self.resolved_at, expires_at=self.expires_at,
            retention_reason=self.retention_reason, merge_reason=self.merge_reason,
            eviction_reason=reason or self.eviction_reason,
            created_at=self.created_at, updated_at=self.updated_at,
            last_recalled_at=self.last_recalled_at, recall_count=self.recall_count,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "memory_id": self.memory_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "summary": self.summary,
            "kind": self.kind,
            "entity_refs": list(self.entity_refs),
            "source_turn_ids": list(self.source_turn_ids),
            "source_snapshot_ids": list(self.source_snapshot_ids),
            "source_card_state_revision": self.source_card_state_revision,
            "importance": self.importance,
            "confidence": self.confidence,
            "status": self.status,
            "resolved_at": self.resolved_at,
            "expires_at": self.expires_at,
            "retention_reason": self.retention_reason,
            "merge_reason": self.merge_reason,
            "eviction_reason": self.eviction_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_recalled_at": self.last_recalled_at,
            "recall_count": self.recall_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActiveMemoryRecord:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            memory_id=data.get("memory_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            summary=data.get("summary", data.get("content", "")),
            kind=data.get("kind", data.get("memory_type", ActiveMemoryKind.UNRESOLVED_THREAD.value)),
            entity_refs=list(data.get("entity_refs", data.get("entities", []))),
            source_turn_ids=list(data.get("source_turn_ids", [])),
            source_snapshot_ids=list(data.get("source_snapshot_ids", [])),
            source_card_state_revision=data.get("source_card_state_revision", data.get("state_version", 0)),
            importance=data.get("importance", 0.5),
            confidence=data.get("confidence", 0.5),
            status=data.get("status", ActiveMemoryStatus.ACTIVE.value),
            resolved_at=data.get("resolved_at", ""),
            expires_at=data.get("expires_at", ""),
            retention_reason=data.get("retention_reason", ""),
            merge_reason=data.get("merge_reason", ""),
            eviction_reason=data.get("eviction_reason", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            last_recalled_at=data.get("last_recalled_at", ""),
            recall_count=data.get("recall_count", 0),
        )


# Backward-compat alias used across stores / runtimes / policies.
ActiveMemoryEntry = ActiveMemoryRecord
