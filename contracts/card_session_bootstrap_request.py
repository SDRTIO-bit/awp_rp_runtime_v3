"""CardSessionBootstrapRequest — request to bootstrap a new RP session from a ready card.

schemaId: awp.rp.card-session-bootstrap-request.v1

Contains all explicit parameters needed to start a session.
No defaults, no inference, no script execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_ID = "awp.rp.card-session-bootstrap-request.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardSessionBootstrapRequest:
    """Explicit request to bootstrap a CardSession from a ready CardDefinition."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    request_id: str = ""
    workflow_run_id: str = ""
    trace_id: str = ""
    session_id: str = ""
    logical_card_id: str = ""
    card_version: int = 0
    greeting_id: str = ""
    expected_source_hash: str = ""
    initial_state_seed: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "workflow_run_id": self.workflow_run_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "greeting_id": self.greeting_id,
            "expected_source_hash": self.expected_source_hash,
            "initial_state_seed": dict(self.initial_state_seed),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardSessionBootstrapRequest:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            request_id=data.get("request_id", ""),
            workflow_run_id=data.get("workflow_run_id", ""),
            trace_id=data.get("trace_id", ""),
            session_id=data.get("session_id", ""),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", 0),
            greeting_id=data.get("greeting_id", ""),
            expected_source_hash=data.get("expected_source_hash", ""),
            initial_state_seed=data.get("initial_state_seed", {}),
            created_at=data.get("created_at", ""),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.request_id:
            errors.append("request_id is required")
        if not self.session_id:
            errors.append("session_id is required")
        if not self.logical_card_id:
            errors.append("logical_card_id is required")
        if self.card_version < 1:
            errors.append("card_version must be >= 1")
        if not self.greeting_id:
            errors.append("greeting_id is required")
        if not self.expected_source_hash:
            errors.append("expected_source_hash is required")
        if self.schema_id != SCHEMA_ID:
            errors.append(f"schema_id must be {SCHEMA_ID}")
        # initial_state_seed validation: must be a dict if present
        if self.initial_state_seed and not isinstance(self.initial_state_seed, dict):
            errors.append("initial_state_seed must be a dict")
        return errors
