"""OpportunityRanker — deterministic ranking of opportunity candidates.

Priority order:
  High-evidence unresolved promise/secret/relationship change
  > High-evidence player goal with future hook
  > High-evidence scene pressure and emotional tension
  > Ordinary foreshadowing echo
  > Unverifiable "interesting idea"

Must exclude:
  - Conflicts with CardState
  - Conflicts with accepted TurnRecord
  - Violates mustNotDo
  - Rejected by player
  - High duplication
  - Needs new facts to be valid
  - Overrides player choice
  - Auto-advances world state
"""

from __future__ import annotations

from ..contracts.opportunity_candidate import OpportunityCandidate, OpportunityKind


# Priority weights by opportunity kind
_KIND_WEIGHTS: dict[OpportunityKind, float] = {
    OpportunityKind.PROMISE_PRESSURE: 0.95,
    OpportunityKind.SECRET_PRESSURE: 0.90,
    OpportunityKind.RELATIONSHIP_TENSION: 0.85,
    OpportunityKind.MISUNDERSTANDING_PRESSURE: 0.82,
    OpportunityKind.GOAL_REACTIVATION: 0.78,
    OpportunityKind.SCENE_PRESSURE: 0.72,
    OpportunityKind.EMOTIONAL_SHIFT: 0.70,
    OpportunityKind.CHOICE_OPENING: 0.65,
    OpportunityKind.FORESHADOWING_ECHO: 0.60,
    OpportunityKind.PACE_VARIATION: 0.55,
    OpportunityKind.THREAD_RECALL: 0.50,
}

MAX_ACCEPTED = 2


class OpportunityRanker:
    """Deterministic opportunity candidate ranker."""

    def rank(
        self,
        candidates: list[OpportunityCandidate],
        max_accepted: int = MAX_ACCEPTED,
    ) -> tuple[list[OpportunityCandidate], list[OpportunityCandidate]]:
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

    def _compute_score(self, candidate: OpportunityCandidate) -> float:
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
        scored: list[tuple[OpportunityCandidate, float]],
    ) -> list[tuple[OpportunityCandidate, float]]:
        """Remove duplicate candidates based on similar focus entities and kind."""
        seen: set[str] = set()
        result: list[tuple[OpportunityCandidate, float]] = []

        for candidate, score in scored:
            # Create a dedup key from kind + sorted focus entities
            key = f"{candidate.kind.value}:{':'.join(sorted(candidate.focus_entities))}"
            if key in seen:
                continue
            seen.add(key)
            result.append((candidate, score))

        return result
