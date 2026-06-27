"""SQLite implementation of TraceStore."""

from __future__ import annotations

import json

from ..interfaces import TraceStore
from ...contracts.execution_trace import ExecutionTrace
from .database import Database


class SqliteTraceStore(TraceStore):
    """SQLite-backed execution trace store."""

    def __init__(self, db: Database):
        self.db = db

    def save(self, trace: ExecutionTrace) -> None:
        """Save an execution trace."""
        conn = self.db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO execution_traces "
            "(trace_id, turn_id, card_id, session_id, trace_json) VALUES (?, ?, ?, ?, ?)",
            (trace.trace_id, trace.turn_id, trace.card_id, trace.session_id,
             json.dumps(trace.to_dict())),
        )
        conn.commit()

    def load(self, trace_id: str) -> ExecutionTrace | None:
        """Load a trace by ID."""
        conn = self.db.connect()
        row = conn.execute(
            "SELECT trace_json FROM execution_traces WHERE trace_id=?",
            (trace_id,),
        ).fetchone()

        if not row:
            return None

        return ExecutionTrace.from_dict(json.loads(row["trace_json"]))

    def get_by_turn(self, turn_id: str) -> ExecutionTrace | None:
        """Get trace for a specific turn."""
        conn = self.db.connect()
        row = conn.execute(
            "SELECT trace_json FROM execution_traces WHERE turn_id=?",
            (turn_id,),
        ).fetchone()

        if not row:
            return None

        return ExecutionTrace.from_dict(json.loads(row["trace_json"]))
