"""MemoryCurationRanker — deterministic ranking of memory curation candidates.

Ranks candidates by importance, evidence quality, and narrative value.
Enforces ActiveMemory 15-slot limit. Prioritizes:
  1. Unresolved promises/secrets/risks over resolved chat
  2. Active narrative goals over background facts
  3. Recoverable hooks over redundant entries
  4. Recent important events over old resolved items
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.memory_curation_candidate import (
    MemoryCurationCandidate, CurationTargetLayer, CurationOperation,
)


# Operation priority weights (higher = more important to keep)
_OPERATION_WEIGHTS = {
    CurationOperation.MARK_RESOLVED: 0.95,   # resolving frees slots
    CurationOperation.UPDATE_ACTIVE: 0.85,    # updating existing is efficient
    CurationOperation.MERGE_ACTIVE: 0.80,     # merging reduces duplication
    CurationOperation.CREATE_ACTIVE: 0.70,    # new active is important
    CurationOperation.ARCHIVE_ACTIVE_TO_RAG: 0.65,  # archiving preserves
    CurationOperation.CREATE_RAG: 0.50,       # RAG is long-term
    CurationOperation.UPDATE_RAG: 0.45,
    CurationOperation.MARK_RAG_STALE: 0.40,
    CurationOperation.DEMOTE_ACTIVE: 0.35,
    CurationOperation.NO_OP: 0.0,
}

# Kind priority for active memory (high-priority kinds are retained longer)
_KIND_IMPORTANCE = {
    "promise": 0.95,
    "secret": 0.90,
    "relationship_shift": 0.85,
    "misunderstanding": 0.82,
    "player_goal": 0.78,
    "scene_pressure": 0.72,
    "unresolved_thread": 0.70,
    "future_hook": 0.65,
    "emotional_trend": 0.60,
    "persistent_fact_reference": 0.55,
}


@dataclass(frozen=True)
class RankingResult:
    """Result of ranking candidates."""
    accepted: list[MemoryCurationCandidate] = field(default_factory=list)
    rejected: list[MemoryCurationCandidate] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)


class MemoryCurationRanker:
    """Deterministic ranker for memory curation candidates.

    No LLM. Pure scoring and sorting.
    """

    def rank(
        self,
        candidates: list[MemoryCurationCandidate],
        current_active_count: int = 0,
        max_active: int = 15,
        max_active_candidates: int = 5,
        max_rag_candidates: int = 5,
    ) -> RankingResult:
        """Rank candidates and select the best ones."""
        if not candidates:
            return RankingResult()

        # Score all candidates
        scored = [
            (self._score(c), idx, c) for idx, c in enumerate(candidates)
        ]

        # Sort by score DESC, then by original order (stable)
        scored.sort(key=lambda t: (-t[0], t[1]))

        accepted: list[MemoryCurationCandidate] = []
        rejected: list[MemoryCurationCandidate] = []
        reasons: list[str] = []
        active_count = 0
        rag_count = 0
        projected_active = current_active_count

        for score, _, candidate in scored:
            # Check capacity limits
            if candidate.target_layer == CurationTargetLayer.ACTIVE_MEMORY:
                if candidate.operation == CurationOperation.MARK_RESOLVED:
                    # Resolving frees a slot, always accept
                    accepted.append(candidate)
                    projected_active = max(0, projected_active - 1)
                    continue

                if candidate.operation in (
                    CurationOperation.CREATE_ACTIVE,
                    CurationOperation.UPDATE_ACTIVE,
                    CurationOperation.MERGE_ACTIVE,
                ):
                    if active_count >= max_active_candidates:
                        rejected.append(candidate)
                        reasons.append(
                            f"active_candidate_limit: {candidate.candidate_id}"
                        )
                        continue

                    # Check projected active memory count
                    if candidate.operation == CurationOperation.CREATE_ACTIVE:
                        if projected_active >= max_active:
                            # Try to demote to RAG instead
                            rejected.append(candidate)
                            reasons.append(
                                f"active_memory_full: {candidate.candidate_id}"
                            )
                            continue
                        projected_active += 1

                    active_count += 1

            elif candidate.target_layer == CurationTargetLayer.RAG_MEMORY:
                if rag_count >= max_rag_candidates:
                    rejected.append(candidate)
                    reasons.append(
                        f"rag_candidate_limit: {candidate.candidate_id}"
                    )
                    continue
                rag_count += 1

            accepted.append(candidate)

        return RankingResult(
            accepted=accepted,
            rejected=rejected,
            rejection_reasons=reasons,
        )

    def _score(self, candidate: MemoryCurationCandidate) -> float:
        """Score a candidate for ranking. Higher = more important."""
        score = 0.0

        # Operation weight
        op_weight = _OPERATION_WEIGHTS.get(candidate.operation, 0.5)
        score += op_weight * 0.40

        # Kind importance (for active memory operations)
        for tag in candidate.tags:
            kind_imp = _KIND_IMPORTANCE.get(tag, 0.5)
            score += kind_imp * 0.25
            break  # use first matching kind

        # Importance and confidence
        score += candidate.importance * 0.20
        score += candidate.confidence * 0.10

        # Evidence bonus: more evidence = higher confidence
        if len(candidate.evidence_refs) >= 2:
            score += 0.05

        return score
