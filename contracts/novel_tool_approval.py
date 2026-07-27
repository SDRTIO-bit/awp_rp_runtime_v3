"""Strict contracts for project-tool risk and author approval."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ToolRisk = Literal["read", "write", "important", "hard_deny"]
ToolDecision = Literal["allow", "deny"]
ToolApprovalMode = Literal["auto", "ask_writes", "read_only"]


class ToolApprovalRequest(BaseModel):
    """One immutable pre-execution decision request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(min_length=1, max_length=128)
    tool: str = Field(min_length=1, max_length=100)
    risk: ToolRisk
    summary: str = Field(min_length=1, max_length=1_000)
    targets: list[str] = Field(default_factory=list, max_length=100)
    reason: str = Field(min_length=1, max_length=2_000)
    diff: str = Field(default="", max_length=60_000)
    arguments_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def create(
        cls,
        *,
        tool: str,
        risk: ToolRisk,
        summary: str,
        targets: list[str],
        reason: str,
        arguments: dict[str, Any],
        diff: str = "",
    ) -> "ToolApprovalRequest":
        canonical = json.dumps(
            arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        arguments_hash = hashlib.sha256(canonical).hexdigest()
        signature_source = json.dumps(
            {
                "tool": tool,
                "risk": risk,
                "targets": targets,
                "reason": reason,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return cls(
            approval_id=f"tool-{uuid.uuid4().hex}",
            tool=tool,
            risk=risk,
            summary=summary,
            targets=targets,
            reason=reason,
            diff=diff,
            arguments_hash=arguments_hash,
            signature=hashlib.sha256(signature_source).hexdigest(),
        )


class ToolApprovalDecision(BaseModel):
    """An author decision returned by the browser."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(min_length=1, max_length=128)
    decision: ToolDecision
    remember: bool = False


__all__ = [
    "ToolApprovalDecision",
    "ToolApprovalMode",
    "ToolApprovalRequest",
    "ToolDecision",
    "ToolRisk",
]
