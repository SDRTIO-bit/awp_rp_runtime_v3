"""AWPV2ActiveMemoryRecall — deterministic L2 recall.

Reads ONLY the current cardId+sessionId. Applies entity/status/importance/
confidence/query filters deterministically. Returns recall result + diagnostics.
"""

from __future__ import annotations

from typing import Any


class AWPV2ActiveMemoryRecall:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "active_memories": ("ACTIVE_MEMORIES",),
                "card_id": ("STRING",),
                "session_id": ("STRING",),
            },
            "optional": {
                "query": ("STRING", {"default": ""}),
                "entity_filter": ("STRING", {"default": ""}),
                "min_importance": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0}),
                "limit": ("INT", {"default": 15, "min": 1, "max": 15}),
            },
        }

    RETURN_TYPES = ("ACTIVE_RECALL", "MEMORY_DIAGNOSTICS")
    RETURN_NAMES = ("active_recall", "diagnostics")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"
    OUTPUT_SCHEMA_ID = "awp.rp.memory-recall-result.v1"

    def execute(
        self,
        active_memories: list,
        card_id: str,
        session_id: str,
        query: str = "",
        entity_filter: str = "",
        min_importance: float = 0.0,
        limit: int = 15,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        from ..contracts.active_memory import ActiveMemoryRecord, ActiveMemoryStatus
        from ..contracts.memory_recall_request import MemoryRecallRequest
        from ..contracts.memory_recall_result import MemoryRecallResult, RecallHit

        records = [
            (ActiveMemoryRecord.from_dict(m) if isinstance(m, dict) else m)
            for m in (active_memories or [])
        ]
        # Strict card+session isolation: drop anything not matching.
        records = [r for r in records if r.card_id == card_id and r.session_id == session_id]

        request = MemoryRecallRequest(
            card_id=card_id, session_id=session_id,
            query=query,
            entity_refs=[e.strip() for e in entity_filter.split(",") if e.strip()] if entity_filter else [],
            min_importance=min_importance, limit=limit,
        )

        stale = {
            ActiveMemoryStatus.RESOLVED.value, ActiveMemoryStatus.EXPIRED.value,
            ActiveMemoryStatus.CONFLICTED.value, ActiveMemoryStatus.SUPERSEDED.value,
            ActiveMemoryStatus.EVICTED.value,
        }
        hits, excluded = [], []
        for r in records:
            if request.exclude_stale and r.status in stale:
                excluded.append({"memory_id": r.memory_id, "reason": f"stale:{r.status}"})
                continue
            if r.importance < request.min_importance:
                excluded.append({"memory_id": r.memory_id, "reason": "low importance"})
                continue
            if request.entity_refs and not set(r.entity_refs) & set(request.entity_refs):
                excluded.append({"memory_id": r.memory_id, "reason": "entity filter miss"})
                continue
            if request.query and request.query.lower() not in r.summary.lower():
                excluded.append({"memory_id": r.memory_id, "reason": "query miss"})
                continue
            hits.append(r)
        hits.sort(key=lambda r: (r.importance, r.confidence, r.recall_count), reverse=True)
        limited = hits[:limit]
        hit_objs = [
            RecallHit(
                memory_id=r.memory_id, layer="active", score=r.importance,
                hit_reasons=["active_recall"], source_refs=list(r.source_turn_ids),
                importance=r.importance, confidence=r.confidence,
                status=r.status, summary=r.summary, content=r.summary,
                entity_refs=list(r.entity_refs),
            )
            for r in limited
        ]
        result = MemoryRecallResult(
            request=request, hits=hit_objs, excluded=excluded,
            ordered_by="importance DESC, confidence DESC, recall_count DESC",
            total_available=len(hits),
        )
        diagnostics = {
            "schema_id": "awp.rp.memory-recall-diagnostics.v1",
            "layer": "active", "card_id": card_id, "session_id": session_id,
            "hits": len(hit_objs), "excluded": len(excluded),
            "excluded_reasons": excluded,
            "ordered_by": result.ordered_by,
        }
        return (result.to_dict(), diagnostics)
