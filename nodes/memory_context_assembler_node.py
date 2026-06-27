"""AWPV2MemoryContextAssembler — assemble unified memory context.

Fixes priority: CardState > L1 > ActiveMemory > high-conf RAG > RAG > worldbook.
Deterministic conflict adjudication (stale/conflicted/ignored). No free LLM.
"""

from __future__ import annotations

from typing import Any


class AWPV2MemoryContextAssembler:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "card_state": ("CARD_STATE",),
                "l1_turns": ("TURN_RECORDS",),
                "active_recall": ("ACTIVE_RECALL",),
                "rag_recall": ("RAG_RECALL",),
            },
            "optional": {
                "worldbook_entries": ("WORLDBOOK_ENTRIES",),
                "conflict_entity": ("STRING", {"default": ""}),
                "conflict_negated_term": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("MEMORY_CONTEXT", "MEMORY_DIAGNOSTICS", "MEMORY_BUDGET")
    RETURN_NAMES = ("memory_context", "diagnostics", "budget")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"
    OUTPUT_SCHEMA_ID = "awp.rp.memory-context.v1"

    def execute(
        self,
        card_state: dict[str, Any],
        l1_turns: list,
        active_recall: dict[str, Any],
        rag_recall: dict[str, Any],
        worldbook_entries: list | None = None,
        conflict_entity: str = "",
        conflict_negated_term: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        from ..contracts.card_state import CardState
        from ..contracts.turn_record import TurnRecord
        from ..contracts.memory_recall_result import MemoryRecallResult
        from ..runtime.memory_context_assembler import (
            MemoryContextAssembler, ConflictSignal,
        )

        state = CardState.from_dict(card_state)
        turns = [TurnRecord.from_dict(t) if isinstance(t, dict) else t for t in (l1_turns or [])]
        active = MemoryRecallResult.from_dict(active_recall)
        rag = MemoryRecallResult.from_dict(rag_recall)

        signals = []
        if conflict_entity and conflict_negated_term:
            signals.append(ConflictSignal(
                entity_refs=[e.strip() for e in conflict_entity.split(",") if e.strip()],
                negated_terms=[conflict_negated_term],
                reason="conflicts_with_card_state",
            ))

        assembler = MemoryContextAssembler()
        ctx = assembler.assemble(
            card_state=state, l1_turns=turns,
            active_result=active, rag_result=rag,
            worldbook_entries=worldbook_entries,
            conflict_signals=signals,
        )
        diagnostics = {
            "schema_id": "awp.rp.memory-recall-diagnostics.v1",
            "entries": ctx.diagnostics,
            "priority_order": ctx.priority_order,
        }
        return (ctx.to_dict(), diagnostics, ctx.budget.to_dict())
