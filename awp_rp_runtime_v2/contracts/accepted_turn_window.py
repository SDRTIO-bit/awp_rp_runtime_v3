"""AcceptedTurnWindow — L1 window of the last <=5 fully-accepted TurnRecords.

schemaId: awp.rp.accepted-turn-window.v1

This is NOT a chat summary and NOT a token-truncated history fragment.
Each turn retains full player input and full final writer output.
The 5th turn is never silently truncated into a summary.

Only `accepted` TurnRecords are admitted. Drafts, rejected text, failed retries,
intermediate revisions, raw tool JSON and agent CoT never enter this window.

When the context budget is insufficient, the window is reduced LAST — low-priority
RAG, worldbook expansions, tool results and optional subagent evidence are cut
first. The selected full TurnRecords are never truncated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .turn_record import TurnRecord
from .turn_record_reference import TurnRecordReference

SCHEMA_ID = "awp.rp.accepted-turn-window.v1"
SCHEMA_VERSION = 1

DEFAULT_WINDOW_SIZE = 5


def select_accepted_window(
    turns: list[TurnRecord],
    limit: int = DEFAULT_WINDOW_SIZE,
) -> list[TurnRecord]:
    """Select up to `limit` accepted turns, most-recent first, stable sort.

    Stable ordering: by turn_index DESC, then accepted_at DESC.
    Only fully-accepted turns are eligible (the TurnRecord store only persists
    accepted turns, so this is a defensive filter).
    """
    eligible = [t for t in turns if _is_accepted(t)]
    eligible.sort(
        key=lambda t: (t.turn_index, t.accepted_at),
        reverse=True,
    )
    return eligible[:limit]


def _is_accepted(turn: TurnRecord) -> bool:
    """A turn is eligible for L1 if it has a turn_id.

    The TurnRecord store only persists accepted turns (drafts, rejected text,
    failed retries, intermediate revisions and raw tool JSON are never stored
    as TurnRecords), so any stored record is accepted by construction. We only
    defend against empty/placeholder entries.
    """
    return bool(turn.turn_id)


@dataclass(frozen=True)
class AcceptedTurnWindow:
    """L1 window of the last <=5 fully-accepted TurnRecords."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    card_id: str = ""
    session_id: str = ""
    snapshot_id: str = ""  # the RoundSnapshot this window was built for
    window_size: int = DEFAULT_WINDOW_SIZE

    # Full TurnRecords (most-recent first), never truncated
    turns: list[TurnRecord] = field(default_factory=list)
    # Compact references for diagnostics
    references: list[TurnRecordReference] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "snapshot_id": self.snapshot_id,
            "window_size": self.window_size,
            "turns": [t.to_dict() for t in self.turns],
            "references": [r.to_dict() for r in self.references],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcceptedTurnWindow:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            window_size=data.get("window_size", DEFAULT_WINDOW_SIZE),
            turns=[TurnRecord.from_dict(t) for t in data.get("turns", [])],
            references=[TurnRecordReference.from_dict(r) for r in data.get("references", [])],
        )

    @classmethod
    def build(
        cls,
        card_id: str,
        session_id: str,
        turns: list[TurnRecord],
        snapshot_id: str = "",
        window_size: int = DEFAULT_WINDOW_SIZE,
    ) -> AcceptedTurnWindow:
        selected = select_accepted_window(turns, limit=window_size)
        refs = [TurnRecordReference.from_turn_record(t) for t in selected]
        return cls(
            card_id=card_id,
            session_id=session_id,
            snapshot_id=snapshot_id,
            window_size=window_size,
            turns=selected,
            references=refs,
        )
