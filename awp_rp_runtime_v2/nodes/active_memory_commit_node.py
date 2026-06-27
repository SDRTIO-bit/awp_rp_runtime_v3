"""AWPV2ActiveMemoryCommit — formal L2 commit (gate-gated, idempotent).

Must explicitly receive: QualityDecision, CardStateCommitResult,
TurnRecordCommitResult, MemoryCommitPlan. Default no implicit side effects:
this node validates the gate and emits a structured result + diagnostics.
Actual persistence is performed by the ActiveMemoryCommitRuntime (orchestrator).
"""

from __future__ import annotations

from typing import Any


class AWPV2ActiveMemoryCommit:

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
    RETURN_NAMES = ("active_commit_result", "diagnostics")
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

        plan = MemoryCommitPlan.from_dict(memory_commit_plan or {})
        qd = QualityDecision.from_dict(quality_decision or {})
        cs_ok = bool((card_state_commit_result or {}).get("status") == "accepted") or \
            bool((card_state_commit_result or {}).get("success"))
        tr_ok = bool((turn_record_commit_result or {}).get("success")) or \
            bool((turn_record_commit_result or {}).get("turn_id"))

        request = MemoryCommitRequest(
            plan=plan,
            card_id=plan.card_id, session_id=plan.session_id, turn_id=plan.turn_id,
            trace_id=plan.trace_id,
            memory_commit_id=memory_commit_id or f"mc_{plan.turn_id}",
            idempotency_key=idempotency_key or f"{plan.turn_id}:active",
            quality_decision_ref=qd.trace_id,
            expected_card_state_revision=plan.expected_card_state_revision,
            card_state_commit_success=cs_ok,
            turn_record_commit_success=tr_ok,
        )

        status = MemoryCommitStatus.COMMITTED
        error = ""
        if qd is None or not qd.is_accepted():
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

        result = MemoryCommitResult(status=status, layer="active", error_message=error)
        diagnostics = {
            "schema_id": "awp.rp.memory-commit-diagnostics.v1",
            "layer": "active", "status": status,
            "card_state_commit_success": cs_ok,
            "turn_record_commit_success": tr_ok,
            "gate_accepted": bool(qd and qd.is_accepted()),
            "plan_turn_id": plan.turn_id,
            "new_active_count": len(plan.new_active_entries),
            "resolved_count": len(plan.resolved_active_ids),
            "error": error,
        }
        return (result.to_dict(), diagnostics)
