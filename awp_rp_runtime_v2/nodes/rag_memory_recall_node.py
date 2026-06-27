"""AWPV2RagMemoryRecall — deterministic L3 recall (FTS5-style keyword + filters).

Reads ONLY the current cardId+sessionId. Filters by entity/alias/tags/status/
scope/importance. resolved/expired/conflicted are downgraded by default.
"""

from __future__ import annotations

from typing import Any


class AWPV2RagMemoryRecall:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "rag_memories": ("RAG_MEMORIES",),
                "card_id": ("STRING",),
                "session_id": ("STRING",),
            },
            "optional": {
                "query": ("STRING", {"default": ""}),
                "entity_filter": ("STRING", {"default": ""}),
                "event_tag_filter": ("STRING", {"default": ""}),
                "min_confidence": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0}),
                "limit": ("INT", {"default": 10, "min": 1, "max": 50}),
            },
        }

    RETURN_TYPES = ("RAG_RECALL", "MEMORY_DIAGNOSTICS")
    RETURN_NAMES = ("rag_recall", "diagnostics")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"
    OUTPUT_SCHEMA_ID = "awp.rp.memory-recall-result.v1"

    def execute(
        self,
        rag_memories: list,
        card_id: str,
        session_id: str,
        query: str = "",
        entity_filter: str = "",
        event_tag_filter: str = "",
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        from ..contracts.rag_memory import RagMemoryRecord, RagMemoryStatus
        from ..contracts.memory_recall_request import MemoryRecallRequest
        from ..contracts.memory_recall_result import MemoryRecallResult, RecallHit

        records = [
            (RagMemoryRecord.from_dict(m) if isinstance(m, dict) else m)
            for m in (rag_memories or [])
        ]
        # Strict isolation: session scope must match; card_global must match card_id.
        isolated = []
        for r in records:
            if r.session_id != session_id:
                continue
            if r.scope == "card_global":
                if r.card_id != card_id:
                    continue
            isolated.append(r)

        request = MemoryRecallRequest(
            card_id=card_id, session_id=session_id, query=query,
            entity_refs=[e.strip() for e in entity_filter.split(",") if e.strip()] if entity_filter else [],
            event_tags=[t.strip() for t in event_tag_filter.split(",") if t.strip()] if event_tag_filter else [],
            min_confidence=min_confidence, limit=limit,
        )

        stale = {
            RagMemoryStatus.RESOLVED.value, RagMemoryStatus.EXPIRED.value,
            RagMemoryStatus.CONFLICTED.value, RagMemoryStatus.SUPERSEDED.value,
        }
        q = (query or "").lower()
        hits, excluded = [], []
        for r in isolated:
            if request.exclude_stale and r.status in stale:
                excluded.append({"memory_id": r.memory_id, "reason": f"stale:{r.status}"})
                continue
            if r.confidence < request.min_confidence:
                excluded.append({"memory_id": r.memory_id, "reason": "low confidence"})
                continue
            if q and not (q in r.content.lower() or q in r.summary.lower()
                          or any(q in a.lower() for a in r.aliases)):
                excluded.append({"memory_id": r.memory_id, "reason": "query miss"})
                continue
            if request.entity_refs and not (set(r.entity_refs) | set(r.aliases)) & set(request.entity_refs):
                excluded.append({"memory_id": r.memory_id, "reason": "entity filter miss"})
                continue
            if request.event_tags and not set(r.event_tags) & set(request.event_tags):
                excluded.append({"memory_id": r.memory_id, "reason": "event_tag miss"})
                continue
            hits.append(r)
        hits.sort(key=lambda e: (e.importance, e.confidence), reverse=True)
        limited = hits[:limit]
        hit_objs = [
            RecallHit(
                memory_id=e.memory_id, layer="rag",
                score=e.importance * 0.6 + e.confidence * 0.4,
                hit_reasons=["fts_match"] if q else ["active_recall"],
                source_refs=list(e.source_turn_ids), provenance=e.provenance,
                importance=e.importance, confidence=e.confidence,
                status=e.status, summary=e.summary, content=e.content,
                entity_refs=list(e.entity_refs),
            )
            for e in limited
        ]
        result = MemoryRecallResult(
            request=request, hits=hit_objs, excluded=excluded,
            ordered_by="fts_match then importance DESC, confidence DESC" if q
            else "importance DESC, confidence DESC",
            total_available=len(hits),
        )
        diagnostics = {
            "schema_id": "awp.rp.memory-recall-diagnostics.v1",
            "layer": "rag", "card_id": card_id, "session_id": session_id,
            "hits": len(hit_objs), "excluded": len(excluded),
            "excluded_reasons": excluded, "ordered_by": result.ordered_by,
        }
        return (result.to_dict(), diagnostics)
