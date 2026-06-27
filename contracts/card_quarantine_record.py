"""CardQuarantineRecord — a quarantined or sanitized content fragment.

schemaId: awp.rp.card-quarantine-record.v1

Frozen record of a content fragment that was quarantined during import
due to executable or security-sensitive patterns. Each record captures
the kind, evidence, and the action taken.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-quarantine-record.v1"
SCHEMA_VERSION = 1


class QuarantineKind:
    JAVASCRIPT = "javascript"
    EVAL = "eval"
    FUNCTION_CONSTRUCTOR = "function_constructor"
    EJS = "ejs"
    GETVAR = "getvar"
    SETVAR = "setvar"
    ADDVAR = "addvar"
    SCRIPT_TAG = "script_tag"
    IFRAME = "iframe"
    FETCH = "fetch"
    IMPORT_URL = "import_url"
    REGEX_SCRIPT = "regex_script"
    VARIABLE_EXEC = "variable_exec"
    UNKNOWN_EXECUTABLE = "unknown_executable"


class QuarantineAction:
    QUARANTINED = "quarantined"
    SANITIZED_FOR_DISPLAY = "sanitized_for_display"
    UNSUPPORTED = "unsupported"
    REQUIRES_MANUAL_MAPPING = "requires_manual_mapping"


class QuarantineSeverity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class CardQuarantineRecord:
    """A quarantined or sanitized content fragment."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    record_id: str = ""
    kind: str = QuarantineKind.UNKNOWN_EXECUTABLE
    source_path: str = ""
    severity: str = QuarantineSeverity.LOW
    evidence_preview: str = ""
    raw_content_ref: str = ""
    action: str = QuarantineAction.QUARANTINED
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "kind": self.kind,
            "source_path": self.source_path,
            "severity": self.severity,
            "evidence_preview": self.evidence_preview,
            "raw_content_ref": self.raw_content_ref,
            "action": self.action,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardQuarantineRecord:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            record_id=data.get("record_id", ""),
            kind=data.get("kind", QuarantineKind.UNKNOWN_EXECUTABLE),
            source_path=data.get("source_path", ""),
            severity=data.get("severity", QuarantineSeverity.LOW),
            evidence_preview=data.get("evidence_preview", ""),
            raw_content_ref=data.get("raw_content_ref", ""),
            action=data.get("action", QuarantineAction.QUARANTINED),
            reason=data.get("reason", ""),
        )
