"""EmotionRelationshipAdapter — converts EmotionRelationshipResult to AgentSuggestion.

Transforms the structured emotion/relationship output into standard AgentSuggestion
objects that can be consumed by SuggestionMerge.

Emotion/relationship suggestions are SOFT guidance — they cannot assert facts
or modify relationships.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from ..contracts.emotion_relationship_result import EmotionRelationshipResult
from ..contracts.emotion_relationship_candidate import RelationshipKind
from ..contracts.emotion_relationship_suggestion import (
    EmotionRelationshipSuggestion, EmotionRelationshipSuggestionKind,
)


# Mapping from RelationshipKind to SuggestionKind
_KIND_MAP: dict[RelationshipKind, SuggestionKind] = {
    RelationshipKind.TRUST_TENSION: SuggestionKind.ER_TRUST_TENSION,
    RelationshipKind.GUARDEDNESS: SuggestionKind.ER_GUARDEDNESS,
    RelationshipKind.EMOTIONAL_RESIDUE: SuggestionKind.ER_EMOTIONAL_RESIDUE,
    RelationshipKind.UNRESOLVED_HURT: SuggestionKind.ER_UNRESOLVED_HURT,
    RelationshipKind.PROMISE_PRESSURE: SuggestionKind.ER_PROMISE_PRESSURE,
    RelationshipKind.MISUNDERSTANDING_SIGNAL: SuggestionKind.ER_MISUNDERSTANDING_SIGNAL,
    RelationshipKind.JEALOUSY_RISK: SuggestionKind.ER_JEALOUSY_RISK,
    RelationshipKind.AFFECTION_RESTRAINT: SuggestionKind.ER_AFFECTION_RESTRAINT,
    RelationshipKind.CONFLICT_DEESCALATION: SuggestionKind.ER_CONFLICT_DEESCALATION,
    RelationshipKind.RELATIONSHIP_BOUNDARY: SuggestionKind.ER_RELATIONSHIP_BOUNDARY,
    RelationshipKind.SUBTEXT_OPPORTUNITY: SuggestionKind.ER_SUBTEXT_OPPORTUNITY,
}

# Violated policies that should generate ER_WARNING suggestions
_WARNING_POLICIES = {"player_agency", "relationship_event", "sudden_shift"}


class EmotionRelationshipAdapter:
    """Converts EmotionRelationshipResult to AgentSuggestion list."""

    def to_suggestions(self, result: EmotionRelationshipResult) -> list[AgentSuggestion]:
        """Convert EmotionRelationshipResult to AgentSuggestion list.

        Each accepted EmotionRelationshipCandidate becomes one AgentSuggestion.
        Evidence refs are carried over.
        """
        now = datetime.now(timezone.utc).isoformat()
        suggestions: list[AgentSuggestion] = []

        for candidate in result.candidates:
            kind = _KIND_MAP.get(candidate.kind, SuggestionKind.ER_SUBTEXT_OPPORTUNITY)

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
            if candidate.sudden_shift_risk > 0.3:
                risk_flags.append("sudden_shift_risk")

            sug = AgentSuggestion(
                suggestion_id=f"erc_{uuid.uuid4().hex[:8]}",
                trace_id=result.trace_id,
                task_run_id=result.task_run_id,
                task_id="emotion-relationship",
                role="emotion-relationship",
                kind=kind,
                priority=candidate.confidence,
                confidence=candidate.confidence,
                summary=candidate.summary,
                recommendations=recommendations,
                evidence=evidence,
                source_refs=source_refs,
                risk_flags=risk_flags,
                created_at=now,
            )
            suggestions.append(sug)

        # Add warning suggestions for rejected candidates with critical violations
        for rejected in result.rejected_candidates:
            if rejected.violated_policy in _WARNING_POLICIES:
                sug = AgentSuggestion(
                    suggestion_id=f"erc_warn_{uuid.uuid4().hex[:8]}",
                    trace_id=result.trace_id,
                    task_run_id=result.task_run_id,
                    task_id="emotion-relationship",
                    role="emotion-relationship",
                    kind=SuggestionKind.ER_WARNING,
                    priority=0.9,
                    confidence=0.9,
                    summary=f"情感关系候选被拒绝: {rejected.reason}",
                    recommendations=["注意: 此方向存在风险，需谨慎处理"],
                    evidence=[],
                    source_refs=rejected.evidence_refs,
                    risk_flags=["emotion_relationship_rejected"],
                    created_at=now,
                )
                suggestions.append(sug)

        return suggestions
