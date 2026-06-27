"""AWPV2CardDefinitionCommit — 提交 CardDefinition 到存储."""

from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Any


class AWPV2CardDefinitionCommit:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"card_definition": ("CARD_DEFINITION",), "approval": ("CARD_IMPORT_APPROVAL",)}}

    RETURN_TYPES = ("CARD_IMPORT_RESULT",)
    RETURN_NAMES = ("import_result",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardImport"

    def execute(self, card_definition: dict, approval: dict) -> tuple[dict]:
        from ..contracts.card_definition import CardDefinition, CardDefinitionStatus
        from ..contracts.card_import_approval import CardImportApproval, ApprovalDecision
        from ..contracts.card_import_result import CardImportResult, ImportResultStatus
        now = datetime.now(timezone.utc).isoformat()
        appr = CardImportApproval.from_dict(approval)
        defn = CardDefinition.from_dict(card_definition)
        if appr.decision == ApprovalDecision.APPROVE:
            ns, rs = CardDefinitionStatus.READY, ImportResultStatus.SUCCESS
        elif appr.decision == ApprovalDecision.REJECT:
            ns, rs = CardDefinitionStatus.REJECTED, ImportResultStatus.SECURITY_REJECTED
        else:
            ns, rs = defn.status, ImportResultStatus.INTERNAL_ERROR
        return (CardImportResult(
            result_id=f"res_{hashlib.sha256(f'{defn.logical_card_id}_{now}'.encode()).hexdigest()[:16]}",
            status=rs, logical_card_id=defn.logical_card_id, card_version=defn.card_version,
            source_id=defn.source_id, source_hash=defn.source_hash,
            name=defn.name, report_ref=defn.import_report_ref, trace_id=defn.trace_id,
        ).to_dict(),)
