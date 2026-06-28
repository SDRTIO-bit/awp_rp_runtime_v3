"""TurnResultProjection — history-safe projection of a completed turn.

schemaId: awp.rp.turn-result-projection.v1

Contains only machine-readable, privacy-safe metadata about a turn result.
Never contains full accepted text, player input, card content, prompts, or keys.
Designed for ComfyUI /history output via AWPV2TurnResultProbe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.turn-result-projection.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TurnResultProjection:
    """History-safe projection of a completed RP turn.

    Contains only identifiers, statuses, hashes, and lengths.
    Never contains full text, prompts, card content, or secrets.
    """

    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Run identity
    workflow_run_id: str = ""
    trace_id: str = ""
    prompt_id: str = ""

    # Turn identity
    turn_id: str = ""
    attempt_id: str = ""
    session_id: str = ""
    turn_index: int = 0
    turn_kind: str = ""  # "first" or "continuation"

    # Quality & receipt
    quality_status: str = ""  # "accepted", "rejected", "revise"
    receipt_status: str = ""  # "committed", "failed", "noop"

    # TurnRecord binding
    turn_record_id: str = ""
    accepted_text_hash: str = ""  # SHA-256 of accepted text
    accepted_text_length: int = 0  # Character count only

    # State revision binding
    card_state_revision_before: int = 0
    card_state_revision_after: int = 0

    # Worldbook
    worldbook_activated_entry_ids: list[str] = field(default_factory=list)
    worldbook_deferred_entry_ids: list[str] = field(default_factory=list)

    # Memory
    memory_disposition: str = ""  # "noop", "curated", "failed"

    # Provider usage (no API keys)
    provider_usage_summary: dict[str, Any] = field(default_factory=dict)

    # P1: Safe state/memory/delegation effects projection
    # (Never contains full CardState, card text, or prompt content)
    state_effects: dict[str, Any] = field(default_factory=dict)
    memory_effects: dict[str, Any] = field(default_factory=dict)
    delegation_effects: dict[str, Any] = field(default_factory=dict)

    # Diagnostics
    diagnostic_status: str = ""  # "success", "failure", "quality_rejected"
    failure_code: str = ""
    failure_message: str = ""  # Sanitized, no secrets

    # Idempotency
    idempotency_status: str = ""  # "fresh", "replayed", "conflict", "recovery_required"

    # Timestamps
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "workflow_run_id": self.workflow_run_id,
            "trace_id": self.trace_id,
            "prompt_id": self.prompt_id,
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "session_id": self.session_id,
            "turn_index": self.turn_index,
            "turn_kind": self.turn_kind,
            "quality_status": self.quality_status,
            "receipt_status": self.receipt_status,
            "turn_record_id": self.turn_record_id,
            "accepted_text_hash": self.accepted_text_hash,
            "accepted_text_length": self.accepted_text_length,
            "card_state_revision_before": self.card_state_revision_before,
            "card_state_revision_after": self.card_state_revision_after,
            "worldbook_activated_entry_ids": list(self.worldbook_activated_entry_ids),
            "worldbook_deferred_entry_ids": list(self.worldbook_deferred_entry_ids),
            "memory_disposition": self.memory_disposition,
            "provider_usage_summary": dict(self.provider_usage_summary),
            "state_effects": dict(self.state_effects),
            "memory_effects": dict(self.memory_effects),
            "delegation_effects": dict(self.delegation_effects),
            "diagnostic_status": self.diagnostic_status,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
            "idempotency_status": self.idempotency_status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TurnResultProjection:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            workflow_run_id=data.get("workflow_run_id", ""),
            trace_id=data.get("trace_id", ""),
            prompt_id=data.get("prompt_id", ""),
            turn_id=data.get("turn_id", ""),
            attempt_id=data.get("attempt_id", ""),
            session_id=data.get("session_id", ""),
            turn_index=data.get("turn_index", 0),
            turn_kind=data.get("turn_kind", ""),
            quality_status=data.get("quality_status", ""),
            receipt_status=data.get("receipt_status", ""),
            turn_record_id=data.get("turn_record_id", ""),
            accepted_text_hash=data.get("accepted_text_hash", ""),
            accepted_text_length=data.get("accepted_text_length", 0),
            card_state_revision_before=data.get("card_state_revision_before", 0),
            card_state_revision_after=data.get("card_state_revision_after", 0),
            worldbook_activated_entry_ids=data.get("worldbook_activated_entry_ids", []),
            worldbook_deferred_entry_ids=data.get("worldbook_deferred_entry_ids", []),
            memory_disposition=data.get("memory_disposition", ""),
            provider_usage_summary=data.get("provider_usage_summary", {}),
            state_effects=data.get("state_effects", {}),
            memory_effects=data.get("memory_effects", {}),
            delegation_effects=data.get("delegation_effects", {}),
            diagnostic_status=data.get("diagnostic_status", ""),
            failure_code=data.get("failure_code", ""),
            failure_message=data.get("failure_message", ""),
            idempotency_status=data.get("idempotency_status", ""),
            created_at=data.get("created_at", ""),
        )
