"""AgentIntegrationTrace — integration-level tracing for D-Integration.

Aggregates agent reports, budget report, conflicts, and resolution
into a single IntegratedTurnTrace.
"""

from __future__ import annotations

from ..contracts.integrated_turn_trace import IntegratedTurnTrace
from ..contracts.agent_execution_report import AgentExecutionReport
from ..contracts.turn_agent_budget_report import TurnAgentBudgetReport
from ..contracts.suggestion_conflict import SuggestionConflict
from .director_suggestion_resolution_runtime import DirectorResolution


class AgentIntegrationTrace:
    """Builds IntegratedTurnTrace from component reports."""

    def build(
        self,
        turn_id: str,
        trace_id: str,
        card_id: str,
        session_id: str,
        agent_reports: list[AgentExecutionReport],
        budget_report: TurnAgentBudgetReport,
        conflicts: list[SuggestionConflict],
        resolution: DirectorResolution,
        dropped_suggestion_ids: list[str] | None = None,
        truncated_sections: list[str] | None = None,
        budget_reason: str = "",
        final_brief_size: int = 0,
        total_duration_ms: int = 0,
    ) -> IntegratedTurnTrace:
        """Build the full integration trace."""
        return IntegratedTurnTrace(
            turn_id=turn_id,
            trace_id=trace_id,
            card_id=card_id,
            session_id=session_id,
            agent_reports=agent_reports,
            budget_report=budget_report,
            conflicts=conflicts,
            accepted_suggestion_ids=resolution.accepted_suggestion_ids,
            partially_accepted_suggestion_ids=resolution.partially_accepted_suggestion_ids,
            rejected_suggestion_ids=resolution.rejected_suggestion_ids,
            rejection_reasons=resolution.rejection_reasons,
            dropped_suggestion_ids=dropped_suggestion_ids or [],
            truncated_sections=truncated_sections or [],
            budget_reason=budget_reason,
            final_brief_size=final_brief_size,
            total_duration_ms=total_duration_ms,
        )
