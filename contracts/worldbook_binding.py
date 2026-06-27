"""WorldbookBinding — binds static worldbook resources to a session.

schemaId: awp.rp.worldbook-binding.v1

Binding ≠ activation. Binding ≠ injection. Binding ≠ memory write.
The Worldbook Retriever reads from this binding later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.worldbook-binding.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WorldbookBindingEntry:
    """A single entry in a WorldbookBinding."""
    schema_id: str = "awp.rp.worldbook-binding-entry.v1"
    schema_version: int = 1

    entry_id: str = ""
    source_uid: int = -1
    enabled: bool = True
    constant: bool = False
    selective: bool = False
    has_chunks: bool = False
    chunk_ids: list[str] = field(default_factory=list)
    activation_status: str = "candidate"  # candidate | disabled | deferred | unsupported

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "entry_id": self.entry_id,
            "source_uid": self.source_uid,
            "enabled": self.enabled,
            "constant": self.constant,
            "selective": self.selective,
            "has_chunks": self.has_chunks,
            "chunk_ids": list(self.chunk_ids),
            "activation_status": self.activation_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldbookBindingEntry:
        return cls(
            schema_id=data.get("schema_id", "awp.rp.worldbook-binding-entry.v1"),
            schema_version=data.get("schema_version", 1),
            entry_id=data.get("entry_id", ""),
            source_uid=data.get("source_uid", -1),
            enabled=data.get("enabled", True),
            constant=data.get("constant", False),
            selective=data.get("selective", False),
            has_chunks=data.get("has_chunks", False),
            chunk_ids=list(data.get("chunk_ids", [])),
            activation_status=data.get("activation_status", "candidate"),
        )


@dataclass(frozen=True)
class WorldbookBinding:
    """Binds static worldbook resources to a session for later retrieval."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    worldbook_binding_id: str = ""
    session_id: str = ""
    logical_card_id: str = ""
    card_version: int = 0
    source_hash: str = ""
    catalog_ref: str = ""
    bound_entry_ids: list[str] = field(default_factory=list)
    bound_chunk_ids: list[str] = field(default_factory=list)
    disabled_entry_ids: list[str] = field(default_factory=list)
    deferred_entry_ids: list[str] = field(default_factory=list)
    unsupported_activation_entry_ids: list[str] = field(default_factory=list)
    entries: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "worldbook_binding_id": self.worldbook_binding_id,
            "session_id": self.session_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "source_hash": self.source_hash,
            "catalog_ref": self.catalog_ref,
            "bound_entry_ids": list(self.bound_entry_ids),
            "bound_chunk_ids": list(self.bound_chunk_ids),
            "disabled_entry_ids": list(self.disabled_entry_ids),
            "deferred_entry_ids": list(self.deferred_entry_ids),
            "unsupported_activation_entry_ids": list(self.unsupported_activation_entry_ids),
            "entries": [e if isinstance(e, dict) else e.to_dict() for e in self.entries],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldbookBinding:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            worldbook_binding_id=data.get("worldbook_binding_id", ""),
            session_id=data.get("session_id", ""),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", 0),
            source_hash=data.get("source_hash", ""),
            catalog_ref=data.get("catalog_ref", ""),
            bound_entry_ids=list(data.get("bound_entry_ids", [])),
            bound_chunk_ids=list(data.get("bound_chunk_ids", [])),
            disabled_entry_ids=list(data.get("disabled_entry_ids", [])),
            deferred_entry_ids=list(data.get("deferred_entry_ids", [])),
            unsupported_activation_entry_ids=list(data.get("unsupported_activation_entry_ids", [])),
            entries=data.get("entries", []),
            created_at=data.get("created_at", ""),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.worldbook_binding_id:
            errors.append("worldbook_binding_id is required")
        if not self.session_id:
            errors.append("session_id is required")
        if not self.logical_card_id:
            errors.append("logical_card_id is required")
        if self.card_version < 1:
            errors.append("card_version must be >= 1")
        if not self.source_hash:
            errors.append("source_hash is required")
        if self.schema_id != SCHEMA_ID:
            errors.append(f"schema_id must be {SCHEMA_ID}")
        return errors
