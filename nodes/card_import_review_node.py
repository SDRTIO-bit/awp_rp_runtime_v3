"""AWPV2CardImportReview — 生成导入审核报告."""

from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Any


class AWPV2CardImportReview:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"card_definition": ("CARD_DEFINITION",), "source_snapshot": ("SOURCE_SNAPSHOT",)}}

    RETURN_TYPES = ("CARD_IMPORT_REPORT",)
    RETURN_NAMES = ("import_report",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardImport"

    def execute(self, card_definition: dict, source_snapshot: dict) -> tuple[dict]:
        from ..contracts.card_import_report import CardImportReport
        now = datetime.now(timezone.utc).isoformat()
        qs = card_definition.get("quarantine_summary", {})
        hints = card_definition.get("structure_hints", {})
        cid = card_definition.get("card_id", "")
        report = CardImportReport(
            report_id=f"rpt_{hashlib.sha256(f'{cid}_{now}'.encode()).hexdigest()[:16]}",
            source_id=source_snapshot.get("source_id", ""),
            card_id=card_definition.get("card_id", ""),
            card_version=card_definition.get("card_version", 1),
            status="warnings" if qs.get("total", 0) > 0 else "ok",
            name=card_definition.get("name", ""), spec=source_snapshot.get("spec", ""),
            greeting_count=len(card_definition.get("greetings", [])),
            worldbook_entry_count=len(card_definition.get("worldbook_catalog", [])),
            worldbook_chunk_count=len(card_definition.get("worldbook_chunks", [])),
            quarantine_count=qs.get("total", 0),
            structure_hint_count=len(hints.get("phase_hints", [])) + len(hints.get("event_hints", [])) + len(hints.get("variable_hints", [])),
            quarantine_summary=qs, created_at=now,
        )
        return (report.to_dict(),)
