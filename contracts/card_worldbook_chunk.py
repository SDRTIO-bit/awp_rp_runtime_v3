"""CardWorldbookChunk — a chunk of a worldbook entry for retrieval.

schemaId: awp.rp.card-worldbook-chunk.v1

Large worldbook entries are split into chunks. Each chunk tracks its
parent, ordinal position, and content boundaries for provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-worldbook-chunk.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardWorldbookChunk:
    """A chunk of a worldbook entry for retrieval."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    chunk_id: str = ""
    parent_entry_id: str = ""
    ordinal: int = 0
    content: str = ""
    start_offset: int = 0
    end_offset: int = 0
    keywords: list[str] = field(default_factory=list)
    entity_refs: list[str] = field(default_factory=list)
    source_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "chunk_id": self.chunk_id,
            "parent_entry_id": self.parent_entry_id,
            "ordinal": self.ordinal,
            "content": self.content,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "keywords": list(self.keywords),
            "entity_refs": list(self.entity_refs),
            "source_hash": self.source_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardWorldbookChunk:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            chunk_id=data.get("chunk_id", ""),
            parent_entry_id=data.get("parent_entry_id", ""),
            ordinal=data.get("ordinal", 0),
            content=data.get("content", ""),
            start_offset=data.get("start_offset", 0),
            end_offset=data.get("end_offset", 0),
            keywords=list(data.get("keywords", [])),
            entity_refs=list(data.get("entity_refs", [])),
            source_hash=data.get("source_hash", ""),
        )
