"""HistoryRecallAdapter — converts HistoryRecallResult to AgentSuggestion.

Transforms the structured history recall output into standard AgentSuggestion
objects that can be consumed by SuggestionMerge.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from ..contracts.history_recall_result import HistoryRecallResult
from ..contracts.history_recall_suggestion import HistoryRecallSuggestion, HistorySuggestionKind


# Mapping from HistorySuggestionKind to SuggestionKind
_KIND_MAP: dict[HistorySuggestionKind, SuggestionKind] = {
    HistorySuggestionKind.CONTINUITY_FACT: SuggestionKind.CONTINUITY_ISSUE,
    HistorySuggestionKind.RELATIONSHIP_CONTEXT: SuggestionKind.RELATIONSHIP_SHIFT,
    HistorySuggestionKind.UNRESOLVED_THREAD: SuggestionKind.NARRATIVE_OPPORTUNITY,
    HistorySuggestionKind.HISTORICAL_CONFLICT: SuggestionKind.HISTORICAL_CONFLICT,
    HistorySuggestionKind.IDENTITY_CLARIFICATION: SuggestionKind.IDENTITY_CLARIFICATION,
    HistorySuggestionKind.TIMELINE_WARNING: SuggestionKind.TIMELINE_WARNING,
    HistorySuggestionKind.WRITER_CONSTRAINT: SuggestionKind.WRITER_CONSTRAINT,
    HistorySuggestionKind.DIRECTOR_FOLLOWUP: SuggestionKind.DIRECTOR_FOLLOWUP,
}


class HistoryRecallAdapter:
    """Converts HistoryRecallResult to AgentSuggestion list."""

    def to_suggestions(self, result: HistoryRecallResult) -> list[AgentSuggestion]:
        """Convert HistoryRecallResult to AgentSuggestion list.

        Each HistoryRecallSuggestion becomes one AgentSuggestion.
        Evidence refs are carried over.
        """
        now = datetime.now(timezone.utc).isoformat()
        suggestions: list[AgentSuggestion] = []

        for hs in result.suggestions:
            kind = _KIND_MAP.get(hs.kind, SuggestionKind.CONTINUITY_ISSUE)

            # Compute priority from confidence and kind
            priority = hs.priority if hs.priority > 0 else 0.5

            # Build evidence strings
            evidence = []
            source_refs = []
            for ev in result.evidence:
                if ev.evidence_id in hs.evidence_refs:
                    evidence.append(f"[{ev.source_type}] {ev.excerpt}")
                    source_refs.append(ev.source_ref)

            # Build risk flags
            risk_flags = []
            for risk in result.continuity_risks:
                if any(ref in risk.entity_refs for ref in hs.entity_refs):
                    risk_flags.append(f"continuity_risk:{risk.risk_level.value}")

            sug = AgentSuggestion(
                suggestion_id=f"hs_{uuid.uuid4().hex[:8]}",
                trace_id=result.trace_id,
                task_run_id=result.task_run_id,
                task_id="history-recall",
                role="history-recall",
                kind=kind,
                priority=priority,
                confidence=hs.confidence,
                summary=hs.summary,
                recommendations=[hs.summary] + ([hs.details] if hs.details else []),
                evidence=evidence,
                source_refs=source_refs,
                risk_flags=risk_flags,
                created_at=now,
            )
            suggestions.append(sug)

        # If no explicit suggestions but we have confirmed facts, create one
        if not suggestions and result.confirmed_facts:
            evidence = []
            source_refs = []
            for ev in result.evidence:
                evidence.append(f"[{ev.source_type}] {ev.excerpt}")
                source_refs.append(ev.source_ref)

            sug = AgentSuggestion(
                suggestion_id=f"hs_{uuid.uuid4().hex[:8]}",
                trace_id=result.trace_id,
                task_run_id=result.task_run_id,
                task_id="history-recall",
                role="history-recall",
                kind=SuggestionKind.CONTINUITY_ISSUE,
                priority=0.8,
                confidence=0.7,
                summary="; ".join(result.confirmed_facts[:3]),
                recommendations=result.writer_recommendations[:3],
                evidence=evidence,
                source_refs=source_refs,
                created_at=now,
            )
            suggestions.append(sug)

        return suggestions
