"""CardSessionBinding — binds a Session to a specific CardDefinition version.

schemaId: awp.rp.card-session-binding.v1

Once a Session is ready, logicalCardId + cardVersion + sourceHash
are immutable. A new card version never changes an existing binding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-session-binding.v1"
SCHEMA_VERSION = 1


class CardSessionBindingStatus:
    PENDING = "pending"
    COMMITTING = "committing"
    READY = "ready"
    FAILED = "failed"


@dataclass
class CardSessionBinding:
    """Binds a Session to a specific CardDefinition version."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    session_id: str = ""
    logical_card_id: str = ""
    card_version: int = 0
    source_hash: str = ""
    card_definition_ref: str = ""
    selected_greeting_id: str = ""
    worldbook_binding_id: str = ""
    opening_record_id: str = ""
    created_at: str = ""
    status: str = CardSessionBindingStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "source_hash": self.source_hash,
            "card_definition_ref": self.card_definition_ref,
            "selected_greeting_id": self.selected_greeting_id,
            "worldbook_binding_id": self.worldbook_binding_id,
            "opening_record_id": self.opening_record_id,
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardSessionBinding:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            session_id=data.get("session_id", ""),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", 0),
            source_hash=data.get("source_hash", ""),
            card_definition_ref=data.get("card_definition_ref", ""),
            selected_greeting_id=data.get("selected_greeting_id", ""),
            worldbook_binding_id=data.get("worldbook_binding_id", ""),
            opening_record_id=data.get("opening_record_id", ""),
            created_at=data.get("created_at", ""),
            status=data.get("status", CardSessionBindingStatus.PENDING),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.session_id:
            errors.append("session_id is required")
        if not self.logical_card_id:
            errors.append("logical_card_id is required")
        if self.card_version < 1:
            errors.append("card_version must be >= 1")
        if not self.source_hash:
            errors.append("source_hash is required")
        if not self.selected_greeting_id:
            errors.append("selected_greeting_id is required")
        if not self.opening_record_id:
            errors.append("opening_record_id is required")
        if not self.worldbook_binding_id:
            errors.append("worldbook_binding_id is required")
        if self.schema_id != SCHEMA_ID:
            errors.append(f"schema_id must be {SCHEMA_ID}")
        return errors
