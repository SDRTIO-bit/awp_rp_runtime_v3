"""AWPV2SuggestionMerge — merges sub-agent suggestions.

Input: delegation_plan, turn_brief, round_snapshot, execution_results
Output: suggestion_merge_result
"""

from __future__ import annotations

from typing import Any


class AWPV2SuggestionMerge:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "delegation_plan": ("DELEGATION_PLAN",),
                "turn_brief": ("TURN_BRIEF",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
                "execution_results": ("AGENT_EXECUTION_RESULTS",),
            },
        }

    RETURN_TYPES = ("SUGGESTION_MERGE_RESULT",)
    RETURN_NAMES = ("suggestion_merge_result",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        delegation_plan: dict[str, Any],
        turn_brief: dict[str, Any],
        round_snapshot: dict[str, Any],
        execution_results: list[dict[str, Any]],
    ) -> tuple[dict[str, Any]]:
        from ..contracts.delegation_plan import DelegationPlan
        from ..contracts.turn_brief import TurnBrief
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.agent_execution_result import AgentExecutionResult
        from ..runtime.suggestion_merger import SuggestionMerger

        plan = DelegationPlan.from_dict(delegation_plan)
        brief = TurnBrief.from_dict(turn_brief)
        snapshot = RoundSnapshot.from_dict(round_snapshot)
        results = [AgentExecutionResult.from_dict(r) for r in execution_results]

        merger = SuggestionMerger()
        merge_result = merger.merge(plan, brief, snapshot, results)
        return (merge_result.to_dict(),)
