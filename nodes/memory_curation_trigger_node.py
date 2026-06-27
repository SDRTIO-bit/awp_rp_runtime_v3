"""AWPV2MemoryCurationTrigger — deterministic trigger evaluation for Memory Curator.

ComfyUI node that evaluates whether memory curation should run for the
current accepted turn.
"""

from __future__ import annotations

from typing import Any


class AWPV2MemoryCurationTrigger:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "quality_decision": ("QUALITY_DECISION",),
                "turn_record_committed": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "card_state_commit_result": ("CARD_STATE_COMMIT_RESULT",),
                "turn_record": ("TURN_RECORD",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
        }

    RETURN_TYPES = ("MEMORY_CURATION_TRIGGER_DIAGNOSTICS",)
    RETURN_NAMES = ("trigger_diagnostics",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2/Memory"
    OUTPUT_SCHEMA_ID = "awp.rp.memory-curation-trigger-diagnostics.v1"

    def execute(
        self,
        quality_decision: dict[str, Any],
        turn_record_committed: bool,
        card_state_commit_result: dict[str, Any] | None = None,
        turn_record: dict[str, Any] | None = None,
        round_snapshot: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any]]:
        from ..contracts.quality_decision import QualityDecision
        from ..contracts.card_state_commit import CardStateCommitResult
        from ..contracts.turn_record import TurnRecord
        from ..contracts.round_snapshot import RoundSnapshot
        from ..runtime.memory_curation_trigger_policy import MemoryCurationTriggerPolicy

        qd = QualityDecision.from_dict(quality_decision) if quality_decision else None
        cs_result = CardStateCommitResult.from_dict(card_state_commit_result) if card_state_commit_result else None
        tr = TurnRecord.from_dict(turn_record) if turn_record else None
        snap = RoundSnapshot.from_dict(round_snapshot) if round_snapshot else None

        policy = MemoryCurationTriggerPolicy()
        result = policy.evaluate(
            quality_decision=qd,
            card_state_commit_result=cs_result,
            turn_record_committed=turn_record_committed,
            turn_record=tr,
            snapshot=snap,
        )

        return (result.to_dict(),)
