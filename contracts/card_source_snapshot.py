"""CardSourceSnapshot — immutable record of a card source file at import time.

schemaId: awp.rp.card-source-snapshot.v1

Captures the provenance and metadata of a source file before any
parsing or transformation. Used for idempotency checks and audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-source-snapshot.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardSourceSnapshot:
    """Immutable record of a card source file at import time."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    source_id: str = ""
    source_hash: str = ""
    source_filename: str = ""
    source_format: str = ""
    source_size_bytes: int = 0
    imported_at: str = ""
    spec: str = ""
    raw_payload_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "source_filename": self.source_filename,
            "source_format": self.source_format,
            "source_size_bytes": self.source_size_bytes,
            "imported_at": self.imported_at,
            "spec": self.spec,
            "raw_payload_ref": self.raw_payload_ref,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardSourceSnapshot:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            source_id=data.get("source_id", ""),
            source_hash=data.get("source_hash", ""),
            source_filename=data.get("source_filename", ""),
            source_format=data.get("source_format", ""),
            source_size_bytes=data.get("source_size_bytes", 0),
            imported_at=data.get("imported_at", ""),
            spec=data.get("spec", ""),
            raw_payload_ref=data.get("raw_payload_ref", ""),
        )
