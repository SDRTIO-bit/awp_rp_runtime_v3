"""WorldLifeRanker — deterministic ranking of world-life candidates.

Priority order:
  High-evidence scene/weather/location/time pressure
  > High-evidence NPC side-tension and event stage echo
  > High-evidence social background or worldbook resonance
  > Offscreen consequence hints (weak signals)
  > Ideas that need new facts to be valid

Must exclude:
  - Conflicts with CardState
  - Conflicts with accepted TurnRecord
  - Violates mustNotDo
  - Auto-advances time, events, relationships, locations, or scenes
  - Overrides player choice
  - Asserts candidate as fact
  - Missing evidence
  - High duplication
  - Only adds irrelevant environmental description
"""
from __future__ import annotations

from ..contracts.world_life_candidate import WorldLifeCandidate, WorldLifeKind


# Priority weights by world-life kind
_KIND_WEIGHTS: dict[WorldLifeKind, float] = {
    WorldLifeKind.ENVIRONMENTAL_PRESSURE: 0.85,
    WorldLifeKind.WEATHER_OR_TIME_ATMOSPHERE: 0.80,
    WorldLifeKind.NPC_SIDE_TENSION: 0.78,
    WorldLifeKind.EVENT_STAGE_ECHO: 0.75,
    WorldLifeKind.LOCATION_LIFE_DETAIL: 0.72,
    WorldLifeKind.SOCIAL_BACKGROUND_SIGNAL: 0.65,
    WorldLifeKind.WORLDBOOK_RESONANCE: 0.70,
    WorldLifeKind.OFFSCREEN_CONSEQUENCE_HINT: 0.55,
    WorldLifeKind.AMBIENT_RUMOR_SIGNAL: 0.50,
    WorldLifeKind.SCENE_TRANSITION_PRESSURE: 0.60,
}

MAX_ACCEPTED = 2


class WorldLifeRanker:
    """Deterministic world-life candidate ranker."""

    def rank(
        self,
        candidates: list[WorldLifeCandidate],
        max_accepted: int = MAX_ACCEPTED,
    ) -> tuple[list[WorldLifeCandidate], list[WorldLifeCandidate]]:
        """Rank candidates and return (accepted, rejected_by_rank).

        Accepted: top max_candidates by score.
        Rejected: remaining candidates (not rejected for policy reasons,
                  just outranked).
        """
        if not candidates:
            return [], []

        # Score each candidate
        scored = []
        for c in candidates:
            score = self._compute_score(c)
            scored.append((c, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Deduplicate by similar title/focus
        deduped = self._deduplicate(scored)

        # Split into accepted and rejected
        accepted = [c for c, _ in deduped[:max_accepted]]
        rejected = [c for c, _ in deduped[max_accepted:]]

        return accepted, rejected

    def _compute_score(self, candidate: WorldLifeCandidate) -> float:
        """Compute priority score for a candidate."""
        kind_weight = _KIND_WEIGHTS.get(candidate.kind, 0.5)

        return (
            kind_weight * 0.30
            + candidate.relevance_score * 0.25
            + candidate.confidence * 0.20
            + candidate.novelty_score * 0.10
            + (1.0 - candidate.player_agency_risk) * 0.10
            + (1.0 - candidate.continuity_risk) * 0.05
        )

    def _deduplicate(
        self,
        scored: list[tuple[WorldLifeCandidate, float]],
    ) -> list[tuple[WorldLifeCandidate, float]]:
        """Remove duplicate candidates based on similar focus and kind."""
        seen: set[str] = set()
        result: list[tuple[WorldLifeCandidate, float]] = []

        for candidate, score in scored:
            # Create a dedup key from kind + sorted focus entities + location
            key_parts = [candidate.kind.value]
            key_parts.extend(sorted(candidate.focus_entities))
            if candidate.focus_location:
                key_parts.append(candidate.focus_location)
            key = ":".join(key_parts)
            if key in seen:
                continue
            seen.add(key)
            result.append((candidate, score))

        return result
