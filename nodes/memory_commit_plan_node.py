"""AWPV2MemoryCommitPlan — build a deterministic MemoryCommitPlan.

M1 uses a deterministic fixture (FakeMemoryCurationAdapter). The Memory
Curator is NOT a free dynamic subagent yet — it may only PROPOSE a plan; the
final write still goes through the commit runtime.
"""

from __future__ import annotations

from typing import Any


class AWPV2MemoryCommitPlan:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT",),
                "accepted_text": ("STRING",),
                "quality_decision": ("QUALITY_DECISION",),
                "turn_id": ("STRING",),
            },
            "optional": {
                "trace_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("MEMORY_COMMIT_PLAN",)
    RETURN_NAMES = ("memory_commit_plan",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"
    OUTPUT_SCHEMA_ID = "awp.rp.memory-commit-plan.v1"

    def execute(
        self,
        round_snapshot: dict[str, Any],
        accepted_text: str,
        quality_decision: dict[str, Any],
        turn_id: str,
        trace_id: str = "",
    ) -> tuple[dict[str, Any]]:
        from ..contracts.memory_commit_plan import MemoryCommitPlan
        from ..contracts.rag_memory import RagMemoryRecord

        snapshot = round_snapshot or {}
        card_id = snapshot.get("card_id", "")
        session_id = snapshot.get("session_id", "")
        base_rev = snapshot.get("base_card_state_revision", 0)
        qd = quality_decision or {}

        summary = (accepted_text or "")[:80]
        rag_entry = RagMemoryRecord(
            memory_id=f"rag_{turn_id}",
            card_id=card_id, session_id=session_id, scope="session",
            content=accepted_text or "", summary=summary,
            source_turn_ids=[turn_id],
            source_card_state_revision=base_rev,
            importance=0.5, confidence=0.6,
            provenance=f"commit:{turn_id}", evidence=[turn_id],
        )
        plan = MemoryCommitPlan(
            turn_id=turn_id, card_id=card_id, session_id=session_id,
            trace_id=trace_id or qd.get("trace_id", ""),
            expected_card_state_revision=base_rev,
            quality_decision_ref=qd.get("trace_id", ""),
            new_rag_entries=[rag_entry],
            write_reasons=["accepted_turn_long_term_record"],
        )
        return (plan.to_dict(),)
