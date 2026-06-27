"""MemoryRecallRequest — a recall query against L2/L3 memory.

schemaId: awp.rp.memory-recall-request.v1

Recall is always scoped to a single cardId + sessionId. Filters are
deterministic: entity / alias / tags / status / importance / confidence /
scope / time. The result is deterministically ordered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.memory-recall-request.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MemoryRecallRequest:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    card_id: str = ""
    session_id: str = ""
    snapshot_id: str = ""
    trace_id: str = ""

    # Free-text / keyword query (FTS5)
    query: str = ""

    # Filters
    entity_refs: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    event_tags: list[str] = field(default_factory=list)
    location_tags: list[str] = field(default_factory=list)
    time_tags: list[str] = field(default_factory=list)
    relationship_tags: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)  # empty = active only by default
    scope: str = ""  # "" = any
    min_importance: float = 0.0
    min_confidence: float = 0.0
    exclude_stale: bool = True  # exclude resolved/expired/conflicted from high priority

    limit: int = 10

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "snapshot_id": self.snapshot_id,
            "trace_id": self.trace_id,
            "query": self.query,
            "entity_refs": list(self.entity_refs),
            "aliases": list(self.aliases),
            "event_tags": list(self.event_tags),
            "location_tags": list(self.location_tags),
            "time_tags": list(self.time_tags),
            "relationship_tags": list(self.relationship_tags),
            "statuses": list(self.statuses),
            "scope": self.scope,
            "min_importance": self.min_importance,
            "min_confidence": self.min_confidence,
            "exclude_stale": self.exclude_stale,
            "limit": self.limit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryRecallRequest:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            trace_id=data.get("trace_id", ""),
            query=data.get("query", ""),
            entity_refs=list(data.get("entity_refs", [])),
            aliases=list(data.get("aliases", [])),
            event_tags=list(data.get("event_tags", [])),
            location_tags=list(data.get("location_tags", [])),
            time_tags=list(data.get("time_tags", [])),
            relationship_tags=list(data.get("relationship_tags", [])),
            statuses=list(data.get("statuses", [])),
            scope=data.get("scope", ""),
            min_importance=data.get("min_importance", 0.0),
            min_confidence=data.get("min_confidence", 0.0),
            exclude_stale=data.get("exclude_stale", True),
            limit=data.get("limit", 10),
        )
