"""TurnRecordCommitRuntime — commits accepted turn records.

Only accepted text (passed quality gate) becomes a TurnRecord.
Gate must pass. Binds base and result revision.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.turn_record import TurnRecord, TurnMode
from ..contracts.quality_decision import (
    QualityDecision, assert_side_effects_allowed, SideEffectBlockedError,
)
from ..contracts.round_snapshot import RoundSnapshot
from ..storage.interfaces import TurnRecordStore


class TurnRecordCommitRuntime:

    def __init__(self, store: TurnRecordStore):
        self.store = store

    def commit(
        self,
        player_input: str,
        accepted_text: str,
        snapshot: RoundSnapshot,
        quality_decision: QualityDecision,
        base_card_state_revision: int,
        result_card_state_revision: int,
        state_commit_patch_id: str = "",
        mode: TurnMode = TurnMode.NORMAL,
        parent_turn_id: str = "",
    ) -> TurnRecord:
        """Commit an accepted turn record. Gate must accept."""
        # Gate check
        assert_side_effects_allowed(quality_decision)

        now = datetime.now(timezone.utc).isoformat()
        turn_index = self.store.get_next_turn_index(snapshot.card_id, snapshot.session_id)

        record = TurnRecord(
            turn_id=f"turn_{uuid.uuid4().hex[:12]}",
            trace_id=snapshot.trace_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            turn_index=turn_index,
            parent_turn_id=parent_turn_id,
            mode=mode,
            player_input=player_input,
            round_snapshot_ref=snapshot.snapshot_id,
            writer_output=accepted_text,
            quality_decision_ref=quality_decision.trace_id,
            state_commit_ref=state_commit_patch_id,
            base_card_state_revision=base_card_state_revision,
            result_card_state_revision=result_card_state_revision,
            created_at=now,
            accepted_at=now,
        )

        self.store.save(record)
        return record
