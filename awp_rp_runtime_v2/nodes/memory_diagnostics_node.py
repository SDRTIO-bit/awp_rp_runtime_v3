"""AWPV2MemoryDiagnostics — aggregate memory recall + commit diagnostics.

Output: MEMORY_DIAGNOSTICS (structured JSON).
"""

from __future__ import annotations

from typing import Any


class AWPV2MemoryDiagnostics:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
            "optional": {
                "active_commit_result": ("MEMORY_COMMIT_RESULT",),
                "rag_commit_result": ("MEMORY_COMMIT_RESULT",),
            },
        }

    RETURN_TYPES = ("MEMORY_DIAGNOSTICS",)
    RETURN_NAMES = ("memory_diagnostics",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"
    OUTPUT_SCHEMA_ID = "awp.rp.memory-diagnostics.v1"

    def execute(
        self,
        round_snapshot: dict[str, Any],
        active_commit_result: dict[str, Any] | None = None,
        rag_commit_result: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any]]:
        snapshot = round_snapshot or {}
        diagnostics = {
            "schema_id": "awp.rp.memory-diagnostics.v1",
            "card_id": snapshot.get("card_id", ""),
            "session_id": snapshot.get("session_id", ""),
            "recall_diagnostics": snapshot.get("memory_recall_diagnostics", []),
            "budget_decision": snapshot.get("memory_budget_decision", {}),
            "l1_turns_used": (snapshot.get("memory_budget_decision") or {}).get("l1_turns_used", 0),
            "active_memories_used": (snapshot.get("memory_budget_decision") or {}).get("active_memories_used", 0),
            "rag_used": (snapshot.get("memory_budget_decision") or {}).get("rag_used", 0),
            "active_commit": active_commit_result or None,
            "rag_commit": rag_commit_result or None,
        }
        return (diagnostics,)
