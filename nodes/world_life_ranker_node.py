"""AWPV2WorldLifeRanker — ComfyUI node for ranking world-life candidates."""

from __future__ import annotations
from typing import Any

from ..contracts.world_life_result import WorldLifeResult
from ..runtime.world_life_ranker import WorldLifeRanker


class AWPV2WorldLifeRanker:
    """Rank world-life candidates by priority."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "world_life_result": ("WORLD_LIFE_RESULT", {}),
            },
        }

    RETURN_TYPES = ("WORLD_LIFE_RESULT",)
    RETURN_NAMES = ("ranked_result",)
    FUNCTION = "rank"
    CATEGORY = "AWP V2/WorldLife"

    def rank(self, world_life_result: WorldLifeResult) -> tuple:
        ranker = WorldLifeRanker()
        accepted, rejected = ranker.rank(world_life_result.candidates)
        world_life_result.candidates = accepted
        for c in rejected:
            world_life_result.rejected_candidates.append(
                type('RejectedWorldLifeCandidate', (), {
                    'candidate_id': c.candidate_id,
                    'reason': '被更高优先级候选淘汰',
                    'violated_policy': 'outranked',
                    'evidence_refs': c.evidence_refs,
                    'to_dict': lambda self: {
                        'candidate_id': self.candidate_id,
                        'reason': self.reason,
                        'violated_policy': self.violated_policy,
                        'evidence_refs': self.evidence_refs,
                    },
                })()
            )
        world_life_result.recommended_candidate_ids = [
            c.candidate_id for c in accepted
        ]
        return (world_life_result,)
