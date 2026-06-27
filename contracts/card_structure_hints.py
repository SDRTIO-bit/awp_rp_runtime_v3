"""CardStructureHints — structural hints extracted from a card.

schemaId: awp.rp.card-structure-hints.v1

Frozen record of hints that guide downstream agents on phases,
events, variables, relationships, timelines, and unsupported behaviors
found in the source card.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-structure-hints.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardStructureHints:
    """Structural hints extracted from a card."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    phase_hints: list[str] = field(default_factory=list)
    event_hints: list[str] = field(default_factory=list)
    variable_hints: list[str] = field(default_factory=list)
    relationship_hints: list[str] = field(default_factory=list)
    timeline_hints: list[str] = field(default_factory=list)
    unsupported_behavior_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "phase_hints": list(self.phase_hints),
            "event_hints": list(self.event_hints),
            "variable_hints": list(self.variable_hints),
            "relationship_hints": list(self.relationship_hints),
            "timeline_hints": list(self.timeline_hints),
            "unsupported_behavior_hints": list(self.unsupported_behavior_hints),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardStructureHints:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            phase_hints=list(data.get("phase_hints", [])),
            event_hints=list(data.get("event_hints", [])),
            variable_hints=list(data.get("variable_hints", [])),
            relationship_hints=list(data.get("relationship_hints", [])),
            timeline_hints=list(data.get("timeline_hints", [])),
            unsupported_behavior_hints=list(data.get("unsupported_behavior_hints", [])),
        )
