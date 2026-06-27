"""CardImportApproval — approval or rejection decision for a staged card.

schemaId: awp.rp.card-import-approval.v1

Frozen record of an approval decision. A card in STAGED status
requires an explicit APPROVE or REJECT before it becomes READY or
REJECTED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-import-approval.v1"
SCHEMA_VERSION = 1


class ApprovalDecision:
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class CardImportApproval:
    """Approval or rejection decision for a staged card."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    approval_id: str = ""
    logical_card_id: str = ""
    card_version: int = 0
    decision: str = ApprovalDecision.REJECT
    reason: str = ""
    approved_by: str = ""
    approved_at: str = ""
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "approval_id": self.approval_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "decision": self.decision,
            "reason": self.reason,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardImportApproval:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            approval_id=data.get("approval_id", ""),
            logical_card_id=data.get("logical_card_id", "") or data.get("card_id", ""),
            card_version=data.get("card_version", 0),
            decision=data.get("decision", ApprovalDecision.REJECT),
            reason=data.get("reason", ""),
            approved_by=data.get("approved_by", ""),
            approved_at=data.get("approved_at", ""),
            trace_id=data.get("trace_id", ""),
        )
