"""AWPV2CardSecurityScan — 安全扫描角色卡."""

from __future__ import annotations
import json
from typing import Any


class AWPV2CardSecurityScan:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"raw_payload": ("CARD_RAW_PAYLOAD",)}}

    RETURN_TYPES = ("QUARANTINE_RECORDS", "SECURITY_ISSUES", "SECURITY_SUMMARY")
    RETURN_NAMES = ("quarantine_records", "security_issues", "security_summary")
    FUNCTION = "execute"
    CATEGORY = "AWP/CardImport"

    def execute(self, raw_payload: str) -> tuple[list, list, dict]:
        from ..runtime.card_security_scanner import CardSecurityScanner
        recs, issues, summary = CardSecurityScanner().scan(json.loads(raw_payload))
        return ([r.to_dict() for r in recs], [i.to_dict() for i in issues], summary)
