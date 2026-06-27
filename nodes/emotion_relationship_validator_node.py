"""AWPV2EmotionRelationshipValidator — ComfyUI node for validating emotion/relationship candidates."""

from __future__ import annotations
from typing import Any

from ..contracts.emotion_relationship_result import EmotionRelationshipResult
from ..runtime.emotion_relationship_validator import EmotionRelationshipValidator


class AWPV2EmotionRelationshipValidator:
    """Validate emotion/relationship candidates against safety rules."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "er_result": ("ER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("ER_VALIDATION_REPORT",)
    RETURN_NAMES = ("validation_report",)
    FUNCTION = "validate"
    CATEGORY = "AWP V2/EmotionRelationship"

    def validate(self, er_result: EmotionRelationshipResult) -> tuple:
        validator = EmotionRelationshipValidator()
        valid, rejected = validator.validate_batch(er_result.candidates, er_result)
        # Update result with validated candidates
        er_result.candidates = valid
        for cand, errors in rejected:
            for error in errors:
                er_result.rejected_candidates.append(
                    type('RejectedEmotionCandidate', (), {
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
        return (er_result,)
