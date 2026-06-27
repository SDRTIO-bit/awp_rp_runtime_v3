"""AWPV2AgentTrace — outputs agent execution trace.

Input: round_snapshot, turn_brief, delegation_plan, execution_results, merge_result
Output: execution_trace
"""

from __future__ import annotations

from typing import Any


class AWPV2AgentTrace:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
            "optional": {
                "turn_brief": ("TURN_BRIEF",),
                "delegation_plan": ("DELEGATION_PLAN",),
                "execution_results": ("AGENT_EXECUTION_RESULTS",),
                "suggestion_merge_result": ("SUGGESTION_MERGE_RESULT",),
            },
        }

    RETURN_TYPES = ("EXECUTION_TRACE",)
    RETURN_NAMES = ("execution_trace",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        round_snapshot: dict[str, Any],
        turn_brief: dict[str, Any] | None = None,
        delegation_plan: dict[str, Any] | None = None,
        execution_results: list[dict[str, Any]] | None = None,
        suggestion_merge_result: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any]]:
        from ..contracts.execution_trace import ExecutionTrace, TraceEvent
        from ..contracts.round_snapshot import RoundSnapshot

        snapshot = RoundSnapshot.from_dict(round_snapshot)
        events = [
            TraceEvent(event_id="evt_snap", event_type="snapshot_built",
                       actor="AWPV2RoundSnapshot", details={"snapshot_id": snapshot.snapshot_id}),
        ]

        if turn_brief:
            events.append(TraceEvent(event_id="evt_director", event_type="director_called",
                                     actor="AWPV2Director"))
        if delegation_plan:
            events.append(TraceEvent(event_id="evt_plan", event_type="delegation_planned",
                                     actor="AWPV2DelegationPlan"))
        if execution_results:
            events.append(TraceEvent(event_id="evt_pool", event_type="subagents_executed",
                                     actor="AWPV2DynamicSubAgentPool",
                                     details={"count": len(execution_results)}))
        if suggestion_merge_result:
            events.append(TraceEvent(event_id="evt_merge", event_type="suggestions_merged",
                                     actor="AWPV2SuggestionMerge"))

        trace = ExecutionTrace(
            trace_id=snapshot.trace_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            events=events,
            success=True,
        )
        return (trace.to_dict(),)
