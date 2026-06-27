"""AWPV2RoundSnapshot — build frozen RoundSnapshot.

Output: ROUND_SNAPSHOT (JSON)
"""

from __future__ import annotations

from typing import Any


class AWPV2RoundSnapshot:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "card_state": ("CARD_STATE",),
                "player_input": ("STRING",),
            },
            "optional": {
                "turn_records": ("TURN_RECORDS",),
                "active_memories": ("ACTIVE_MEMORIES",),
                "rag_recall": ("RAG_RECALL",),
                "worldbook_entries": ("WORLDBOOK_ENTRIES",),
            },
        }

    RETURN_TYPES = ("ROUND_SNAPSHOT",)
    RETURN_NAMES = ("round_snapshot",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        card_state: dict[str, Any],
        player_input: str,
        turn_records: list | None = None,
        active_memories: list | None = None,
        rag_recall: list | None = None,
        worldbook_entries: list | None = None,
    ) -> tuple[dict[str, Any]]:
        import uuid
        from datetime import datetime, timezone
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.card_state import CardState
        from ..contracts.turn_record import TurnRecord

        state = CardState.from_dict(card_state)
        turns = [TurnRecord.from_dict(t) for t in (turn_records or [])]
        now = datetime.now(timezone.utc).isoformat()

        snapshot = RoundSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:12]}",
            trace_id=f"trace_{uuid.uuid4().hex[:12]}",
            card_id=state.card_id,
            session_id=state.session_id,
            base_card_state_revision=state.revision,
            card_state=state,
            player_input=player_input,
            recent_turn_records=turns,
            active_worldbook_entries=worldbook_entries or [],
            active_memories=active_memories or [],
            rag_recall=rag_recall or [],
            created_at=now,
        )
        return (snapshot.to_dict(),)
