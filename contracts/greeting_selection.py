"""GreetingSelection — validated greeting selection for bootstrap.

schemaId: awp.rp.greeting-selection.v1

Records which greeting was selected and validates it belongs to
the exact logicalCardId + cardVersion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.greeting-selection.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GreetingSelection:
    """Validated greeting selection for a bootstrap request."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    greeting_id: str = ""
    logical_card_id: str = ""
    card_version: int = 0
    safe_display_content: str = ""
    content_hash: str = ""
    is_default: bool = False
    index: int = 0
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "greeting_id": self.greeting_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "safe_display_content": self.safe_display_content,
            "content_hash": self.content_hash,
            "is_default": self.is_default,
            "index": self.index,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GreetingSelection:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            greeting_id=data.get("greeting_id", ""),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", 0),
            safe_display_content=data.get("safe_display_content", ""),
            content_hash=data.get("content_hash", ""),
            is_default=data.get("is_default", False),
            index=data.get("index", 0),
            label=data.get("label", ""),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.greeting_id:
            errors.append("greeting_id is required")
        if not self.logical_card_id:
            errors.append("logical_card_id is required")
        if self.card_version < 1:
            errors.append("card_version must be >= 1")
        if not self.safe_display_content:
            errors.append("safe_display_content is required")
        if not self.content_hash:
            errors.append("content_hash is required")
        if self.schema_id != SCHEMA_ID:
            errors.append(f"schema_id must be {SCHEMA_ID}")
        return errors
