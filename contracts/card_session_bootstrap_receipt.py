"""CardSessionBootstrapReceipt — receipt of a successful bootstrap.

schemaId: awp.rp.card-session-bootstrap-receipt.v1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-session-bootstrap-receipt.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardSessionBootstrapReceipt:
    """Receipt of a successful CardSession bootstrap."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    receipt_id: str = ""
    request_id: str = ""
    workflow_run_id: str = ""
    trace_id: str = ""
    session_id: str = ""
    logical_card_id: str = ""
    card_version: int = 0
    source_hash: str = ""
    greeting_id: str = ""
    opening_record_id: str = ""
    worldbook_binding_id: str = ""
    card_state_revision: int = 0
    commit_status: str = ""
    idempotency_status: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "workflow_run_id": self.workflow_run_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "source_hash": self.source_hash,
            "greeting_id": self.greeting_id,
            "opening_record_id": self.opening_record_id,
            "worldbook_binding_id": self.worldbook_binding_id,
            "card_state_revision": self.card_state_revision,
            "commit_status": self.commit_status,
            "idempotency_status": self.idempotency_status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardSessionBootstrapReceipt:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            receipt_id=data.get("receipt_id", ""),
            request_id=data.get("request_id", ""),
            workflow_run_id=data.get("workflow_run_id", ""),
            trace_id=data.get("trace_id", ""),
            session_id=data.get("session_id", ""),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", 0),
            source_hash=data.get("source_hash", ""),
            greeting_id=data.get("greeting_id", ""),
            opening_record_id=data.get("opening_record_id", ""),
            worldbook_binding_id=data.get("worldbook_binding_id", ""),
            card_state_revision=data.get("card_state_revision", 0),
            commit_status=data.get("commit_status", ""),
            idempotency_status=data.get("idempotency_status", ""),
            created_at=data.get("created_at", ""),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.receipt_id:
            errors.append("receipt_id is required")
        if not self.request_id:
            errors.append("request_id is required")
        if not self.session_id:
            errors.append("session_id is required")
        if not self.logical_card_id:
            errors.append("logical_card_id is required")
        if self.card_version < 1:
            errors.append("card_version must be >= 1")
        if not self.source_hash:
            errors.append("source_hash is required")
        if not self.greeting_id:
            errors.append("greeting_id is required")
        if not self.opening_record_id:
            errors.append("opening_record_id is required")
        if not self.worldbook_binding_id:
            errors.append("worldbook_binding_id is required")
        if self.schema_id != SCHEMA_ID:
            errors.append(f"schema_id must be {SCHEMA_ID}")
        return errors
