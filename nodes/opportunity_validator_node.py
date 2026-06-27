"""AWPV2OpportunityValidator — ComfyUI node for validating opportunity candidates."""

from __future__ import annotations
from typing import Any

from ..contracts.opportunity_result import OpportunityResult
from ..contracts.round_snapshot import RoundSnapshot
from ..runtime.opportunity_validator import OpportunityValidator


class AWPV2OpportunityValidator:
    """Validate opportunity candidates against safety rules."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "opportunity_result": ("OPPORTUNITY_RESULT", {}),
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
            },
        }

    RETURN_TYPES = ("OPPORTUNITY_RESULT",)
    RETURN_NAMES = ("validated_result",)
    FUNCTION = "validate"
    CATEGORY = "AWP V2/Opportunity"

    def validate(
        self,
        opportunity_result: OpportunityResult,
        round_snapshot: RoundSnapshot,
    ) -> tuple:
        validator = OpportunityValidator()
        valid, rejected = validator.validate_batch(
            opportunity_result.candidates, round_snapshot
        )
        # Update result with validated candidates
        opportunity_result.candidates = valid
        for cand, errors in rejected:
            for error in errors:
                opportunity_result.rejected_candidates.append(
                    type('RejectedCandidate', (), {
                        'candidate_id': cand.candidate_id,
                        'reason': error,
                        'violated_policy': 'validation',
                        'evidence_refs': cand.evidence_refs,
                        'to_dict': lambda self: {
                            'candidate_id': self.candidate_id,
                            'reason': self.reason,
                            'violated_policy': self.violated_policy,
                            'evidence_refs': self.evidence_refs,
                        },
                    })()
                )
        return (opportunity_result,)
