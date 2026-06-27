"""CardImportResult — final result of a card import request.

schemaId: awp.rp.card-import-result.v1

Frozen record returned to the caller after the import pipeline
completes. Encapsulates success, failure, or intermediate status
such as approval_required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-import-result.v1"
SCHEMA_VERSION = 1


class ImportResultStatus:
    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    VALIDATION_FAILED = "validation_failed"
    SECURITY_REJECTED = "security_rejected"
    APPROVAL_REQUIRED = "approval_required"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class CardImportResult:
    """Final result of a card import request."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    result_id: str = ""
    request_id: str = ""
    status: str = ImportResultStatus.INTERNAL_ERROR
    logical_card_id: str = ""
    card_version: int = 0
    source_id: str = ""
    source_hash: str = ""
    name: str = ""
    report_ref: str = ""
    error_message: str = ""
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "request_id": self.request_id,
            "status": self.status,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "name": self.name,
            "report_ref": self.report_ref,
            "error_message": self.error_message,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardImportResult:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            result_id=data.get("result_id", ""),
            request_id=data.get("request_id", ""),
            status=data.get("status", ImportResultStatus.INTERNAL_ERROR),
            logical_card_id=data.get("logical_card_id", "") or data.get("card_id", ""),
            card_version=data.get("card_version", 0),
            source_id=data.get("source_id", ""),
            source_hash=data.get("source_hash", ""),
            name=data.get("name", ""),
            report_ref=data.get("report_ref", ""),
            error_message=data.get("error_message", ""),
            trace_id=data.get("trace_id", ""),
        )
