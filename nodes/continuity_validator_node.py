"""AWPV2ContinuityValidator — ComfyUI node for validating ContinuityResult."""

from __future__ import annotations
from typing import Any

from ..contracts.continuity_result import ContinuityResult
from ..contracts.continuity_evidence import ContinuityEvidence
from ..runtime.continuity_validator import ContinuityValidator


class AWPV2ContinuityValidator:
    """Validate continuity issues for correctness and safety."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "continuity_result": ("CONTINUITY_RESULT", {}),
            },
        }

    RETURN_TYPES = ("CONTINUITY_RESULT", "STRING")
    RETURN_NAMES = ("validated_result", "validation_summary")
    FUNCTION = "validate"
    CATEGORY = "AWP V2/Continuity"

    def validate(self, continuity_result: ContinuityResult) -> tuple:
        validator = ContinuityValidator()

        # Collect all evidence IDs from issues
        all_evidence: list[ContinuityEvidence] = []
        for issue in continuity_result.issues:
            for ref in issue.evidence_refs:
                all_evidence.append(ContinuityEvidence(
                    evidence_id=ref,
                    source_type=_ref_to_source_type(ref),
                ))

        # Validate each issue
        valid, rejected = validator.validate_batch(
            continuity_result.issues, all_evidence,
        )

        # Build summary
        summary_parts = [
            f"验证通过: {len(valid)}",
            f"验证拒绝: {len(rejected)}",
        ]
        if rejected:
            for issue, errors in rejected[:3]:
                summary_parts.append(f"拒绝: {issue.issue_id} - {errors[0][:50]}")

        # Return the original result (validation is informational)
        return (continuity_result, " | ".join(summary_parts))


def _ref_to_source_type(ref: str):
    """Infer source type from evidence ref prefix."""
    from ..contracts.continuity_evidence import EvidenceSourceType
    if ref.startswith("cardstate:"):
        return EvidenceSourceType.CARD_STATE
    elif ref.startswith("turn:"):
        return EvidenceSourceType.ACCEPTED_TURN
    elif ref.startswith("am:"):
        return EvidenceSourceType.ACTIVE_MEMORY
    elif ref.startswith("rag:"):
        return EvidenceSourceType.RAG_MEMORY
    elif ref.startswith("worldbook:"):
        return EvidenceSourceType.WORLDBOOK
    return EvidenceSourceType.TOOL_RESULT
