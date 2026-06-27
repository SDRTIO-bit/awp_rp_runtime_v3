"""CardProfile — character profile fields extracted from a card.

schemaId: awp.rp.card-profile.v1

Frozen record of the core character description fields parsed from
the source card. Immutable once created.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-profile.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardProfile:
    """Character profile fields extracted from a card."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    name: str = ""
    description: str = ""
    personality: str = ""
    scenario: str = ""
    mes_example: str = ""
    creator_notes: str = ""
    tags: list[str] = field(default_factory=list)
    extensions_summary: dict[str, Any] = field(default_factory=dict)
    source_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "name": self.name,
            "description": self.description,
            "personality": self.personality,
            "scenario": self.scenario,
            "mes_example": self.mes_example,
            "creator_notes": self.creator_notes,
            "tags": list(self.tags),
            "extensions_summary": dict(self.extensions_summary),
            "source_paths": list(self.source_paths),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardProfile:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            name=data.get("name", ""),
            description=data.get("description", ""),
            personality=data.get("personality", ""),
            scenario=data.get("scenario", ""),
            mes_example=data.get("mes_example", ""),
            creator_notes=data.get("creator_notes", ""),
            tags=list(data.get("tags", [])),
            extensions_summary=data.get("extensions_summary", {}),
            source_paths=list(data.get("source_paths", [])),
        )
