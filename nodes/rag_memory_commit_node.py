"""AWPV2RagMemoryCommit — formal L3 commit (gate-gated, idempotent).

Must explicitly receive: QualityDecision, CardStateCommitResult,
TurnRecordCommitResult, MemoryCommitPlan. Default no implicit side effects.
Enforces session scope default + no cross-cardId sharing.
"""

from __future__ import annotations

from typing import Any


class AWPV2RagMemoryCommit:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "memory_commit_plan": ("MEMORY_COMMIT_PLAN",),
                "quality_decision": ("QUALITY_DECISION",),
                "card_state_commit_result": ("CARD_STATE_COMMIT_RESULT",),
                "turn_record_commit_result": ("TURN_RECORD_COMMIT_RESULT",),
            },
            "optional": {
                "memory_commit_id": ("STRING", {"default": ""}),
                "idempotency_key": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("MEMORY_COMMIT_RESULT", "MEMORY_DIAGNOSTICS")
    RETURN_NAMES = ("rag_commit_result", "diagnostics")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"
    OUTPUT_SCHEMA_ID = "awp.rp.memory-commit-result.v1"

    def execute(
        self,
        memory_commit_plan: dict[str, Any],
        quality_decision: dict[str, Any],
        card_state_commit_result: dict[str, Any],
        turn_record_commit_result: dict[str, Any],
        memory_commit_id: str = "",
        idempotency_key: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        from ..contracts.memory_commit_plan import (
            MemoryCommitPlan, MemoryCommitRequest, MemoryCommitResult, MemoryCommitStatus,
        )
        from ..contracts.quality_decision import QualityDecision
        from ..contracts.rag_memory import RagMemoryScope

        plan = MemoryCommitPlan.from_dict(memory_commit_plan or {})
        qd = QualityDecision.from_dict(quality_decision or {})
        cs_ok = bool((card_state_commit_result or {}).get("status") == "accepted") or \
            bool((card_state_commit_result or {}).get("success"))
        tr_ok = bool((turn_record_commit_result or {}).get("success")) or \
            bool((turn_record_commit_result or {}).get("turn_id"))

        status = MemoryCommitStatus.COMMITTED
        error = ""
        if not qd or not qd.is_accepted():
            status = MemoryCommitStatus.BLOCKED_GATE_NOT_ACCEPT
            error = f"gate not accept: {qd.verdict.value if qd else 'none'}"
        elif plan.trace_id and qd.trace_id and plan.trace_id != qd.trace_id:
            status = MemoryCommitStatus.BLOCKED_TRACE_MISMATCH
            error = "trace mismatch"
        elif not cs_ok:
            status = MemoryCommitStatus.BLOCKED_CARD_STATE
            error = "CardStateCommit did not succeed"
        elif not tr_ok:
            status = MemoryCommitStatus.BLOCKED_TURN_RECORD
            error = "TurnRecordCommit did not succeed"
        else:
            for entry in plan.new_rag_entries:
                if entry.scope == RagMemoryScope.CARD_GLOBAL.value and \
                        entry.card_id and entry.card_id != plan.card_id:
                    status = MemoryCommitStatus.BLOCKED_VALIDATION
                    error = f"card_global crosses cardId: {entry.memory_id}"
                    break

        result = MemoryCommitResult(status=status, layer="rag", error_message=error)
        diagnostics = {
            "schema_id": "awp.rp.memory-commit-diagnostics.v1",
            "layer": "rag", "status": status,
            "card_state_commit_success": cs_ok,
            "turn_record_commit_success": tr_ok,
            "gate_accepted": bool(qd and qd.is_accepted()),
            "plan_turn_id": plan.turn_id,
            "new_rag_count": len(plan.new_rag_entries),
            "scopes": [e.scope for e in plan.new_rag_entries],
            "error": error,
        }
        return (result.to_dict(), diagnostics)
