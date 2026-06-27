"""RagMemoryRecord — L3 long-term retrievable memory.

schemaId: awp.rp.rag-memory.v1

Defaults to `session` scope. `card_global` must be declared explicitly and may
never leak across sessions implicitly. No cross-cardId sharing. Every record
must carry source_turn_ids and a source CardState revision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.rag-memory.v1"
SCHEMA_VERSION = 1


class RagMemoryScope(str, Enum):
    SESSION = "session"
    CARD_GLOBAL = "card_global"


class RagMemoryStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    CONFLICTED = "conflicted"


@dataclass(frozen=True)
class RagMemoryRecord:
    """A single L3 long-term retrievable memory."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity & isolation
    memory_id: str = ""
    card_id: str = ""
    session_id: str = ""
    scope: str = RagMemoryScope.SESSION.value

    # Content
    content: str = ""
    summary: str = ""

    # Retrieval keys
    entity_refs: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    event_tags: list[str] = field(default_factory=list)
    location_tags: list[str] = field(default_factory=list)
    time_tags: list[str] = field(default_factory=list)
    relationship_tags: list[str] = field(default_factory=list)

    # Source binding
    source_turn_ids: list[str] = field(default_factory=list)
    source_card_state_revision: int = 0

    # Ranking
    importance: float = 0.5
    confidence: float = 0.5

    # Lifecycle
    status: str = RagMemoryStatus.ACTIVE.value
    resolved_at: str = ""
    expires_at: str = ""

    # Timestamps & recall stats
    created_at: str = ""
    updated_at: str = ""
    last_recalled_at: str = ""
    recall_count: int = 0

    # Provenance
    provenance: str = ""  # e.g. "commit:turn_id/memory_commit_id"
    evidence: list[str] = field(default_factory=list)

    # ---- Backward-compat read aliases ----
    @property
    def entities(self) -> list[str]:
        return list(self.entity_refs)

    @property
    def time_range(self) -> str:
        return ";".join(self.time_tags)

    @property
    def source_turn_id(self) -> str:
        return self.source_turn_ids[0] if self.source_turn_ids else ""

    @property
    def state_version(self) -> int:
        return self.source_card_state_revision

    @property
    def is_resolved(self) -> bool:
        return self.status == RagMemoryStatus.RESOLVED.value

    @property
    def is_expired(self) -> bool:
        return self.status == RagMemoryStatus.EXPIRED.value

    def is_high_priority(self) -> bool:
        """Resolved/expired/conflicted are NOT high priority by default."""
        return self.status == RagMemoryStatus.ACTIVE.value

    def with_status(self, status: str) -> RagMemoryRecord:
        return RagMemoryRecord(
            schema_id=self.schema_id, schema_version=self.schema_version,
            memory_id=self.memory_id, card_id=self.card_id, session_id=self.session_id,
            scope=self.scope, content=self.content, summary=self.summary,
            entity_refs=list(self.entity_refs), aliases=list(self.aliases),
            event_tags=list(self.event_tags), location_tags=list(self.location_tags),
            time_tags=list(self.time_tags), relationship_tags=list(self.relationship_tags),
            source_turn_ids=list(self.source_turn_ids),
            source_card_state_revision=self.source_card_state_revision,
            importance=self.importance, confidence=self.confidence,
            status=status, resolved_at=self.resolved_at, expires_at=self.expires_at,
            created_at=self.created_at, updated_at=self.updated_at,
            last_recalled_at=self.last_recalled_at, recall_count=self.recall_count,
            provenance=self.provenance, evidence=list(self.evidence),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "memory_id": self.memory_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "scope": self.scope,
            "content": self.content,
            "summary": self.summary,
            "entity_refs": list(self.entity_refs),
            "aliases": list(self.aliases),
            "event_tags": list(self.event_tags),
            "location_tags": list(self.location_tags),
            "time_tags": list(self.time_tags),
            "relationship_tags": list(self.relationship_tags),
            "source_turn_ids": list(self.source_turn_ids),
            "source_card_state_revision": self.source_card_state_revision,
            "importance": self.importance,
            "confidence": self.confidence,
            "status": self.status,
            "resolved_at": self.resolved_at,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_recalled_at": self.last_recalled_at,
            "recall_count": self.recall_count,
            "provenance": self.provenance,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RagMemoryRecord:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            memory_id=data.get("memory_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            scope=data.get("scope", RagMemoryScope.SESSION.value),
            content=data.get("content", ""),
            summary=data.get("summary", ""),
            entity_refs=list(data.get("entity_refs", data.get("entities", []))),
            aliases=list(data.get("aliases", [])),
            event_tags=list(data.get("event_tags", [])),
            location_tags=list(data.get("location_tags", [])),
            time_tags=list(data.get("time_tags", [])),
            relationship_tags=list(data.get("relationship_tags", [])),
            source_turn_ids=list(data.get("source_turn_ids", [])),
            source_card_state_revision=data.get("source_card_state_revision", data.get("state_version", 0)),
            importance=data.get("importance", 0.5),
            confidence=data.get("confidence", 0.5),
            status=data.get("status", RagMemoryStatus.ACTIVE.value),
            resolved_at=data.get("resolved_at", ""),
            expires_at=data.get("expires_at", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            last_recalled_at=data.get("last_recalled_at", ""),
            recall_count=data.get("recall_count", 0),
            provenance=data.get("provenance", ""),
            evidence=list(data.get("evidence", [])),
        )


# Backward-compat alias.
RagMemoryEntry = RagMemoryRecord
