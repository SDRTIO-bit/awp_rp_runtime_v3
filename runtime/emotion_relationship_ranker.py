"""EmotionRelationshipRanker — deterministic ranking of emotion/relationship candidates.

Priority order:
  RELATIONSHIP_BOUNDARY > UNRESOLVED_HURT > TRUST_TENSION
  > GUARDEDNESS > EMOTIONAL_RESIDUE > MISUNDERSTANDING_SIGNAL
  > PROMISE_PRESSURE > JEALOUSY_RISK > CONFLICT_DEESCALATION
  > AFFECTION_RESTRAINT > SUBTEXT_OPPORTUNITY

Must exclude:
  - Conflicts with CardState
  - Conflicts with accepted TurnRecord
  - Violates mustNotDo
  - Asserts candidate as fact
  - Modifies relationships
  - Overrides player choice
  - Sudden shifts
  - Missing evidence
  - High duplication
"""

from __future__ import annotations

from ..contracts.emotion_relationship_candidate import (
    EmotionRelationshipCandidate, RelationshipKind,
)


# Priority weights by relationship kind
_KIND_WEIGHTS: dict[RelationshipKind, float] = {
    RelationshipKind.RELATIONSHIP_BOUNDARY: 0.90,
    RelationshipKind.UNRESOLVED_HURT: 0.88,
    RelationshipKind.TRUST_TENSION: 0.85,
    RelationshipKind.GUARDEDNESS: 0.80,
    RelationshipKind.EMOTIONAL_RESIDUE: 0.78,
    RelationshipKind.MISUNDERSTANDING_SIGNAL: 0.76,
    RelationshipKind.PROMISE_PRESSURE: 0.75,
    RelationshipKind.JEALOUSY_RISK: 0.73,
    RelationshipKind.CONFLICT_DEESCALATION: 0.72,
    RelationshipKind.AFFECTION_RESTRAINT: 0.70,
    RelationshipKind.SUBTEXT_OPPORTUNITY: 0.65,
}

MAX_ACCEPTED = 2


class EmotionRelationshipRanker:
    """Deterministic emotion/relationship candidate ranker."""

    def rank(
        self,
        candidates: list[EmotionRelationshipCandidate],
        max_accepted: int = MAX_ACCEPTED,
    ) -> tuple[list[EmotionRelationshipCandidate], list[EmotionRelationshipCandidate]]:
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

        # Deduplicate by similar focus and kind
        deduped = self._deduplicate(scored)

        # Split into accepted and rejected
        accepted = [c for c, _ in deduped[:max_accepted]]
        rejected = [c for c, _ in deduped[max_accepted:]]

        return accepted, rejected

    def _compute_score(self, candidate: EmotionRelationshipCandidate) -> float:
        """Compute priority score for a candidate.

        Score = kind_weight*0.30 + confidence*0.25
              + (1-player_agency_risk)*0.15 + (1-sudden_shift_risk)*0.15
              + (1-continuity_risk)*0.10 + evidence_bonus*0.05
        """
        kind_weight = _KIND_WEIGHTS.get(candidate.kind, 0.5)

        # Evidence bonus: more evidence = higher bonus
        evidence_bonus = min(len(candidate.evidence_refs) / 3.0, 1.0)

        return (
            kind_weight * 0.30
            + candidate.confidence * 0.25
            + (1.0 - candidate.player_agency_risk) * 0.15
            + (1.0 - candidate.sudden_shift_risk) * 0.15
            + (1.0 - candidate.continuity_risk) * 0.10
            + evidence_bonus * 0.05
        )

    def _deduplicate(
        self,
        scored: list[tuple[EmotionRelationshipCandidate, float]],
    ) -> list[tuple[EmotionRelationshipCandidate, float]]:
        """Remove duplicate candidates based on similar focus entities and kind."""
        seen: set[str] = set()
        result: list[tuple[EmotionRelationshipCandidate, float]] = []

        for candidate, score in scored:
            # Create a dedup key from kind + sorted focus entities
            key = f"{candidate.kind.value}:{':'.join(sorted(candidate.focus_entities))}"
            if key in seen:
                continue
            seen.add(key)
            result.append((candidate, score))

        return result
