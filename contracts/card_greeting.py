"""CardGreeting — a single greeting message from a card.

schemaId: awp.rp.card-greeting.v1

Frozen record of one greeting. Greeting content is stored by reference
(raw_content_ref) with a safe display variant (safe_display_content).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-greeting.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardGreeting:
    """A single greeting message from a card."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    greeting_id: str = ""
    index: int = 0
    label: str = ""
    raw_content_ref: str = ""
    safe_display_content: str = ""
    content_hash: str = ""
    is_default: bool = False
    source_path: str = ""
    quarantine_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "greeting_id": self.greeting_id,
            "index": self.index,
            "label": self.label,
            "raw_content_ref": self.raw_content_ref,
            "safe_display_content": self.safe_display_content,
            "content_hash": self.content_hash,
            "is_default": self.is_default,
            "source_path": self.source_path,
            "quarantine_refs": list(self.quarantine_refs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardGreeting:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            greeting_id=data.get("greeting_id", ""),
            index=data.get("index", 0),
            label=data.get("label", ""),
            raw_content_ref=data.get("raw_content_ref", ""),
            safe_display_content=data.get("safe_display_content", ""),
            content_hash=data.get("content_hash", ""),
            is_default=data.get("is_default", False),
            source_path=data.get("source_path", ""),
            quarantine_refs=list(data.get("quarantine_refs", [])),
        )
