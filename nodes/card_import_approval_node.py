"""AWPV2CardImportApproval — 显式批准或拒绝导入."""

from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Any


class AWPV2CardImportApproval:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"card_definition": ("CARD_DEFINITION",), "decision": (["approve", "reject"],)},
                "optional": {"reason": ("STRING", {"default": ""})}}

    RETURN_TYPES = ("CARD_IMPORT_APPROVAL",)
    RETURN_NAMES = ("approval",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardImport"

    def execute(self, card_definition: dict, decision: str, reason: str = "") -> tuple[dict]:
        from ..contracts.card_import_approval import CardImportApproval
        now = datetime.now(timezone.utc).isoformat()
        cid = card_definition.get("logical_card_id", "")
        cv = card_definition.get("card_version", 1)
        return (CardImportApproval(
            approval_id=f"appr_{hashlib.sha256(f'{cid}_{cv}_{now}'.encode()).hexdigest()[:16]}",
            logical_card_id=cid, card_version=cv, decision=decision, reason=reason,
            approved_by="user", approved_at=now,
        ).to_dict(),)
