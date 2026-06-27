"""OpportunityAdapter — converts OpportunityResult to AgentSuggestion.

Transforms the structured opportunity output into standard AgentSuggestion
objects that can be consumed by SuggestionMerge.

Opportunity suggestions are SOFT guidance — they cannot be asserted as facts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from ..contracts.opportunity_result import OpportunityResult
from ..contracts.opportunity_candidate import OpportunityKind
from ..contracts.opportunity_suggestion import OpportunitySuggestion, OpportunitySuggestionKind


# Mapping from OpportunityKind to SuggestionKind
_KIND_MAP: dict[OpportunityKind, SuggestionKind] = {
    OpportunityKind.PROMISE_PRESSURE: SuggestionKind.PROMISE_PRESSURE,
    OpportunityKind.RELATIONSHIP_TENSION: SuggestionKind.RELATIONSHIP_TENSION,
    OpportunityKind.EMOTIONAL_SHIFT: SuggestionKind.EMOTIONAL_SHIFT,
    OpportunityKind.SECRET_PRESSURE: SuggestionKind.SECRET_PRESSURE,
    OpportunityKind.MISUNDERSTANDING_PRESSURE: SuggestionKind.MISUNDERSTANDING_PRESSURE,
    OpportunityKind.GOAL_REACTIVATION: SuggestionKind.GOAL_REACTIVATION,
    OpportunityKind.SCENE_PRESSURE: SuggestionKind.SCENE_PRESSURE,
    OpportunityKind.CHOICE_OPENING: SuggestionKind.CHOICE_OPENING,
    OpportunityKind.FORESHADOWING_ECHO: SuggestionKind.FORESHADOWING_ECHO,
    OpportunityKind.PACE_VARIATION: SuggestionKind.PACE_VARIATION,
    OpportunityKind.THREAD_RECALL: SuggestionKind.NARRATIVE_OPPORTUNITY,
}


class OpportunityAdapter:
    """Converts OpportunityResult to AgentSuggestion list."""

    def to_suggestions(self, result: OpportunityResult) -> list[AgentSuggestion]:
        """Convert OpportunityResult to AgentSuggestion list.

        Each accepted OpportunityCandidate becomes one AgentSuggestion.
        Evidence refs are carried over.
        """
        now = datetime.now(timezone.utc).isoformat()
        suggestions: list[AgentSuggestion] = []

        for candidate in result.candidates:
            kind = _KIND_MAP.get(candidate.kind, SuggestionKind.NARRATIVE_OPPORTUNITY)

            # Build evidence strings
            evidence = []
            source_refs = list(candidate.evidence_refs)

            # Build recommendations from suggested use
            recommendations = []
            if candidate.suggested_writer_use:
                recommendations.append(candidate.suggested_writer_use)
            if candidate.suggested_director_use:
                recommendations.append(candidate.suggested_director_use)

            # Build risk flags
            risk_flags = []
            if candidate.player_agency_risk > 0.3:
                risk_flags.append("player_agency_risk")
            if candidate.continuity_risk > 0.3:
                risk_flags.append("continuity_risk")

            sug = AgentSuggestion(
                suggestion_id=f"oc_{uuid.uuid4().hex[:8]}",
                trace_id=result.trace_id,
                task_run_id=result.task_run_id,
                task_id="opportunity",
                role="opportunity",
                kind=kind,
                priority=candidate.relevance_score,
                confidence=candidate.confidence,
                summary=candidate.summary,
                recommendations=recommendations,
                evidence=evidence,
                source_refs=source_refs,
                risk_flags=risk_flags,
                created_at=now,
            )
            suggestions.append(sug)

        # Add warning suggestions for rejected candidates
        for rejected in result.rejected_candidates:
            if rejected.violated_policy in ("player_agency", "event_assertion"):
                sug = AgentSuggestion(
                    suggestion_id=f"oc_warn_{uuid.uuid4().hex[:8]}",
                    trace_id=result.trace_id,
                    task_run_id=result.task_run_id,
                    task_id="opportunity",
                    role="opportunity",
                    kind=SuggestionKind.OPPORTUNITY_WARNING,
                    priority=0.9,
                    confidence=0.9,
                    summary=f"机会候选被拒绝: {rejected.reason}",
                    recommendations=["注意: 此方向存在风险，需谨慎处理"],
                    evidence=[],
                    source_refs=rejected.evidence_refs,
                    risk_flags=["opportunity_rejected"],
                    created_at=now,
                )
                suggestions.append(sug)

        return suggestions
