"""OpeningRecord — the Greeting saved as an independent session opening.

schemaId: awp.rp.opening-record.v1

OpeningRecord is NOT a TurnRecord.
OpeningRecord is NOT an accepted Writer output.
OpeningRecord does NOT trigger D6.
OpeningRecord does NOT enter ActiveMemory or RagMemory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.opening-record.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class OpeningRecord:
    """The greeting saved as an independent session opening record."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    opening_record_id: str = ""
    session_id: str = ""
    logical_card_id: str = ""
    card_version: int = 0
    greeting_id: str = ""
    safe_display_content: str = ""
    source_greeting_ref: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "opening_record_id": self.opening_record_id,
            "session_id": self.session_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "greeting_id": self.greeting_id,
            "safe_display_content": self.safe_display_content,
            "source_greeting_ref": self.source_greeting_ref,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpeningRecord:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            opening_record_id=data.get("opening_record_id", ""),
            session_id=data.get("session_id", ""),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", 0),
            greeting_id=data.get("greeting_id", ""),
            safe_display_content=data.get("safe_display_content", ""),
            source_greeting_ref=data.get("source_greeting_ref", ""),
            created_at=data.get("created_at", ""),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.opening_record_id:
            errors.append("opening_record_id is required")
        if not self.session_id:
            errors.append("session_id is required")
        if not self.logical_card_id:
            errors.append("logical_card_id is required")
        if self.card_version < 1:
            errors.append("card_version must be >= 1")
        if not self.greeting_id:
            errors.append("greeting_id is required")
        if not self.safe_display_content:
            errors.append("safe_display_content is required")
        if self.schema_id != SCHEMA_ID:
            errors.append(f"schema_id must be {SCHEMA_ID}")
        return errors
