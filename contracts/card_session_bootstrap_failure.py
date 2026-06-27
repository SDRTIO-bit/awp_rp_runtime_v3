"""CardSessionBootstrapFailure — failure record for a failed bootstrap.

schemaId: awp.rp.card-session-bootstrap-failure.v1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-session-bootstrap-failure.v1"
SCHEMA_VERSION = 1


class BootstrapFailureCode:
    CARD_NOT_READY = "card_not_ready"
    CARD_NOT_FOUND = "card_not_found"
    GREETING_NOT_FOUND = "greeting_not_found"
    SOURCE_HASH_MISMATCH = "source_hash_mismatch"
    SESSION_VERSION_CONFLICT = "session_version_conFLICT"
    IDEMPOTENCY_RETRY = "idempotency_retry"
    VALIDATION_ERROR = "validation_error"
    PARTIAL_FAILURE = "partial_failure"


@dataclass(frozen=True)
class CardSessionBootstrapFailure:
    """Records why a bootstrap failed."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    failure_id: str = ""
    request_id: str = ""
    session_id: str = ""
    logical_card_id: str = ""
    card_version: int = 0
    failure_code: str = ""
    failure_message: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "failure_id": self.failure_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardSessionBootstrapFailure:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            failure_id=data.get("failure_id", ""),
            request_id=data.get("request_id", ""),
            session_id=data.get("session_id", ""),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", 0),
            failure_code=data.get("failure_code", ""),
            failure_message=data.get("failure_message", ""),
            created_at=data.get("created_at", ""),
        )
