"""CardImportRequest — request to import a card source file.

schemaId: awp.rp.card-import-request.v1

Submitted to the import pipeline. Each request produces a single
CardImportResult and CardImportReport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-import-request.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardImportRequest:
    """Request to import a card source file."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    request_id: str = ""
    source_path: str = ""
    source_filename: str = ""
    existing_logical_card_id: str = ""  # if set, import as new version of this card
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "source_path": self.source_path,
            "source_filename": self.source_filename,
            "existing_logical_card_id": self.existing_logical_card_id,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardImportRequest:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            request_id=data.get("request_id", ""),
            source_path=data.get("source_path", ""),
            source_filename=data.get("source_filename", ""),
            existing_logical_card_id=data.get("existing_logical_card_id", ""),
            trace_id=data.get("trace_id", ""),
        )
