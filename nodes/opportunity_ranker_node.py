"""AWPV2OpportunityRanker — ComfyUI node for ranking opportunity candidates."""

from __future__ import annotations
from typing import Any

from ..contracts.opportunity_result import OpportunityResult
from ..runtime.opportunity_ranker import OpportunityRanker


class AWPV2OpportunityRanker:
    """Rank opportunity candidates by priority."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "opportunity_result": ("OPPORTUNITY_RESULT", {}),
            },
        }

    RETURN_TYPES = ("OPPORTUNITY_RESULT",)
    RETURN_NAMES = ("ranked_result",)
    FUNCTION = "rank"
    CATEGORY = "AWP V2/Opportunity"

    def rank(self, opportunity_result: OpportunityResult) -> tuple:
        ranker = OpportunityRanker()
        accepted, rejected = ranker.rank(opportunity_result.candidates)
        opportunity_result.candidates = accepted
        for c in rejected:
            opportunity_result.rejected_candidates.append(
                type('RejectedCandidate', (), {
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
        opportunity_result.recommended_opportunity_ids = [
            c.candidate_id for c in accepted
        ]
        return (opportunity_result,)
