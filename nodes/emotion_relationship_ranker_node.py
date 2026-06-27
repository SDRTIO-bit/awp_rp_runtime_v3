"""AWPV2EmotionRelationshipRanker — ComfyUI node for ranking emotion/relationship candidates."""

from __future__ import annotations
from typing import Any

from ..contracts.emotion_relationship_result import EmotionRelationshipResult
from ..runtime.emotion_relationship_ranker import EmotionRelationshipRanker


class AWPV2EmotionRelationshipRanker:
    """Rank emotion/relationship candidates by priority."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "er_result": ("ER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("ER_RESULT",)
    RETURN_NAMES = ("ranked_result",)
    FUNCTION = "rank"
    CATEGORY = "AWP V2/EmotionRelationship"

    def rank(self, er_result: EmotionRelationshipResult) -> tuple:
        ranker = EmotionRelationshipRanker()
        accepted, rejected = ranker.rank(er_result.candidates)
        er_result.candidates = accepted
        for c in rejected:
            er_result.rejected_candidates.append(
                type('RejectedEmotionCandidate', (), {
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
        er_result.recommended_candidate_ids = [
            c.candidate_id for c in accepted
        ]
        return (er_result,)
