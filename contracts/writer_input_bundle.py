"""WriterInputBundle — the only formal input for future Writer.

schemaId: awp.rp.writer-input-bundle.v1

Writer can ONLY read from this bundle. Not from raw suggestions, not from stores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.writer-input-bundle.v1"
SCHEMA_VERSION = 1


@dataclass
class WriterInputBundle:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    bundle_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    brief_id: str = ""
    merge_id: str = ""
    card_id: str = ""
    session_id: str = ""
    base_card_state_revision: int = 0

    # References (not inline copies)
    round_snapshot_ref: str = ""
    turn_brief_ref: str = ""
    suggestion_merge_ref: str = ""

    # What Writer must do / must not do
    writer_constraints: list[str] = field(default_factory=list)
    accepted_guidance: list[str] = field(default_factory=list)

    # Hints for future state/memory proposals
    state_proposal_hints: list[dict[str, Any]] = field(default_factory=list)
    memory_proposal_hints: list[dict[str, Any]] = field(default_factory=list)

    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "bundle_id": self.bundle_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "brief_id": self.brief_id,
            "merge_id": self.merge_id, "card_id": self.card_id,
            "session_id": self.session_id,
            "base_card_state_revision": self.base_card_state_revision,
            "round_snapshot_ref": self.round_snapshot_ref,
            "turn_brief_ref": self.turn_brief_ref,
            "suggestion_merge_ref": self.suggestion_merge_ref,
            "writer_constraints": self.writer_constraints,
            "accepted_guidance": self.accepted_guidance,
            "state_proposal_hints": self.state_proposal_hints,
            "memory_proposal_hints": self.memory_proposal_hints,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WriterInputBundle:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            bundle_id=data.get("bundle_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            brief_id=data.get("brief_id", ""),
            merge_id=data.get("merge_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            base_card_state_revision=data.get("base_card_state_revision", 0),
            round_snapshot_ref=data.get("round_snapshot_ref", ""),
            turn_brief_ref=data.get("turn_brief_ref", ""),
            suggestion_merge_ref=data.get("suggestion_merge_ref", ""),
            writer_constraints=data.get("writer_constraints", []),
            accepted_guidance=data.get("accepted_guidance", []),
            state_proposal_hints=data.get("state_proposal_hints", []),
            memory_proposal_hints=data.get("memory_proposal_hints", []),
            created_at=data.get("created_at", ""),
        )
