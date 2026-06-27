"""SQLite RoundSnapshotStore."""

from __future__ import annotations

import json

from ..interfaces import RoundSnapshotStore
from ...contracts.round_snapshot import RoundSnapshot
from .database import Database


class SqliteRoundSnapshotStore(RoundSnapshotStore):

    def __init__(self, db: Database):
        self.db = db

    def save(self, snapshot: RoundSnapshot) -> None:
        conn = self.db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO round_snapshots "
            "(snapshot_id, trace_id, card_id, session_id, base_card_state_revision, snapshot_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (snapshot.snapshot_id, snapshot.trace_id, snapshot.card_id,
             snapshot.session_id, snapshot.base_card_state_revision,
             json.dumps(snapshot.to_dict())),
        )
        conn.commit()

    def load(self, snapshot_id: str) -> RoundSnapshot | None:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT snapshot_json FROM round_snapshots WHERE snapshot_id=?",
            (snapshot_id,),
        ).fetchone()
        return RoundSnapshot.from_dict(json.loads(row["snapshot_json"])) if row else None
