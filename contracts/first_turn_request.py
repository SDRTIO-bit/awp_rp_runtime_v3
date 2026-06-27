"""First Turn Request -- validates Session readiness before RP turn execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.first-turn-request.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FirstTurnRequest:
    """Request to execute the first formal RP turn on a bootstrapped Session.

    Identity fields mirror WorkflowRunContext quartet + card identity.
    Player input is the raw text from the user.
    """

    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    request_id: str = ""
    workflow_run_id: str = ""
    trace_id: str = ""
    turn_id: str = ""
    attempt_id: str = ""
    session_id: str = ""
    player_input: str = ""
    expected_logical_card_id: str = ""
    expected_card_version: int = 0
    expected_source_hash: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "workflow_run_id": self.workflow_run_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "session_id": self.session_id,
            "player_input": self.player_input,
            "expected_logical_card_id": self.expected_logical_card_id,
            "expected_card_version": self.expected_card_version,
            "expected_source_hash": self.expected_source_hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FirstTurnRequest:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            request_id=data.get("request_id", ""),
            workflow_run_id=data.get("workflow_run_id", ""),
            trace_id=data.get("trace_id", ""),
            turn_id=data.get("turn_id", ""),
            attempt_id=data.get("attempt_id", ""),
            session_id=data.get("session_id", ""),
            player_input=data.get("player_input", ""),
            expected_logical_card_id=data.get("expected_logical_card_id", ""),
            expected_card_version=data.get("expected_card_version", 0),
            expected_source_hash=data.get("expected_source_hash", ""),
            created_at=data.get("created_at", ""),
        )

    def validate(self) -> list[str]:
        """Return list of validation errors; empty = valid."""
        errors: list[str] = []
        if self.schema_id != SCHEMA_ID:
            errors.append(f"schema_id mismatch: {self.schema_id}")
        if not self.request_id:
            errors.append("request_id is required")
        if not self.session_id:
            errors.append("session_id is required")
        if not self.player_input.strip():
            errors.append("player_input is required")
        if not self.expected_logical_card_id:
            errors.append("expected_logical_card_id is required")
        if self.expected_card_version < 1:
            errors.append("expected_card_version must be >= 1")
        if not self.expected_source_hash:
            errors.append("expected_source_hash is required")
        if not self.turn_id:
            errors.append("turn_id is required")
        if not self.attempt_id:
            errors.append("attempt_id is required")
        return errors
