"""SQLite implementation of RagMemoryStore with FTS5 retrieval."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ..interfaces import RagMemoryStore
from ...contracts.rag_memory import RagMemoryRecord, RagMemoryEntry, RagMemoryStatus, RagMemoryScope
from ...contracts.memory_commit_plan import MemoryCommitReceipt
from ...contracts.memory_recall_request import MemoryRecallRequest
from ...contracts.memory_recall_result import MemoryRecallResult, RecallHit
from .database import Database

_STALE_STATUSES = {
    RagMemoryStatus.RESOLVED.value,
    RagMemoryStatus.EXPIRED.value,
    RagMemoryStatus.CONFLICTED.value,
    RagMemoryStatus.SUPERSEDED.value,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteRagMemoryStore(RagMemoryStore):
    """SQLite-backed RAG memory store with FTS5."""

    def __init__(self, db: Database):
        self.db = db

    # ---- basic CRUD ----
    def save(self, card_id: str, session_id: str, entry: RagMemoryEntry) -> None:
        """Save a RAG memory entry + index it in FTS5."""
        conn = self.db.connect()
        data = entry.to_dict()
        aliases_text = " ".join(entry.aliases)
        tags = {
            "event_tags": entry.event_tags,
            "location_tags": entry.location_tags,
            "time_tags": entry.time_tags,
            "relationship_tags": entry.relationship_tags,
        }
        conn.execute(
            "INSERT OR REPLACE INTO rag_memory_records "
            "(memory_id, card_id, session_id, memory_json, created_at, "
            " scope, status, summary, importance, confidence, "
            " source_card_state_revision, source_turn_ids_json, entity_refs_json, "
            " aliases_json, tags_json, updated_at, last_recalled_at, recall_count, provenance) "
            "VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM rag_memory_records WHERE memory_id=?), datetime('now')), "
            " ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.memory_id, card_id, session_id,
                json.dumps(data, ensure_ascii=False), entry.memory_id,
                entry.scope, entry.status, entry.summary,
                entry.importance, entry.confidence,
                entry.source_card_state_revision,
                json.dumps(entry.source_turn_ids, ensure_ascii=False),
                json.dumps(entry.entity_refs, ensure_ascii=False),
                json.dumps(entry.aliases, ensure_ascii=False),
                json.dumps(tags, ensure_ascii=False),
                _now(), entry.last_recalled_at, entry.recall_count, entry.provenance,
            ),
        )
        # Sync FTS5 (delete + insert to keep idempotent).
        conn.execute("DELETE FROM rag_memory_fts WHERE memory_id=?", (entry.memory_id,))
        conn.execute(
            "INSERT INTO rag_memory_fts (memory_id, card_id, session_id, content, summary, aliases) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry.memory_id, card_id, session_id,
                entry.content, entry.summary, aliases_text,
            ),
        )
        conn.commit()

    def search(
        self,
        card_id: str,
        session_id: str,
        query: str,
        limit: int = 10,
    ) -> list[RagMemoryEntry]:
        """FTS5 keyword search with LIKE fallback for CJK, scoped to card+session."""
        conn = self.db.connect()
        fts_query = _to_fts_query(query)
        rows: list = []
        if fts_query:
            try:
                rows = conn.execute(
                    "SELECT r.memory_json FROM rag_memory_fts f "
                    "JOIN rag_memory_records r ON r.memory_id = f.memory_id "
                    "WHERE f.card_id=? AND f.session_id=? AND rag_memory_fts MATCH ? "
                    "ORDER BY r.importance DESC, r.confidence DESC, r.created_at DESC LIMIT ?",
                    (card_id, session_id, fts_query, limit),
                ).fetchall()
            except Exception:
                rows = []
        # LIKE fallback: split query into individual terms and OR them.
        if not rows and query:
            tokens = [t.strip() for t in query.split() if t.strip()]
            if tokens:
                conditions = " OR ".join(
                    ["memory_json LIKE ?" for _ in tokens]
                )
                params = [card_id, session_id] + [f"%{t}%" for t in tokens] + [limit]
                rows = conn.execute(
                    "SELECT memory_json FROM rag_memory_records "
                    "WHERE card_id=? AND session_id=? AND status='active' "
                    f"AND ({conditions}) "
                    "ORDER BY importance DESC, confidence DESC, created_at DESC LIMIT ?",
                    params,
                ).fetchall()
        elif not rows:
            rows = conn.execute(
                "SELECT memory_json FROM rag_memory_records "
                "WHERE card_id=? AND session_id=? AND status='active' "
                "ORDER BY importance DESC, confidence DESC, created_at DESC LIMIT ?",
                (card_id, session_id, limit),
            ).fetchall()
        return [RagMemoryRecord.from_dict(json.loads(r["memory_json"])) for r in rows]

    def get_by_entity(
        self, card_id: str, session_id: str, entity: str
    ) -> list[RagMemoryEntry]:
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT memory_json FROM rag_memory_records "
            "WHERE card_id=? AND session_id=? "
            "AND (entity_refs_json LIKE ? OR aliases_json LIKE ?) "
            "ORDER BY importance DESC, created_at DESC",
            (card_id, session_id, f'%"{entity}"%', f'%"{entity}"%'),
        ).fetchall()
        return [RagMemoryRecord.from_dict(json.loads(r["memory_json"])) for r in rows]

    # ---- lifecycle / recall stats ----
    def set_status(
        self, card_id: str, session_id: str, memory_id: str, status: str
    ) -> None:
        conn = self.db.connect()
        resolved_at = _now() if status == RagMemoryStatus.RESOLVED.value else ""
        conn.execute(
            "UPDATE rag_memory_records SET status=?, "
            "resolved_at=COALESCE(NULLIF(?, ''), resolved_at), updated_at=? "
            "WHERE memory_id=? AND card_id=? AND session_id=?",
            (status, resolved_at, _now(), memory_id, card_id, session_id),
        )
        conn.commit()

    def touch_recall(self, card_id: str, session_id: str, memory_id: str) -> None:
        conn = self.db.connect()
        conn.execute(
            "UPDATE rag_memory_records SET last_recalled_at=?, "
            "recall_count=recall_count+1 WHERE memory_id=? AND card_id=? AND session_id=?",
            (_now(), memory_id, card_id, session_id),
        )
        conn.commit()

    # ---- recall ----
    def recall(
        self, card_id: str, session_id: str, request: MemoryRecallRequest
    ) -> MemoryRecallResult:
        conn = self.db.connect()
        fts_query = _to_fts_query(request.query)

        # Base candidate set: FTS5 hits with LIKE fallback (CJK 2-char tokens).
        rows: list = []
        base_score: dict = {}
        if fts_query:
            try:
                rows = conn.execute(
                    "SELECT r.memory_json, r.memory_id, bm25(rag_memory_fts) AS score FROM rag_memory_fts f "
                    "JOIN rag_memory_records r ON r.memory_id = f.memory_id "
                    "WHERE f.card_id=? AND f.session_id=? AND rag_memory_fts MATCH ? "
                    "ORDER BY score",
                    (card_id, session_id, fts_query),
                ).fetchall()
                base_score = {r["memory_id"]: _b25_to_score(r["score"]) for r in rows}
            except Exception:
                rows = []
        if not rows and request.query:
            # LIKE fallback: split query into individual tokens and OR them.
            tokens = [t.strip() for t in request.query.split() if t.strip()]
            if tokens:
                conditions = " OR ".join(["memory_json LIKE ?" for _ in tokens])
                params = [card_id, session_id] + [f"%{t}%" for t in tokens]
                rows = conn.execute(
                    "SELECT memory_json FROM rag_memory_records "
                    "WHERE card_id=? AND session_id=? "
                    f"AND ({conditions}) "
                    "ORDER BY importance DESC, confidence DESC, created_at DESC",
                    params,
                ).fetchall()
            else:
                q = f"%{request.query}%"
                rows = conn.execute(
                    "SELECT memory_json FROM rag_memory_records "
                    "WHERE card_id=? AND session_id=? "
                    "AND (memory_json LIKE ?) "
                    "ORDER BY importance DESC, confidence DESC, created_at DESC",
                    (card_id, session_id, q),
                ).fetchall()
        elif not rows:
            rows = conn.execute(
                "SELECT memory_json FROM rag_memory_records "
                "WHERE card_id=? AND session_id=? "
                "ORDER BY importance DESC, confidence DESC, created_at DESC",
                (card_id, session_id),
            ).fetchall()

        records = [RagMemoryRecord.from_dict(json.loads(r["memory_json"])) for r in rows]
        hits, excluded = _filter_rag(records, request, base_score)
        ordered = _order_rag(hits, base_score)
        limited = ordered[: request.limit]
        for h in limited:
            self.touch_recall(card_id, session_id, h.memory_id)

        hit_objs = [
            RecallHit(
                memory_id=r.memory_id, layer="rag",
                score=base_score.get(r.memory_id, _rank_score(r)),
                hit_reasons=_hit_reasons(r, request, fts_query),
                source_refs=list(r.source_turn_ids),
                provenance=r.provenance,
                importance=r.importance, confidence=r.confidence,
                status=r.status, summary=r.summary, content=r.content,
                entity_refs=list(r.entity_refs),
            )
            for r in limited
        ]
        return MemoryRecallResult(
            request=request,
            hits=hit_objs,
            excluded=excluded,
            ordered_by="bm25 ASC then importance DESC, confidence DESC" if fts_query
            else "importance DESC, confidence DESC, created_at DESC",
            total_available=len(hits),
        )

    # ---- receipts ----
    def record_receipt(self, receipt: MemoryCommitReceipt) -> None:
        conn = self.db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO rag_memory_commit_receipts "
            "(memory_commit_id, idempotency_key, turn_id, card_id, session_id, trace_id, "
            " expected_card_state_revision, quality_decision_ref, "
            " committed_rag_ids_json, committed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                receipt.memory_commit_id, receipt.idempotency_key, receipt.turn_id,
                receipt.card_id, receipt.session_id, receipt.trace_id,
                receipt.expected_card_state_revision, receipt.quality_decision_ref,
                json.dumps(list(receipt.committed_rag_ids), ensure_ascii=False),
                receipt.committed_at or _now(),
            ),
        )
        conn.commit()

    def get_receipt_by_idempotency_key(
        self, card_id: str, session_id: str, idempotency_key: str
    ) -> MemoryCommitReceipt | None:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT * FROM rag_memory_commit_receipts "
            "WHERE card_id=? AND session_id=? AND idempotency_key=?",
            (card_id, session_id, idempotency_key),
        ).fetchone()
        if not row:
            return None
        return MemoryCommitReceipt(
            memory_commit_id=row["memory_commit_id"],
            idempotency_key=row["idempotency_key"],
            turn_id=row["turn_id"],
            card_id=row["card_id"],
            session_id=row["session_id"],
            trace_id=row["trace_id"],
            expected_card_state_revision=row["expected_card_state_revision"],
            quality_decision_ref=row["quality_decision_ref"],
            committed_rag_ids=json.loads(row["committed_rag_ids_json"]),
            committed_at=row["committed_at"],
        )


def _to_fts_query(query: str) -> str:
    """Convert a free-text query into a safe FTS5 query."""
    if not query:
        return ""
    tokens = [t for t in query.replace('"', " ").split() if t]
    if not tokens:
        return ""
    return " ".join(f'"{t}"' for t in tokens)


def _b25_to_score(bm25: float) -> float:
    """bm25 is negative (lower = better match). Convert to 0..1 positive score."""
    try:
        v = float(bm25)
    except (TypeError, ValueError):
        return 0.0
    # bm25 typical range -0.1 .. -10; map to 1.0 .. 0.0
    return max(0.0, min(1.0, 1.0 + v / 10.0))


def _rank_score(r: RagMemoryRecord) -> float:
    return r.importance * 0.6 + r.confidence * 0.4


def _hit_reasons(r: RagMemoryRecord, request: MemoryRecallRequest, fts_query: str) -> list[str]:
    reasons: list[str] = []
    if fts_query:
        reasons.append("fts_match")
    shared = set(r.entity_refs) & set(request.entity_refs)
    if shared:
        reasons.append(f"entity:{sorted(shared)}")
    shared_alias = set(r.aliases) & set(request.aliases)
    if shared_alias:
        reasons.append(f"alias:{sorted(shared_alias)}")
    if not reasons:
        reasons.append("active_recall")
    return reasons


def _filter_rag(records, request: MemoryRecallRequest, base_score):
    hits = []
    excluded = []
    statuses = set(request.statuses) if request.statuses else {"active"}
    for r in records:
        if r.status not in statuses:
            if request.exclude_stale and r.status in _STALE_STATUSES:
                excluded.append({"memory_id": r.memory_id, "reason": f"stale:{r.status}"})
            else:
                excluded.append({"memory_id": r.memory_id, "reason": f"status={r.status}"})
            continue
        if request.exclude_stale and r.status in _STALE_STATUSES:
            excluded.append({"memory_id": r.memory_id, "reason": f"stale:{r.status}"})
            continue
        if request.scope and r.scope != request.scope:
            excluded.append({"memory_id": r.memory_id, "reason": "scope_mismatch"})
            continue
        if r.scope == RagMemoryScope.CARD_GLOBAL.value and r.card_id != request.card_id:
            excluded.append({"memory_id": r.memory_id, "reason": "card_scope_mismatch"})
            continue
        if r.importance < request.min_importance:
            excluded.append({"memory_id": r.memory_id, "reason": "low importance"})
            continue
        if r.confidence < request.min_confidence:
            excluded.append({"memory_id": r.memory_id, "reason": "low confidence"})
            continue
        if request.entity_refs and not (set(r.entity_refs) | set(r.aliases)) & set(request.entity_refs):
            excluded.append({"memory_id": r.memory_id, "reason": "entity filter miss"})
            continue
        if request.aliases and not set(r.aliases) & set(request.aliases):
            excluded.append({"memory_id": r.memory_id, "reason": "alias filter miss"})
            continue
        if request.event_tags and not set(r.event_tags) & set(request.event_tags):
            excluded.append({"memory_id": r.memory_id, "reason": "event_tag miss"})
            continue
        if request.location_tags and not set(r.location_tags) & set(request.location_tags):
            excluded.append({"memory_id": r.memory_id, "reason": "location_tag miss"})
            continue
        hits.append(r)
    return hits, excluded


def _order_rag(records, base_score):
    def key(r):
        s = base_score.get(r.memory_id, _rank_score(r))
        return (s, r.importance, r.confidence)
    return sorted(records, key=key, reverse=True)
