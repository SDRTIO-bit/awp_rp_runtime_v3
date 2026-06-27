"""StateUpdateProposalNode — generates state update proposal.

Input: quality_decision, candidate_text, round_snapshot
Output: state_update_proposal
"""

from __future__ import annotations

from typing import Any


class StateUpdateProposalNode:
    """Generate state update proposal from accepted text."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "quality_decision": ("QUALITY_DECISION",),
                "candidate_text": ("STRING",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
        }

    RETURN_TYPES = ("STATE_UPDATE_PROPOSAL",)
    RETURN_NAMES = ("state_update_proposal",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        quality_decision: dict[str, Any],
        candidate_text: str,
        round_snapshot: dict[str, Any],
    ) -> tuple[dict[str, Any]]:
        """Generate state update proposal."""
        from ..contracts.quality_decision import QualityDecision
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.state_update_proposal import StateUpdateProposal
        from ..testing.fakes.fake_llm import FakeLLMProvider
        from ..runtime.state_proposal_runtime import StateProposalRuntime

        decision = QualityDecision.from_dict(quality_decision)
        snapshot = RoundSnapshot.from_dict(round_snapshot)

        llm = FakeLLMProvider()
        runtime = StateProposalRuntime(llm)
        proposal = runtime.generate(candidate_text, snapshot, decision)

        return (proposal.to_dict(),)
