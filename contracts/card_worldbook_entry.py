"""CardWorldbookEntry — a single worldbook entry from a card.

schemaId: awp.rp.card-worldbook-entry.v1

Frozen record of one worldbook entry. Entries may be chunked for
retrieval; has_chunks indicates whether chunk children exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-worldbook-entry.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardWorldbookEntry:
    """A single worldbook entry from a card."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    entry_id: str = ""
    source_uid: int = -1
    title: str = ""
    content: str = ""
    keys: list[str] = field(default_factory=list)
    secondary_keys: list[str] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    constant: bool = False
    selective: bool = False
    activation_raw: str = ""
    source_order: int = -1
    source_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    quarantine_refs: list[str] = field(default_factory=list)
    has_chunks: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "entry_id": self.entry_id,
            "source_uid": self.source_uid,
            "title": self.title,
            "content": self.content,
            "keys": list(self.keys),
            "secondary_keys": list(self.secondary_keys),
            "priority": self.priority,
            "enabled": self.enabled,
            "constant": self.constant,
            "selective": self.selective,
            "activation_raw": self.activation_raw,
            "source_order": self.source_order,
            "source_path": self.source_path,
            "metadata": dict(self.metadata),
            "quarantine_refs": list(self.quarantine_refs),
            "has_chunks": self.has_chunks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardWorldbookEntry:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            entry_id=data.get("entry_id", ""),
            source_uid=data.get("source_uid", -1),
            title=data.get("title", ""),
            content=data.get("content", ""),
            keys=list(data.get("keys", [])),
            secondary_keys=list(data.get("secondary_keys", [])),
            priority=data.get("priority", 0),
            enabled=data.get("enabled", True),
            constant=data.get("constant", False),
            selective=data.get("selective", False),
            activation_raw=data.get("activation_raw", ""),
            source_order=data.get("source_order", -1),
            source_path=data.get("source_path", ""),
            metadata=data.get("metadata", {}),
            quarantine_refs=list(data.get("quarantine_refs", [])),
            has_chunks=data.get("has_chunks", False),
        )
