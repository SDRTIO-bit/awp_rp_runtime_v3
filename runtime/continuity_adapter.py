"""ContinuityAdapter — converts ContinuityResult to AgentSuggestion.

Transforms the structured continuity output into standard AgentSuggestion
objects that can be consumed by SuggestionMerge.

Continuity suggestions are HARD constraints for blocking issues
and SOFT guidance for warnings.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from ..contracts.continuity_result import ContinuityResult
from ..contracts.continuity_issue import ContinuityIssueKind, ContinuitySeverity
from ..contracts.continuity_suggestion import ContinuitySuggestion, ContinuitySuggestionKind


# Mapping from ContinuityIssueKind to SuggestionKind
_KIND_MAP: dict[ContinuityIssueKind, SuggestionKind] = {
    ContinuityIssueKind.IDENTITY_CONFLICT: SuggestionKind.CONTINUITY_IDENTITY_WARNING,
    ContinuityIssueKind.LOCATION_CONFLICT: SuggestionKind.CONTINUITY_LOCATION_WARNING,
    ContinuityIssueKind.TIMELINE_CONFLICT: SuggestionKind.CONTINUITY_TIMELINE_WARNING,
    ContinuityIssueKind.EVENT_STAGE_CONFLICT: SuggestionKind.CONTINUITY_BLOCKING_RISK,
    ContinuityIssueKind.STATE_CONFLICT: SuggestionKind.CONTINUITY_BLOCKING_RISK,
    ContinuityIssueKind.RELATIONSHIP_CONFLICT: SuggestionKind.CONTINUITY_BLOCKING_RISK,
    ContinuityIssueKind.KNOWLEDGE_BOUNDARY_CONFLICT: SuggestionKind.CONTINUITY_KNOWLEDGE_BOUNDARY_WARNING,
    ContinuityIssueKind.SECRET_EXPOSURE_RISK: SuggestionKind.CONTINUITY_KNOWLEDGE_BOUNDARY_WARNING,
    ContinuityIssueKind.PROMISE_RESOLUTION_RISK: SuggestionKind.CONTINUITY_FACT_CONSTRAINT,
    ContinuityIssueKind.CHARACTER_AVAILABILITY_CONFLICT: SuggestionKind.CONTINUITY_BLOCKING_RISK,
    ContinuityIssueKind.CAUSALITY_GAP: SuggestionKind.CONTINUITY_TIMELINE_WARNING,
    ContinuityIssueKind.MEMORY_CONFLICT: SuggestionKind.CONTINUITY_SUGGESTION_CONFLICT,
    ContinuityIssueKind.SUGGESTION_CONFLICT: SuggestionKind.CONTINUITY_SUGGESTION_CONFLICT,
    ContinuityIssueKind.WORLDBOOK_CONFLICT: SuggestionKind.CONTINUITY_SUGGESTION_CONFLICT,
    ContinuityIssueKind.PLAYER_AGENCY_RISK: SuggestionKind.CONTINUITY_BLOCKING_RISK,
}


class ContinuityAdapter:
    """Converts ContinuityResult to AgentSuggestion list."""

    def to_suggestions(self, result: ContinuityResult) -> list[AgentSuggestion]:
        """Convert ContinuityResult to AgentSuggestion list.

        Each accepted issue becomes one AgentSuggestion.
        Blocking issues become high-priority constraints.
        Warnings become soft guidance.
        """
        now = datetime.now(timezone.utc).isoformat()
        suggestions: list[AgentSuggestion] = []

        # Convert blocking issues
        for issue in result.blocking_issues:
            kind = _KIND_MAP.get(issue.kind, SuggestionKind.CONTINUITY_BLOCKING_RISK)
            sug = AgentSuggestion(
                suggestion_id=f"ci_block_{uuid.uuid4().hex[:8]}",
                trace_id=result.trace_id,
                task_run_id=result.task_run_id,
                task_id="continuity",
                role="continuity",
                kind=kind,
                priority=0.95,
                confidence=0.95,
                summary=issue.summary,
                recommendations=[issue.writer_constraint] if issue.writer_constraint else [],
                evidence=[],
                source_refs=issue.evidence_refs,
                risk_flags=["continuity_blocking"],
                created_at=now,
            )
            suggestions.append(sug)

        # Convert warnings
        for issue in result.warnings:
            kind = _KIND_MAP.get(issue.kind, SuggestionKind.CONTINUITY_WRITER_CONSTRAINT)
            sug = AgentSuggestion(
                suggestion_id=f"ci_warn_{uuid.uuid4().hex[:8]}",
                trace_id=result.trace_id,
                task_run_id=result.task_run_id,
                task_id="continuity",
                role="continuity",
                kind=kind,
                priority=0.7,
                confidence=0.7,
                summary=issue.summary,
                recommendations=[issue.writer_constraint] if issue.writer_constraint else [],
                evidence=[],
                source_refs=issue.evidence_refs,
                risk_flags=["continuity_warning"],
                created_at=now,
            )
            suggestions.append(sug)

        # Convert informational notes
        for issue in result.informational_notes:
            sug = AgentSuggestion(
                suggestion_id=f"ci_info_{uuid.uuid4().hex[:8]}",
                trace_id=result.trace_id,
                task_run_id=result.task_run_id,
                task_id="continuity",
                role="continuity",
                kind=SuggestionKind.CONTINUITY_DIRECTOR_FOLLOWUP,
                priority=0.4,
                confidence=0.5,
                summary=issue.summary,
                recommendations=[issue.director_recommendation] if issue.director_recommendation else [],
                evidence=[],
                source_refs=issue.evidence_refs,
                risk_flags=[],
                created_at=now,
            )
            suggestions.append(sug)

        # Add writer constraints as explicit constraint suggestions
        for constraint in result.writer_constraints:
            sug = AgentSuggestion(
                suggestion_id=f"ci_wc_{uuid.uuid4().hex[:8]}",
                trace_id=result.trace_id,
                task_run_id=result.task_run_id,
                task_id="continuity",
                role="continuity",
                kind=SuggestionKind.CONTINUITY_WRITER_CONSTRAINT,
                priority=0.9,
                confidence=0.9,
                summary=constraint,
                recommendations=[constraint],
                evidence=[],
                source_refs=[],
                risk_flags=["continuity_constraint"],
                created_at=now,
            )
            suggestions.append(sug)

        return suggestions
