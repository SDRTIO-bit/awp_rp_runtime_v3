"""RecallFocus — what the History/Recall Agent should focus on.

schemaId: awp.rp.recall-focus.v1

Defines the entity, aliases, and recall kinds for a single focus item.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.recall-focus.v1"
SCHEMA_VERSION = 1


class RecallKind(str, Enum):
    """Types of historical recall."""
    EVENT_HISTORY = "event_history"
    RELATIONSHIP_HISTORY = "relationship_history"
    PROMISE_HISTORY = "promise_history"
    SECRET_HISTORY = "secret_history"
    CONFLICT_HISTORY = "conflict_history"
    LOCATION_HISTORY = "location_history"
    IDENTITY_HISTORY = "identity_history"
    TIMELINE_HISTORY = "timeline_history"
    UNRESOLVED_THREAD = "unresolved_thread"


@dataclass
class RecallFocus:
    """A single focus entity with its recall requirements."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    focus_id: str = ""
    entity: str = ""  # Primary entity name or ID
    aliases: list[str] = field(default_factory=list)
    recall_kinds: list[RecallKind] = field(default_factory=list)
    query_hints: str = ""  # Additional query context

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "focus_id": self.focus_id,
            "entity": self.entity,
            "aliases": list(self.aliases),
            "recall_kinds": [k.value for k in self.recall_kinds],
            "query_hints": self.query_hints,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecallFocus:
        kinds = []
        for k in data.get("recall_kinds", []):
            try:
                kinds.append(RecallKind(k))
            except ValueError:
                pass
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            focus_id=data.get("focus_id", ""),
            entity=data.get("entity", ""),
            aliases=list(data.get("aliases", [])),
            recall_kinds=kinds,
            query_hints=data.get("query_hints", ""),
        )
