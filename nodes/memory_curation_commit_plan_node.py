"""AWPV2MemoryCurationCommitPlan — compiles curation result into MemoryCommitPlan.

ComfyUI node that converts accepted candidates into the MemoryCommitPlan
format that the existing commit runtimes can execute.
"""

from __future__ import annotations

from typing import Any


class AWPV2MemoryCurationCommitPlan:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "curation_result": ("MEMORY_CURATION_RESULT",),
                "turn_id": ("STRING",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
                "quality_decision": ("QUALITY_DECISION",),
            },
            "optional": {
                "trace_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("MEMORY_COMMIT_PLAN",)
    RETURN_NAMES = ("memory_commit_plan",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2/Memory"
    OUTPUT_SCHEMA_ID = "awp.rp.memory-commit-plan.v1"

    def execute(
        self,
        curation_result: dict[str, Any],
        turn_id: str,
        round_snapshot: dict[str, Any],
        quality_decision: dict[str, Any],
        trace_id: str = "",
    ) -> tuple[dict[str, Any]]:
        from ..contracts.memory_curation_result import MemoryCurationResult
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.quality_decision import QualityDecision
        from ..runtime.memory_plan_compiler import MemoryPlanCompiler

        result = MemoryCurationResult.from_dict(curation_result)
        snap = RoundSnapshot.from_dict(round_snapshot)
        qd = QualityDecision.from_dict(quality_decision)

        compiler = MemoryPlanCompiler()
        plan = compiler.compile(
            curation_result=result,
            turn_id=turn_id,
            card_id=snap.card_id,
            session_id=snap.session_id,
            trace_id=trace_id or snap.trace_id,
            expected_card_state_revision=snap.base_card_state_revision,
            quality_decision_ref=qd.trace_id,
        )

        return (plan.to_dict(),)
