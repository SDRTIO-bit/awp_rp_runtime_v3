"""StateUpdateProposal — proposed state changes from accepted text.

schemaId: awp.rp.state-update-proposal.v1

This is a candidate patch. It must go through QualityGate and
CardStateCommitRuntime before any writes happen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.state-update-proposal.v1"
SCHEMA_VERSION = 1


class PatchOp(str, Enum):
    """Patch operation type."""
    SET_VARIABLE = "set_variable"
    INCREMENT_VARIABLE = "increment_variable"
    DECREMENT_VARIABLE = "decrement_variable"
    SET_EVENT_FLAG = "set_event_flag"
    CLEAR_EVENT_FLAG = "clear_event_flag"
    SET_SCENE = "set_scene"
    ADD_ACTIVE_STAGE = "add_active_stage"
    REMOVE_ACTIVE_STAGE = "remove_active_stage"


@dataclass(frozen=True)
class PatchOpEntry:
    """A single patch operation."""
    op: PatchOp
    path: str  # e.g. "variables.favorability" or "event_flags.quest_started"
    value: Any = None
    reason: str = ""


@dataclass
class StateUpdateProposal:
    """Proposed state changes from accepted text.

    This is a CANDIDATE patch. It must be validated and committed
    through CardStateCommitRuntime. No agent can write directly.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    turn_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # The patch operations
    operations: list[PatchOpEntry] = field(default_factory=list)

    # Metadata
    source: str = ""  # Where this proposal came from
    confidence: float = 0.5  # 0.0 - 1.0
    evidence: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.operations) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "turn_id": self.turn_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "operations": [
                {
                    "op": op.op.value,
                    "path": op.path,
                    "value": op.value,
                    "reason": op.reason,
                }
                for op in self.operations
            ],
            "source": self.source,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateUpdateProposal:
        operations = []
        for op_data in data.get("operations", []):
            operations.append(PatchOpEntry(
                op=PatchOp(op_data["op"]),
                path=op_data["path"],
                value=op_data.get("value"),
                reason=op_data.get("reason", ""),
            ))
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            turn_id=data.get("turn_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            operations=operations,
            source=data.get("source", ""),
            confidence=data.get("confidence", 0.5),
            evidence=data.get("evidence", []),
        )
