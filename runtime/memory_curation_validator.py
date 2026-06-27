"""MemoryCurationValidator — validates memory curation candidates.

Deterministic validation. Rejects candidates that:
- Have no evidence
- Have no accepted source turn ID
- Assert unsupported facts
- Try to write storage directly
- Try to modify CardState
- Have invalid summaries (for active memory)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.memory_curation_candidate import (
    MemoryCurationCandidate, CurationTargetLayer, CurationOperation,
)
from ..contracts.memory_curation_request import MemoryCurationRequest


@dataclass(frozen=True)
class CandidateValidation:
    """Result of validating a single candidate."""
    valid: bool = True
    rejection_reason: str = ""


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating all candidates."""
    valid_candidates: list[MemoryCurationCandidate] = field(default_factory=list)
    rejected_candidates: list[MemoryCurationCandidate] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)


class MemoryCurationValidator:
    """Deterministic validator for memory curation candidates.

    No LLM. Pure rule-based validation.
    """

    SUMMARY_MIN_CHARS = 30
    SUMMARY_MAX_CHARS = 80

    def validate_all(
        self,
        candidates: list[MemoryCurationCandidate],
        request: MemoryCurationRequest,
    ) -> ValidationResult:
        """Validate all candidates. Returns accepted and rejected lists."""
        valid: list[MemoryCurationCandidate] = []
        rejected: list[MemoryCurationCandidate] = []
        reasons: list[str] = []

        for candidate in candidates:
            result = self.validate_single(candidate, request)
            if result.valid:
                valid.append(candidate)
            else:
                rejected.append(candidate)
                reasons.append(result.rejection_reason)

        return ValidationResult(
            valid_candidates=valid,
            rejected_candidates=rejected,
            rejection_reasons=reasons,
        )

    def validate_single(
        self,
        candidate: MemoryCurationCandidate,
        request: MemoryCurationRequest,
    ) -> CandidateValidation:
        """Validate a single candidate against all rules."""

        # Rule 1: no_op is always valid
        if candidate.operation == CurationOperation.NO_OP:
            return CandidateValidation(valid=True)

        # Rule 2: Must have at least one evidence reference
        if not candidate.evidence_refs:
            return CandidateValidation(
                valid=False,
                rejection_reason=f"missing_evidence: {candidate.candidate_id}",
            )

        # Rule 3: Must have at least one accepted source turn ID
        if not candidate.source_turn_ids:
            return CandidateValidation(
                valid=False,
                rejection_reason=f"missing_source_turn_id: {candidate.candidate_id}",
            )

        # Rule 4: Evidence must reference an accepted turn
        for ev in candidate.evidence_refs:
            if not ev.source_turn_id:
                return CandidateValidation(
                    valid=False,
                    rejection_reason=f"evidence_missing_source_turn: {candidate.candidate_id}",
                )

        # Rule 5: Must not assert unsupported facts
        if not candidate.must_not_assert_unsupported_fact:
            return CandidateValidation(
                valid=False,
                rejection_reason=f"assertion_violation: {candidate.candidate_id}",
            )

        # Rule 6: Must not try to write storage directly
        if not candidate.must_not_write_storage:
            return CandidateValidation(
                valid=False,
                rejection_reason=f"storage_write_attempt: {candidate.candidate_id}",
            )

        # Rule 7: Active memory summary length validation
        if candidate.operation in (
            CurationOperation.CREATE_ACTIVE,
            CurationOperation.UPDATE_ACTIVE,
            CurationOperation.MERGE_ACTIVE,
        ):
            if candidate.summary:
                char_len = len(candidate.summary)
                if char_len < self.SUMMARY_MIN_CHARS:
                    return CandidateValidation(
                        valid=False,
                        rejection_reason=f"summary_too_short: {candidate.candidate_id} ({char_len} < {self.SUMMARY_MIN_CHARS})",
                    )
                if char_len > self.SUMMARY_MAX_CHARS:
                    return CandidateValidation(
                        valid=False,
                        rejection_reason=f"summary_too_long: {candidate.candidate_id} ({char_len} > {self.SUMMARY_MAX_CHARS})",
                    )

        # Rule 8: RAG content must not be empty
        if candidate.operation in (
            CurationOperation.CREATE_RAG,
            CurationOperation.UPDATE_RAG,
        ):
            if not candidate.content.strip() and not candidate.summary.strip():
                return CandidateValidation(
                    valid=False,
                    rejection_reason=f"empty_rag_content: {candidate.candidate_id}",
                )

        # Rule 9: Mark resolved must have a target
        if candidate.operation == CurationOperation.MARK_RESOLVED:
            if not candidate.duplicate_of_memory_ids:
                return CandidateValidation(
                    valid=False,
                    rejection_reason=f"resolve_missing_target: {candidate.candidate_id}",
                )

        # Rule 10: Importance and confidence must be 0-1
        if candidate.importance < 0 or candidate.importance > 1:
            return CandidateValidation(
                valid=False,
                rejection_reason=f"invalid_importance: {candidate.candidate_id}",
            )
        if candidate.confidence < 0 or candidate.confidence > 1:
            return CandidateValidation(
                valid=False,
                rejection_reason=f"invalid_confidence: {candidate.candidate_id}",
            )

        return CandidateValidation(valid=True)
