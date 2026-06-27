"""AWPV2TurnRecordCommit — commit accepted turn records.

Gate must accept. Binds base/result revision.
"""

from __future__ import annotations

from typing import Any


class AWPV2TurnRecordCommit:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "player_input": ("STRING",),
                "accepted_text": ("STRING",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
                "quality_decision": ("QUALITY_DECISION",),
                "base_card_state_revision": ("INT",),
                "result_card_state_revision": ("INT",),
            },
            "optional": {
                "patch_id": ("STRING", {"default": ""}),
                "mode": ("STRING", {"default": "normal"}),
                "parent_turn_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("TURN_RECORD",)
    RETURN_NAMES = ("turn_record",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        player_input: str,
        accepted_text: str,
        round_snapshot: dict[str, Any],
        quality_decision: dict[str, Any],
        base_card_state_revision: int,
        result_card_state_revision: int,
        patch_id: str = "",
        mode: str = "normal",
        parent_turn_id: str = "",
    ) -> tuple[dict[str, Any]]:
        import uuid
        from datetime import datetime, timezone
        from ..contracts.turn_record import TurnRecord, TurnMode
        from ..contracts.quality_decision import QualityDecision, assert_side_effects_allowed
        from ..contracts.round_snapshot import RoundSnapshot

        decision = QualityDecision.from_dict(quality_decision)
        assert_side_effects_allowed(decision)

        snapshot = RoundSnapshot.from_dict(round_snapshot)
        now = datetime.now(timezone.utc).isoformat()
        turn_mode = TurnMode(mode) if mode in [m.value for m in TurnMode] else TurnMode.NORMAL

        record = TurnRecord(
            turn_id=f"turn_{uuid.uuid4().hex[:12]}",
            trace_id=snapshot.trace_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            turn_index=0,  # Would be set by store
            parent_turn_id=parent_turn_id,
            mode=turn_mode,
            player_input=player_input,
            round_snapshot_ref=snapshot.snapshot_id,
            writer_output=accepted_text,
            quality_decision_ref=decision.trace_id,
            state_commit_ref=patch_id,
            base_card_state_revision=base_card_state_revision,
            result_card_state_revision=result_card_state_revision,
            created_at=now,
            accepted_at=now,
        )

        return (record.to_dict(),)
