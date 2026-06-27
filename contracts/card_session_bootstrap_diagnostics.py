"""CardSessionBootstrapDiagnostics — diagnostic summary for a bootstrap.

schemaId: awp.rp.card-session-bootstrap-diagnostics.v1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-session-bootstrap-diagnostics.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardSessionBootstrapDiagnostics:
    """Diagnostic summary for a CardSession bootstrap."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    logical_card_id: str = ""
    card_version: int = 0
    source_hash: str = ""
    session_id: str = ""
    request_id: str = ""
    selected_greeting_id: str = ""
    opening_record_id: str = ""
    worldbook_binding_id: str = ""
    card_state_revision_before: int = 0
    card_state_revision_after: int = 0
    bound_entry_count: int = 0
    disabled_entry_count: int = 0
    deferred_entry_count: int = 0
    commit_status: str = ""
    idempotency_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "source_hash": self.source_hash,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "selected_greeting_id": self.selected_greeting_id,
            "opening_record_id": self.opening_record_id,
            "worldbook_binding_id": self.worldbook_binding_id,
            "card_state_revision_before": self.card_state_revision_before,
            "card_state_revision_after": self.card_state_revision_after,
            "bound_entry_count": self.bound_entry_count,
            "disabled_entry_count": self.disabled_entry_count,
            "deferred_entry_count": self.deferred_entry_count,
            "commit_status": self.commit_status,
            "idempotency_status": self.idempotency_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardSessionBootstrapDiagnostics:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", 0),
            source_hash=data.get("source_hash", ""),
            session_id=data.get("session_id", ""),
            request_id=data.get("request_id", ""),
            selected_greeting_id=data.get("selected_greeting_id", ""),
            opening_record_id=data.get("opening_record_id", ""),
            worldbook_binding_id=data.get("worldbook_binding_id", ""),
            card_state_revision_before=data.get("card_state_revision_before", 0),
            card_state_revision_after=data.get("card_state_revision_after", 0),
            bound_entry_count=data.get("bound_entry_count", 0),
            disabled_entry_count=data.get("disabled_entry_count", 0),
            deferred_entry_count=data.get("deferred_entry_count", 0),
            commit_status=data.get("commit_status", ""),
            idempotency_status=data.get("idempotency_status", ""),
        )
