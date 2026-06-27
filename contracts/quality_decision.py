"""QualityDecision — the quality gate's decision.

schemaId: awp.rp.quality-decision.v1

Three verdicts:
  accept → allow commit
  revise → block all side effects, allow retry
  reject → block all side effects, stop

The gate is the ONLY permission path for all writes:
  CardStateCommit, TurnRecordCommit, ActiveMemoryCommit, RAGMemoryCommit.
Without a matching accepted QualityDecision, zero writes are permitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.quality-decision.v1"
SCHEMA_VERSION = 1


class QualityVerdict(str, Enum):
    """Three-state quality gate verdict."""
    ACCEPTED = "accept"
    REVISE = "revise"
    REJECTED = "reject"


@dataclass
class QualityDecision:
    """Quality gate decision on candidate text.

    Fields:
      verdict: accept | revise | reject
      decision: alias for verdict (backward compat)
      blockingReasons: why this verdict was chosen
      warnings: non-blocking observations
      traceId: links to the execution trace
      sourceTurnId: which turn this decision belongs to
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    trace_id: str = ""
    source_turn_id: str = ""

    # Verdict
    verdict: QualityVerdict = QualityVerdict.REJECTED
    candidate_text: str = ""

    # Reasons
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Check details
    checks: list[dict[str, Any]] = field(default_factory=list)
    overall_score: float = 0.0

    # Retry info
    retry_allowed: bool = True
    retry_count: int = 0
    max_retries: int = 3

    # Acceptance notes
    acceptance_notes: list[str] = field(default_factory=list)

    @property
    def decision(self) -> str:
        """Alias for verdict.value (backward compat)."""
        return self.verdict.value

    def is_accepted(self) -> bool:
        return self.verdict == QualityVerdict.ACCEPTED

    def is_revise(self) -> bool:
        return self.verdict == QualityVerdict.REVISE

    def is_rejected(self) -> bool:
        return self.verdict == QualityVerdict.REJECTED

    def allows_side_effects(self) -> bool:
        """Only 'accept' allows side effects."""
        return self.verdict == QualityVerdict.ACCEPTED

    def can_retry(self) -> bool:
        """Only 'revise' allows retry. 'reject' is final."""
        return (
            self.verdict == QualityVerdict.REVISE
            and self.retry_allowed
            and self.retry_count < self.max_retries
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "source_turn_id": self.source_turn_id,
            "verdict": self.verdict.value,
            "decision": self.decision,
            "candidate_text": self.candidate_text,
            "blocking_reasons": self.blocking_reasons,
            "warnings": self.warnings,
            "checks": self.checks,
            "overall_score": self.overall_score,
            "retry_allowed": self.retry_allowed,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "acceptance_notes": self.acceptance_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityDecision:
        verdict_raw = data.get("verdict", data.get("decision", "reject"))
        # Handle both old "accepted"/"rejected" and new "accept"/"reject"
        verdict_map = {
            "accepted": QualityVerdict.ACCEPTED,
            "accept": QualityVerdict.ACCEPTED,
            "rejected": QualityVerdict.REJECTED,
            "reject": QualityVerdict.REJECTED,
            "revise": QualityVerdict.REVISE,
        }
        verdict = verdict_map.get(verdict_raw, QualityVerdict.REJECTED)

        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            trace_id=data.get("trace_id", ""),
            source_turn_id=data.get("source_turn_id", data.get("turn_id", "")),
            verdict=verdict,
            candidate_text=data.get("candidate_text", ""),
            blocking_reasons=data.get("blocking_reasons", data.get("rejection_reasons", [])),
            warnings=data.get("warnings", []),
            checks=data.get("checks", []),
            overall_score=data.get("overall_score", 0.0),
            retry_allowed=data.get("retry_allowed", True),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            acceptance_notes=data.get("acceptance_notes", []),
        )


def assert_side_effects_allowed(quality_decision: QualityDecision | None) -> None:
    """Gate function: raise if side effects are not allowed.

    Rules:
      accept  → allow
      revise  → block
      reject  → block
      None    → block
      traceId mismatch → block (caller must check separately)
    """
    if quality_decision is None:
        raise SideEffectBlockedError("No QualityDecision provided")

    if not quality_decision.allows_side_effects():
        raise SideEffectBlockedError(
            f"Side effects blocked: verdict={quality_decision.verdict.value}, "
            f"reasons={quality_decision.blocking_reasons}"
        )


class SideEffectBlockedError(Exception):
    """Raised when a commit is attempted without gate approval."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Side effect blocked: {reason}")
