"""SQLite implementation of ActiveMemoryStore."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ..interfaces import ActiveMemoryStore
from ...contracts.active_memory import ActiveMemoryRecord, ActiveMemoryEntry, ActiveMemoryStatus
from ...contracts.memory_commit_plan import MemoryCommitReceipt
from ...contracts.memory_recall_request import MemoryRecallRequest
from ...contracts.memory_recall_result import MemoryRecallResult, RecallHit
from .database import Database

_STALE_STATUSES = {
    ActiveMemoryStatus.RESOLVED.value,
    ActiveMemoryStatus.EXPIRED.value,
    ActiveMemoryStatus.CONFLICTED.value,
    ActiveMemoryStatus.SUPERSEDED.value,
    ActiveMemoryStatus.EVICTED.value,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteActiveMemoryStore(ActiveMemoryStore):
    """SQLite-backed active memory store."""

    def __init__(self, db: Database):
        self.db = db

    # ---- basic CRUD ----
    def get_all(self, card_id: str, session_id: str) -> list[ActiveMemoryEntry]:
        """Get all active memories for a card+session (active status only)."""
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT memory_json FROM active_memory_records "
            "WHERE card_id=? AND session_id=? AND status='active' "
            "ORDER BY importance DESC, updated_at DESC",
            (card_id, session_id),
        ).fetchall()
        return [ActiveMemoryRecord.from_dict(json.loads(r["memory_json"])) for r in rows]

    def get_all_records(self, card_id: str, session_id: str) -> list[ActiveMemoryRecord]:
        """Get ALL records regardless of status (for retention decisions)."""
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT memory_json FROM active_memory_records "
            "WHERE card_id=? AND session_id=? "
            "ORDER BY status, importance DESC, updated_at DESC",
            (card_id, session_id),
        ).fetchall()
        return [ActiveMemoryRecord.from_dict(json.loads(r["memory_json"])) for r in rows]

    def upsert(self, card_id: str, session_id: str, entry: ActiveMemoryEntry) -> None:
        """Insert or update an active memory entry."""
        conn = self.db.connect()
        data = entry.to_dict()
        conn.execute(
            "INSERT OR REPLACE INTO active_memory_records "
            "(memory_id, card_id, session_id, memory_json, status, updated_at, "
            " kind, summary, importance, confidence, source_card_state_revision, "
            " source_turn_ids_json, entity_refs_json, created_at, last_recalled_at, "
            " recall_count, resolved_at, expires_at, eviction_reason, retention_reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.memory_id, card_id, session_id, json.dumps(data, ensure_ascii=False),
                entry.status, _now(),
                entry.kind, entry.summary, entry.importance, entry.confidence,
                entry.source_card_state_revision,
                json.dumps(entry.source_turn_ids, ensure_ascii=False),
                json.dumps(entry.entity_refs, ensure_ascii=False),
                entry.created_at or _now(), entry.last_recalled_at, entry.recall_count,
                entry.resolved_at, entry.expires_at, entry.eviction_reason, entry.retention_reason,
            ),
        )
        conn.commit()

    def resolve(self, card_id: str, session_id: str, memory_id: str) -> None:
        self.set_status(card_id, session_id, memory_id, ActiveMemoryStatus.RESOLVED.value)

    def delete(self, card_id: str, session_id: str, memory_id: str) -> None:
        conn = self.db.connect()
        conn.execute(
            "DELETE FROM active_memory_records "
            "WHERE memory_id=? AND card_id=? AND session_id=?",
            (memory_id, card_id, session_id),
        )
        conn.commit()

    # ---- lifecycle / recall stats ----
    def get_active_count(self, card_id: str, session_id: str) -> int:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM active_memory_records "
            "WHERE card_id=? AND session_id=? AND status='active'",
            (card_id, session_id),
        ).fetchone()
        return int(row["c"])

    def set_status(
        self, card_id: str, session_id: str, memory_id: str, status: str, reason: str = ""
    ) -> None:
        conn = self.db.connect()
        resolved_at = _now() if status == ActiveMemoryStatus.RESOLVED.value else ""
        conn.execute(
            "UPDATE active_memory_records SET status=?, eviction_reason=?, "
            "resolved_at=COALESCE(NULLIF(?, ''), resolved_at), updated_at=? "
            "WHERE memory_id=? AND card_id=? AND session_id=?",
            (status, reason, resolved_at, _now(), memory_id, card_id, session_id),
        )
        conn.commit()

    def touch_recall(self, card_id: str, session_id: str, memory_id: str) -> None:
        conn = self.db.connect()
        conn.execute(
            "UPDATE active_memory_records SET last_recalled_at=?, "
            "recall_count=recall_count+1 WHERE memory_id=? AND card_id=? AND session_id=?",
            (_now(), memory_id, card_id, session_id),
        )
        conn.commit()

    # ---- recall ----
    def recall(
        self, card_id: str, session_id: str, request: MemoryRecallRequest
    ) -> MemoryRecallResult:
        records = self.get_all(card_id, session_id)
        hits, excluded = _filter_active(records, request)
        ordered = _order_active(hits)
        limited = ordered[: request.limit]
        for h in limited:
            self.touch_recall(card_id, session_id, h.memory_id)
        return MemoryRecallResult(
            request=request,
            hits=limited,
            excluded=excluded,
            ordered_by="importance DESC, confidence DESC, recall_count DESC",
            total_available=len(hits),
        )

    # ---- receipts ----
    def record_receipt(self, receipt: MemoryCommitReceipt) -> None:
        conn = self.db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO active_memory_commit_receipts "
            "(memory_commit_id, idempotency_key, turn_id, card_id, session_id, trace_id, "
            " expected_card_state_revision, quality_decision_ref, "
            " committed_active_ids_json, evicted_active_ids_json, committed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                receipt.memory_commit_id, receipt.idempotency_key, receipt.turn_id,
                receipt.card_id, receipt.session_id, receipt.trace_id,
                receipt.expected_card_state_revision, receipt.quality_decision_ref,
                json.dumps(list(receipt.committed_active_ids), ensure_ascii=False),
                json.dumps(list(receipt.evicted_active_ids), ensure_ascii=False),
                receipt.committed_at or _now(),
            ),
        )
        conn.commit()

    def get_receipt_by_idempotency_key(
        self, card_id: str, session_id: str, idempotency_key: str
    ) -> MemoryCommitReceipt | None:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT * FROM active_memory_commit_receipts "
            "WHERE card_id=? AND session_id=? AND idempotency_key=?",
            (card_id, session_id, idempotency_key),
        ).fetchone()
        if not row:
            return None
        return _receipt_from_row(row)


def _receipt_from_row(row) -> MemoryCommitReceipt:
    return MemoryCommitReceipt(
        memory_commit_id=row["memory_commit_id"],
        idempotency_key=row["idempotency_key"],
        turn_id=row["turn_id"],
        card_id=row["card_id"],
        session_id=row["session_id"],
        trace_id=row["trace_id"],
        expected_card_state_revision=row["expected_card_state_revision"],
        quality_decision_ref=row["quality_decision_ref"],
        committed_active_ids=json.loads(row["committed_active_ids_json"]),
        evicted_active_ids=json.loads(row["evicted_active_ids_json"]),
        committed_at=row["committed_at"],
    )


def _filter_active(records, request: MemoryRecallRequest):
    hits = []
    excluded = []
    statuses = set(request.statuses) if request.statuses else {"active"}
    for r in records:
        if r.status not in statuses:
            excluded.append({"memory_id": r.memory_id, "reason": f"status={r.status}"})
            continue
        if request.exclude_stale and r.status in _STALE_STATUSES:
            excluded.append({"memory_id": r.memory_id, "reason": "stale"})
            continue
        if r.importance < request.min_importance:
            excluded.append({"memory_id": r.memory_id, "reason": "low importance"})
            continue
        if r.confidence < request.min_confidence:
            excluded.append({"memory_id": r.memory_id, "reason": "low confidence"})
            continue
        if request.entity_refs:
            if not set(r.entity_refs) & set(request.entity_refs):
                excluded.append({"memory_id": r.memory_id, "reason": "entity filter miss"})
                continue
        if request.query:
            if request.query.lower() not in r.summary.lower():
                excluded.append({"memory_id": r.memory_id, "reason": "query miss"})
                continue
        hits.append(r)
    return hits, excluded


def _order_active(records):
    return sorted(
        records,
        key=lambda r: (r.importance, r.confidence, r.recall_count),
        reverse=True,
    )
