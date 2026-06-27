"""CardDefinition — the mutable definition record for an imported card.

schemaId: awp.rp.card-definition.v1

CardDefinition is the canonical representation of a parsed card after
import. It aggregates profile, greetings, worldbook, structure hints,
and quarantine data. Lifecycle is managed via CardDefinitionStatus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-definition.v1"
SCHEMA_VERSION = 1


class CardDefinitionStatus:
    STAGED = "staged"
    READY = "ready"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass
class CardDefinition:
    """Mutable definition record for an imported card."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    card_id: str = ""
    card_version: int = 0
    source_id: str = ""
    source_hash: str = ""
    name: str = ""
    display_name: str = ""
    status: str = CardDefinitionStatus.STAGED
    profile: dict[str, Any] = field(default_factory=dict)
    greetings: list[dict[str, Any]] = field(default_factory=list)
    worldbook_catalog: list[dict[str, Any]] = field(default_factory=list)
    worldbook_chunks: list[dict[str, Any]] = field(default_factory=list)
    structure_hints: dict[str, Any] = field(default_factory=dict)
    quarantine_summary: dict[str, Any] = field(default_factory=dict)
    import_report_ref: str = ""
    created_at: str = ""
    updated_at: str = ""
    trace_id: str = ""

    def validate(self) -> list[str]:
        """Validate this CardDefinition. Returns list of errors (empty = valid)."""
        errors = []
        if not self.card_id:
            errors.append("card_id is required")
        if self.card_version < 1:
            errors.append("card_version must be >= 1")
        if not self.source_id:
            errors.append("source_id is required")
        if not self.source_hash:
            errors.append("source_hash is required")
        if not self.name:
            errors.append("name is required")
        if self.schema_id != SCHEMA_ID:
            errors.append(f"schema_id must be {SCHEMA_ID}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "card_id": self.card_id,
            "card_version": self.card_version,
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "name": self.name,
            "display_name": self.display_name,
            "status": self.status,
            "profile": dict(self.profile),
            "greetings": list(self.greetings),
            "worldbook_catalog": list(self.worldbook_catalog),
            "worldbook_chunks": list(self.worldbook_chunks),
            "structure_hints": dict(self.structure_hints),
            "quarantine_summary": dict(self.quarantine_summary),
            "import_report_ref": self.import_report_ref,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardDefinition:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            card_id=data.get("card_id", ""),
            card_version=data.get("card_version", 0),
            source_id=data.get("source_id", ""),
            source_hash=data.get("source_hash", ""),
            name=data.get("name", ""),
            display_name=data.get("display_name", ""),
            status=data.get("status", CardDefinitionStatus.STAGED),
            profile=data.get("profile", {}),
            greetings=data.get("greetings", []),
            worldbook_catalog=data.get("worldbook_catalog", []),
            worldbook_chunks=data.get("worldbook_chunks", []),
            structure_hints=data.get("structure_hints", {}),
            quarantine_summary=data.get("quarantine_summary", {}),
            import_report_ref=data.get("import_report_ref", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            trace_id=data.get("trace_id", ""),
        )
