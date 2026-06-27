"""SQLite CardSourceStore."""

from __future__ import annotations

import json

from ..card_import_interfaces import CardSourceStore
from ...contracts.card_source_snapshot import CardSourceSnapshot
from .database import Database


class SqliteCardSourceStore(CardSourceStore):
    """SQLite-backed card source snapshot store."""

    def __init__(self, db: Database):
        self.db = db

    def save(self, snapshot: CardSourceSnapshot) -> None:
        conn = self.db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO card_source_snapshots "
            "(source_id, source_hash, source_filename, source_format, "
            "source_size_bytes, imported_at, spec, raw_payload_ref, snapshot_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot.source_id,
                snapshot.source_hash,
                snapshot.source_filename,
                snapshot.source_format,
                snapshot.source_size_bytes,
                snapshot.imported_at,
                snapshot.spec,
                snapshot.raw_payload_ref,
                json.dumps(snapshot.to_dict(), ensure_ascii=False),
            ),
        )
        conn.commit()

    def load(self, source_id: str) -> CardSourceSnapshot | None:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT snapshot_json FROM card_source_snapshots WHERE source_id=?",
            (source_id,),
        ).fetchone()
        if not row:
            return None
        return CardSourceSnapshot.from_dict(json.loads(row["snapshot_json"]))

    def get_by_hash(self, source_hash: str) -> CardSourceSnapshot | None:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT snapshot_json FROM card_source_snapshots WHERE source_hash=?",
            (source_hash,),
        ).fetchone()
        if not row:
            return None
        return CardSourceSnapshot.from_dict(json.loads(row["snapshot_json"]))
