"""StateProposalRuntime — generates state update proposals.

Produces a CardStatePatch (candidate). Must be committed via CardStateCommitRuntime.
"""

from __future__ import annotations

from typing import Any

from ..contracts.card_state_patch import CardStatePatch, CardStatePatchOperation, PatchOpType
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.quality_decision import QualityDecision
from ..contracts.state_update_proposal import StateUpdateProposal


class StateProposalRuntime:

    def __init__(self, llm_provider: Any):
        self.llm_provider = llm_provider

    def generate(
        self,
        accepted_text: str,
        snapshot: RoundSnapshot,
        quality_decision: QualityDecision,
    ) -> CardStatePatch:
        """Generate a CardStatePatch from accepted text."""
        import uuid
        summary = (
            f"Card: {snapshot.card_id}, Session: {snapshot.session_id}, "
            f"Revision: {snapshot.base_card_state_revision}"
        )

        # Use LLM to get proposal (may return StateUpdateProposal)
        proposal = self.llm_provider.generate_state_proposal(accepted_text, summary)

        # Convert StateUpdateProposal → CardStatePatch
        operations = []
        if hasattr(proposal, 'operations'):
            for op in proposal.operations:
                # Map old PatchOp → new PatchOpType
                op_type_map = {
                    "set_variable": PatchOpType.SET,
                    "increment_variable": PatchOpType.INCREMENT,
                    "decrement_variable": PatchOpType.INCREMENT,
                    "set_event_flag": PatchOpType.SET_FLAG,
                    "clear_event_flag": PatchOpType.REMOVE,
                    "set_scene": PatchOpType.SET_SCENE_FIELD,
                    "add_active_stage": PatchOpType.ACTIVATE_STAGE,
                    "remove_active_stage": PatchOpType.DEACTIVATE_STAGE,
                }
                mapped = op_type_map.get(op.op.value if hasattr(op.op, 'value') else op.op)
                if mapped:
                    path = op.path
                    value = op.value
                    # Handle decrement as negative increment
                    if op.op.value == "decrement_variable" and isinstance(value, (int, float)):
                        value = -value
                    operations.append(CardStatePatchOperation(
                        op=mapped, path=path, value=value,
                        reason=getattr(op, 'reason', ''),
                    ))

        return CardStatePatch(
            patch_id=f"patch_{uuid.uuid4().hex[:12]}",
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            operations=operations,
            source="state_proposal_runtime",
            trace_id=snapshot.trace_id,
        )
