"""AWPV2MemoryCuratorAgent — runs the Memory Curator Agent.

ComfyUI node that executes the full Memory Curator pipeline:
  trigger → request → query plan → adapter → result
"""

from __future__ import annotations

from typing import Any


class AWPV2MemoryCuratorAgent:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "quality_decision": ("QUALITY_DECISION",),
                "turn_record": ("TURN_RECORD",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
            "optional": {
                "card_state_commit_result": ("CARD_STATE_COMMIT_RESULT",),
                "trace_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("MEMORY_CURATION_RESULT", "MEMORY_CURATION_TRIGGER_DIAGNOSTICS")
    RETURN_NAMES = ("curation_result", "trigger_diagnostics")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2/Memory"
    OUTPUT_SCHEMA_ID = "awp.rp.memory-curation-result.v1"

    def execute(
        self,
        quality_decision: dict[str, Any],
        turn_record: dict[str, Any],
        round_snapshot: dict[str, Any],
        card_state_commit_result: dict[str, Any] | None = None,
        trace_id: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        from ..contracts.quality_decision import QualityDecision
        from ..contracts.card_state_commit import CardStateCommitResult
        from ..contracts.turn_record import TurnRecord
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.execution_trace import ExecutionTrace
        from ..runtime.memory_curation_runtime import MemoryCurationRuntime

        qd = QualityDecision.from_dict(quality_decision)
        tr = TurnRecord.from_dict(turn_record)
        snap = RoundSnapshot.from_dict(round_snapshot)
        cs_result = CardStateCommitResult.from_dict(card_state_commit_result) if card_state_commit_result else None

        runtime = MemoryCurationRuntime()
        result = runtime.curate(
            quality_decision=qd,
            card_state_commit_result=cs_result,
            turn_record=tr,
            snapshot=snap,
        )

        # Also return the trigger diagnostics
        trigger_result = runtime.trigger_policy.evaluate(
            quality_decision=qd,
            card_state_commit_result=cs_result,
            turn_record_committed=True,
            turn_record=tr,
            snapshot=snap,
        )

        return (result.to_dict(), trigger_result.to_dict())
