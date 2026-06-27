"""WorldLifeAdapter — converts WorldLifeResult to AgentSuggestion.

Transforms the structured world-life output into standard AgentSuggestion
objects that can be consumed by SuggestionMerge.

World-life suggestions are SOFT guidance — they cannot be asserted as facts.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from ..contracts.world_life_result import WorldLifeResult
from ..contracts.world_life_candidate import WorldLifeKind
from ..contracts.world_life_suggestion import WorldLifeSuggestion, WorldLifeSuggestionKind


# Mapping from WorldLifeKind to SuggestionKind
_KIND_MAP: dict[WorldLifeKind, SuggestionKind] = {
    WorldLifeKind.ENVIRONMENTAL_PRESSURE: SuggestionKind.ENVIRONMENTAL_PRESSURE,
    WorldLifeKind.WEATHER_OR_TIME_ATMOSPHERE: SuggestionKind.WEATHER_OR_TIME_ATMOSPHERE,
    WorldLifeKind.NPC_SIDE_TENSION: SuggestionKind.NPC_SIDE_TENSION,
    WorldLifeKind.EVENT_STAGE_ECHO: SuggestionKind.EVENT_STAGE_ECHO,
    WorldLifeKind.LOCATION_LIFE_DETAIL: SuggestionKind.LOCATION_LIFE_DETAIL,
    WorldLifeKind.SOCIAL_BACKGROUND_SIGNAL: SuggestionKind.SOCIAL_BACKGROUND_SIGNAL,
    WorldLifeKind.WORLDBOOK_RESONANCE: SuggestionKind.WORLDBOOK_RESONANCE,
    WorldLifeKind.OFFSCREEN_CONSEQUENCE_HINT: SuggestionKind.OFFSCREEN_CONSEQUENCE_HINT,
    WorldLifeKind.AMBIENT_RUMOR_SIGNAL: SuggestionKind.AMBIENT_RUMOR_SIGNAL,
    WorldLifeKind.SCENE_TRANSITION_PRESSURE: SuggestionKind.LOCATION_LIFE_DETAIL,
}


class WorldLifeAdapter:
    """Converts WorldLifeResult to AgentSuggestion list."""

    def to_suggestions(self, result: WorldLifeResult) -> list[AgentSuggestion]:
        """Convert WorldLifeResult to AgentSuggestion list.

        Each accepted WorldLifeCandidate becomes one AgentSuggestion.
        Evidence refs are carried over.
        """
        now = datetime.now(timezone.utc).isoformat()
        suggestions: list[AgentSuggestion] = []

        for candidate in result.candidates:
            kind = _KIND_MAP.get(candidate.kind, SuggestionKind.LOCATION_LIFE_DETAIL)

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
            if candidate.state_change_risk > 0.1:
                risk_flags.append("state_change_risk")

            sug = AgentSuggestion(
                suggestion_id=f"wlc_{uuid.uuid4().hex[:8]}",
                trace_id=result.trace_id,
                task_run_id=result.task_run_id,
                task_id="world-life",
                role="world-life",
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
            if rejected.violated_policy in ("player_agency", "event_assertion", "auto_advance"):
                sug = AgentSuggestion(
                    suggestion_id=f"wlc_warn_{uuid.uuid4().hex[:8]}",
                    trace_id=result.trace_id,
                    task_run_id=result.task_run_id,
                    task_id="world-life",
                    role="world-life",
                    kind=SuggestionKind.WORLD_LIFE_WARNING,
                    priority=0.9,
                    confidence=0.9,
                    summary=f"世界活性候选被拒绝: {rejected.reason}",
                    recommendations=["注意: 此方向存在风险，需谨慎处理"],
                    evidence=[],
                    source_refs=rejected.evidence_refs,
                    risk_flags=["world_life_rejected"],
                    created_at=now,
                )
                suggestions.append(sug)

        return suggestions
