"""SQLite implementation of RecallLogStore + RetentionDecisionStore."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ..interfaces import RecallLogStore, RetentionDecisionStore
from ...contracts.memory_recall_result import MemoryRecallResult
from ...contracts.memory_retention_decision import MemoryRetentionResult
from .database import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteRecallLogStore(RecallLogStore):
    """Persists memory recall diagnostics."""

    def __init__(self, db: Database):
        self.db = db

    def log_recall(self, result: MemoryRecallResult) -> None:
        conn = self.db.connect()
        req = result.request
        conn.execute(
            "INSERT INTO memory_recall_logs "
            "(card_id, session_id, snapshot_id, layer, query, hits_json, excluded_json, ordered_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                req.card_id, req.session_id, req.snapshot_id,
                "mixed", req.query,
                json.dumps([h.to_dict() for h in result.hits], ensure_ascii=False),
                json.dumps(list(result.excluded), ensure_ascii=False),
                result.ordered_by,
            ),
        )
        conn.commit()

    def get_recent(self, card_id: str, session_id: str, limit: int = 20) -> list[dict]:
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT * FROM memory_recall_logs "
            "WHERE card_id=? AND session_id=? ORDER BY created_at DESC LIMIT ?",
            (card_id, session_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


class SqliteRetentionDecisionStore(RetentionDecisionStore):
    """Persists retention/eviction decisions for audit."""

    def __init__(self, db: Database):
        self.db = db

    def log_retention(self, result: MemoryRetentionResult) -> None:
        conn = self.db.connect()
        for d in result.decisions:
            conn.execute(
                "INSERT INTO memory_retention_decisions "
                "(card_id, session_id, turn_id, memory_id, action, reason, score) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    result.card_id, result.session_id, result.turn_id,
                    d.memory_id, d.action, d.reason, d.score,
                ),
            )
        conn.commit()

    def get_by_turn(self, card_id: str, session_id: str, turn_id: str) -> list[dict]:
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT * FROM memory_retention_decisions "
            "WHERE card_id=? AND session_id=? AND turn_id=? ORDER BY decided_at",
            (card_id, session_id, turn_id),
        ).fetchall()
        return [dict(r) for r in rows]
