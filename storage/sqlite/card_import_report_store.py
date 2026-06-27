"""SQLite CardImportReportStore."""

from __future__ import annotations

import json

from ..card_import_interfaces import CardImportReportStore
from ...contracts.card_import_report import CardImportReport
from .database import Database


class SqliteCardImportReportStore(CardImportReportStore):
    """SQLite-backed card import report store."""

    def __init__(self, db: Database):
        self.db = db

    def save(self, report: CardImportReport) -> None:
        conn = self.db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO card_import_reports "
            "(report_id, request_id, source_id, card_id, card_version, "
            "status, name, report_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                report.report_id,
                report.request_id,
                report.source_id,
                report.card_id,
                report.card_version,
                report.status,
                report.name,
                json.dumps(report.to_dict(), ensure_ascii=False),
                report.created_at,
            ),
        )
        conn.commit()

    def load(self, report_id: str) -> CardImportReport | None:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT report_json FROM card_import_reports WHERE report_id=?",
            (report_id,),
        ).fetchone()
        if not row:
            return None
        return CardImportReport.from_dict(json.loads(row["report_json"]))

    def get_by_card(self, card_id: str, card_version: int = 0) -> list[CardImportReport]:
        conn = self.db.connect()
        if card_version > 0:
            rows = conn.execute(
                "SELECT report_json FROM card_import_reports "
                "WHERE card_id=? AND card_version=? ORDER BY created_at",
                (card_id, card_version),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT report_json FROM card_import_reports "
                "WHERE card_id=? ORDER BY card_version, created_at",
                (card_id,),
            ).fetchall()
        return [CardImportReport.from_dict(json.loads(r["report_json"])) for r in rows]
