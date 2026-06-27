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

    logical_card_id: str = ""
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
        """Validate this CardDefinition with recursive nested contract checks.

        Returns list of errors (empty = valid).
        """
        from .card_profile import CardProfile, SCHEMA_ID as PROFILE_SID
        from .card_greeting import CardGreeting, SCHEMA_ID as GREETING_SID
        from .card_worldbook_entry import CardWorldbookEntry, SCHEMA_ID as WB_SID
        from .card_worldbook_chunk import CardWorldbookChunk, SCHEMA_ID as CHUNK_SID
        from .card_structure_hints import CardStructureHints, SCHEMA_ID as HINTS_SID

        errors: list[str] = []

        # Top-level
        if not self.logical_card_id:
            errors.append("logical_card_id is required")
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

        # Nested: profile
        if self.profile:
            p = CardProfile.from_dict(self.profile)
            if p.schema_id != PROFILE_SID:
                errors.append(f"profile.schema_id must be {PROFILE_SID}")
            if p.schema_version != 1:
                errors.append("profile.schema_version must be 1")

        # Nested: greetings
        for i, g_data in enumerate(self.greetings):
            g = CardGreeting.from_dict(g_data)
            if g.schema_id != GREETING_SID:
                errors.append(f"greetings[{i}].schema_id must be {GREETING_SID}")
            if g.schema_version != 1:
                errors.append(f"greetings[{i}].schema_version must be 1")

        # Nested: worldbook_catalog
        for i, e_data in enumerate(self.worldbook_catalog):
            e = CardWorldbookEntry.from_dict(e_data)
            if e.schema_id != WB_SID:
                errors.append(f"worldbook_catalog[{i}].schema_id must be {WB_SID}")
            if e.schema_version != 1:
                errors.append(f"worldbook_catalog[{i}].schema_version must be 1")

        # Nested: worldbook_chunks
        for i, c_data in enumerate(self.worldbook_chunks):
            c = CardWorldbookChunk.from_dict(c_data)
            if c.schema_id != CHUNK_SID:
                errors.append(f"worldbook_chunks[{i}].schema_id must be {CHUNK_SID}")
            if c.schema_version != 1:
                errors.append(f"worldbook_chunks[{i}].schema_version must be 1")
            if self.worldbook_catalog:
                parent_ids = {e.get("entry_id", "") if isinstance(e, dict) else "" for e in self.worldbook_catalog}
                if c.parent_entry_id and c.parent_entry_id not in parent_ids:
                    errors.append(f"worldbook_chunks[{i}].parent_entry_id '{c.parent_entry_id}' not in catalog")

        # Nested: structure_hints
        if self.structure_hints:
            h = CardStructureHints.from_dict(self.structure_hints)
            if h.schema_id != HINTS_SID:
                errors.append(f"structure_hints.schema_id must be {HINTS_SID}")
            if h.schema_version != 1:
                errors.append("structure_hints.schema_version must be 1")

        return errors

    def to_dict(self) -> dict[str, Any]:
        from .card_profile import CardProfile
        from .card_greeting import CardGreeting
        from .card_worldbook_entry import CardWorldbookEntry
        from .card_worldbook_chunk import CardWorldbookChunk
        from .card_structure_hints import CardStructureHints

        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "name": self.name,
            "display_name": self.display_name,
            "status": self.status,
            "profile": CardProfile.from_dict(self.profile).to_dict() if self.profile else {},
            "greetings": [CardGreeting.from_dict(g).to_dict() for g in self.greetings],
            "worldbook_catalog": [CardWorldbookEntry.from_dict(e).to_dict() for e in self.worldbook_catalog],
            "worldbook_chunks": [CardWorldbookChunk.from_dict(c).to_dict() for c in self.worldbook_chunks],
            "structure_hints": CardStructureHints.from_dict(self.structure_hints).to_dict() if self.structure_hints else {},
            "quarantine_summary": dict(self.quarantine_summary),
            "import_report_ref": self.import_report_ref,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardDefinition:
        # Accept both old "card_id" and new "logical_card_id" for migration
        logical_card_id = data.get("logical_card_id", "") or data.get("card_id", "")
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            logical_card_id=logical_card_id,
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
