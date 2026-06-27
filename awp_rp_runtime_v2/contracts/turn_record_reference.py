"""TurnRecordReference — lightweight reference to an accepted TurnRecord.

schemaId: awp.rp.turn-record-reference.v1

A compact, serializable view of a TurnRecord used inside memory contexts and
recall diagnostics without dragging the full record body around.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .turn_record import TurnRecord

SCHEMA_ID = "awp.rp.turn-record-reference.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TurnRecordReference:
    """Compact reference to an accepted turn."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    turn_id: str = ""
    turn_index: int = 0
    card_id: str = ""
    session_id: str = ""
    accepted_at: str = ""
    base_card_state_revision: int = 0
    result_card_state_revision: int = 0
    trace_id: str = ""
    mode: str = "normal"
    player_input: str = ""
    writer_output: str = ""

    @classmethod
    def from_turn_record(cls, record: TurnRecord) -> TurnRecordReference:
        return cls(
            turn_id=record.turn_id,
            turn_index=record.turn_index,
            card_id=record.card_id,
            session_id=record.session_id,
            accepted_at=record.accepted_at,
            base_card_state_revision=record.base_card_state_revision,
            result_card_state_revision=record.result_card_state_revision,
            trace_id=record.trace_id,
            mode=record.mode.value if hasattr(record.mode, "value") else str(record.mode),
            player_input=record.player_input,
            writer_output=record.writer_output,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "turn_id": self.turn_id,
            "turn_index": self.turn_index,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "accepted_at": self.accepted_at,
            "base_card_state_revision": self.base_card_state_revision,
            "result_card_state_revision": self.result_card_state_revision,
            "trace_id": self.trace_id,
            "mode": self.mode,
            "player_input": self.player_input,
            "writer_output": self.writer_output,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TurnRecordReference:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            turn_id=data.get("turn_id", ""),
            turn_index=data.get("turn_index", 0),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            accepted_at=data.get("accepted_at", ""),
            base_card_state_revision=data.get("base_card_state_revision", 0),
            result_card_state_revision=data.get("result_card_state_revision", 0),
            trace_id=data.get("trace_id", ""),
            mode=data.get("mode", "normal"),
            player_input=data.get("player_input", ""),
            writer_output=data.get("writer_output", ""),
        )
