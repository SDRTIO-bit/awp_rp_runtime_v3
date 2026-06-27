"""CardImportReport — mutable report produced by the card import pipeline.

schemaId: awp.rp.card-import-report.v1

Aggregates all findings from a single import run: counts of greetings,
worldbook entries/chunks, quarantines, structure hints, and issues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .card_import_issue import CardImportIssue

SCHEMA_ID = "awp.rp.card-import-report.v1"
SCHEMA_VERSION = 1


@dataclass
class CardImportReport:
    """Mutable report produced by the card import pipeline."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    report_id: str = ""
    request_id: str = ""
    source_id: str = ""
    card_id: str = ""
    card_version: int = 0
    trace_id: str = ""
    status: str = ""
    name: str = ""
    spec: str = ""
    greeting_count: int = 0
    worldbook_entry_count: int = 0
    worldbook_chunk_count: int = 0
    quarantine_count: int = 0
    structure_hint_count: int = 0
    issues: list[CardImportIssue] = field(default_factory=list)
    quarantine_summary: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "request_id": self.request_id,
            "source_id": self.source_id,
            "card_id": self.card_id,
            "card_version": self.card_version,
            "trace_id": self.trace_id,
            "status": self.status,
            "name": self.name,
            "spec": self.spec,
            "greeting_count": self.greeting_count,
            "worldbook_entry_count": self.worldbook_entry_count,
            "worldbook_chunk_count": self.worldbook_chunk_count,
            "quarantine_count": self.quarantine_count,
            "structure_hint_count": self.structure_hint_count,
            "issues": [i.to_dict() for i in self.issues],
            "quarantine_summary": dict(self.quarantine_summary),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardImportReport:
        issues = [
            CardImportIssue.from_dict(i) for i in data.get("issues", [])
        ]
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            report_id=data.get("report_id", ""),
            request_id=data.get("request_id", ""),
            source_id=data.get("source_id", ""),
            card_id=data.get("card_id", ""),
            card_version=data.get("card_version", 0),
            trace_id=data.get("trace_id", ""),
            status=data.get("status", ""),
            name=data.get("name", ""),
            spec=data.get("spec", ""),
            greeting_count=data.get("greeting_count", 0),
            worldbook_entry_count=data.get("worldbook_entry_count", 0),
            worldbook_chunk_count=data.get("worldbook_chunk_count", 0),
            quarantine_count=data.get("quarantine_count", 0),
            structure_hint_count=data.get("structure_hint_count", 0),
            issues=issues,
            quarantine_summary=data.get("quarantine_summary", {}),
            created_at=data.get("created_at", ""),
        )
