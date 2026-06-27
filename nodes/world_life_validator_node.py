"""AWPV2WorldLifeValidator — ComfyUI node for validating world-life candidates."""

from __future__ import annotations
from typing import Any

from ..contracts.world_life_result import WorldLifeResult
from ..contracts.round_snapshot import RoundSnapshot
from ..runtime.world_life_validator import WorldLifeValidator


class AWPV2WorldLifeValidator:
    """Validate world-life candidates against safety rules."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "world_life_result": ("WORLD_LIFE_RESULT", {}),
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
            },
        }

    RETURN_TYPES = ("WORLD_LIFE_RESULT",)
    RETURN_NAMES = ("validated_result",)
    FUNCTION = "validate"
    CATEGORY = "AWP V2/WorldLife"

    def validate(
        self,
        world_life_result: WorldLifeResult,
        round_snapshot: RoundSnapshot,
    ) -> tuple:
        validator = WorldLifeValidator()
        valid, rejected = validator.validate_batch(
            world_life_result.candidates, round_snapshot
        )
        # Update result with validated candidates
        world_life_result.candidates = valid
        for cand, errors in rejected:
            for error in errors:
                world_life_result.rejected_candidates.append(
                    type('RejectedWorldLifeCandidate', (), {
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
        return (world_life_result,)
