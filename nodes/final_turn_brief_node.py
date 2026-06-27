"""AWPV2FinalTurnBrief — ComfyUI node for producing FinalTurnBrief.

Director produces this after tool execution.
"""

from __future__ import annotations


class AWPV2FinalTurnBrief:
    """AWP V2 最终回合简报节点"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "director_plan": ("DIRECTOR_PLAN",),
                "enrichment_bundle": ("ENRICHMENT_BUNDLE",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
        }

    RETURN_TYPES = ("FINAL_TURN_BRIEF",)
    RETURN_NAMES = ("final_turn_brief",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2 / Director"

    def execute(self, director_plan: dict, enrichment_bundle: dict, round_snapshot: dict):
        from ..runtime.final_turn_brief_runtime import FinalTurnBriefRuntime
        from ..contracts.director_plan import DirectorPlan
        from ..contracts.enrichment_bundle import EnrichmentBundle
        from ..contracts.round_snapshot import RoundSnapshot

        plan = DirectorPlan.from_dict(director_plan)
        enrichment = EnrichmentBundle.from_dict(enrichment_bundle)
        snapshot = RoundSnapshot.from_dict(round_snapshot)

        runtime = FinalTurnBriefRuntime()
        brief = runtime.produce(plan, enrichment, snapshot)

        return (brief.to_dict(),)
