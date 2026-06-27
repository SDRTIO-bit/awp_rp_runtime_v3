"""CardStateCommitRequest / Result / Status — formal commit contracts.

schemaId: awp.rp.card-state-commit-request.v1
schemaId: awp.rp.card-state-commit-result.v1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .card_state_patch import CardStatePatch

REQUEST_SCHEMA_ID = "awp.rp.card-state-commit-request.v1"
RESULT_SCHEMA_ID = "awp.rp.card-state-commit-result.v1"
SCHEMA_VERSION = 1


class CardStateCommitStatus(str, Enum):
    """Status of a CardState commit attempt."""
    ACCEPTED = "accepted"
    REVISION_CONFLICT = "revision_conflict"
    DUPLICATE_PATCH = "duplicate_patch"
    VALIDATION_FAILED = "validation_failed"
    GATE_REJECTED = "gate_rejected"
    TRACE_MISMATCH = "trace_mismatch"
    INTERNAL_ERROR = "internal_error"


@dataclass
class CardStateCommitRequest:
    """Request to commit state changes.

    Must include:
    - patch: the validated patch
    - expected_revision: current revision must match this
    - quality_decision_ref: reference to the QualityDecision that approved this
    - trace_id: must match the QualityDecision's trace_id
    """
    schema_id: str = REQUEST_SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    patch: CardStatePatch = field(default_factory=CardStatePatch)
    expected_revision: int = 0
    quality_decision_ref: str = ""  # turn_id from QualityDecision
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "patch": self.patch.to_dict(),
            "expected_revision": self.expected_revision,
            "quality_decision_ref": self.quality_decision_ref,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardStateCommitRequest:
        return cls(
            schema_id=data.get("schema_id", REQUEST_SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            patch=CardStatePatch.from_dict(data.get("patch", {})),
            expected_revision=data.get("expected_revision", 0),
            quality_decision_ref=data.get("quality_decision_ref", ""),
            trace_id=data.get("trace_id", ""),
        )


@dataclass
class CardStateCommitResult:
    """Result of a CardState commit attempt."""
    schema_id: str = RESULT_SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    status: CardStateCommitStatus = CardStateCommitStatus.INTERNAL_ERROR
    card_id: str = ""
    session_id: str = ""
    patch_id: str = ""
    from_revision: int = 0
    to_revision: int = 0
    trace_id: str = ""
    error_message: str = ""
    validation_errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.status == CardStateCommitStatus.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "status": self.status.value,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "patch_id": self.patch_id,
            "from_revision": self.from_revision,
            "to_revision": self.to_revision,
            "trace_id": self.trace_id,
            "error_message": self.error_message,
            "validation_errors": self.validation_errors,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardStateCommitResult:
        return cls(
            schema_id=data.get("schema_id", RESULT_SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            status=CardStateCommitStatus(data.get("status", "internal_error")),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            patch_id=data.get("patch_id", ""),
            from_revision=data.get("from_revision", 0),
            to_revision=data.get("to_revision", 0),
            trace_id=data.get("trace_id", ""),
            error_message=data.get("error_message", ""),
            validation_errors=data.get("validation_errors", []),
        )
