"""AWPV2EmotionRelationshipAgent — ComfyUI node for running Emotion/Relationship Agent."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.delegation_plan import DelegationTask
from ..runtime.emotion_relationship_trigger_policy import EmotionRelationshipTriggerResult
from ..runtime.emotion_relationship_runtime import EmotionRelationshipRuntime


class AWPV2EmotionRelationshipAgent:
    """Run the Emotion/Relationship Agent to identify relational dynamics."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
                "er_trigger_result": ("ER_TRIGGER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("ER_RESULT",)
    RETURN_NAMES = ("er_result",)
    FUNCTION = "run"
    CATEGORY = "AWP V2/EmotionRelationship"

    def run(
        self,
        round_snapshot: RoundSnapshot,
        er_trigger_result: EmotionRelationshipTriggerResult,
    ) -> tuple:
        runtime = EmotionRelationshipRuntime()
        task = DelegationTask(
            task_id="er_task",
            role="emotion-relationship",
            tool_allowlist=list(runtime.query_planner.__class__.__dict__.keys()),
        )
        result = runtime.run(
            snapshot=round_snapshot,
            task=task,
            trigger_result=er_trigger_result,
        )
        return (result,)
