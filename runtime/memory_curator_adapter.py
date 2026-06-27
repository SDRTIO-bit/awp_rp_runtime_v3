"""MemoryCuratorAdapter — adapter protocol and fake implementation.

The adapter is the bridge between the Memory Curator Runtime and the
candidate generator. In D6 we use FakeMemoryCandidateGenerator (deterministic).
A real LLM adapter is future work.
"""

from __future__ import annotations

from typing import Protocol

from ..contracts.memory_curation_request import MemoryCurationRequest
from ..contracts.memory_curation_result import MemoryCurationResult
from ..contracts.memory_curation_candidate import MemoryCurationCandidate
from .memory_curation_query_planner import CurationQueryPlan
from .memory_candidate_generator import FakeMemoryCandidateGenerator
from .memory_curation_validator import MemoryCurationValidator
from .memory_curation_ranker import MemoryCurationRanker


class MemoryCuratorAdapterProtocol(Protocol):
    """Protocol for the Memory Curator adapter."""
    def curate(
        self, request: MemoryCurationRequest, plan: CurationQueryPlan,
    ) -> MemoryCurationResult:
        ...


class FakeMemoryCuratorAdapter:
    """Deterministic adapter for D6. No LLM involved.

    Uses FakeMemoryCandidateGenerator + Validator + Ranker to produce
    a MemoryCurationResult from accepted turn data.
    """

    def __init__(self):
        self.generator = FakeMemoryCandidateGenerator()
        self.validator = MemoryCurationValidator()
        self.ranker = MemoryCurationRanker()

    def curate(
        self,
        request: MemoryCurationRequest,
        plan: CurationQueryPlan,
    ) -> MemoryCurationResult:
        """Run the full curation pipeline deterministically."""
        # 1. Generate candidates
        candidates = self.generator.generate(request, plan)

        # 2. Validate candidates
        validation = self.validator.validate_all(candidates, request)

        # 3. Rank accepted candidates
        current_active_count = len(request.active_memory_snapshot)
        ranking = self.ranker.rank(
            validation.valid_candidates,
            current_active_count=current_active_count,
            max_active=15,
            max_active_candidates=plan.max_active_candidates,
            max_rag_candidates=plan.max_rag_candidates,
        )

        # 4. Build result
        all_rejected = validation.rejected_candidates + ranking.rejected
        all_rejection_reasons = validation.rejection_reasons + ranking.rejection_reasons

        return MemoryCurationResult(
            result_id=f"mcr_{request.turn_id}",
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            card_id=request.card_id,
            session_id=request.session_id,
            accepted_candidates=ranking.accepted,
            rejected_candidates=all_rejected,
            rejection_reasons=all_rejection_reasons,
            degraded=False,
            total_candidates_generated=len(candidates),
            total_candidates_accepted=len(ranking.accepted),
            total_candidates_rejected=len(all_rejected),
            active_memory_count_before=current_active_count,
            active_memory_count_after=current_active_count,
        )
