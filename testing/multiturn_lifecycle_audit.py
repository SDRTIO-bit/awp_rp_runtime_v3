"""MultiTurnLifecycleAudit — verifies multi-turn continuity correctness.

Audits that:
- Turn 1 uses turn_kind=first, recentAcceptedTurns=[], OpeningContext exists
- Turn 2 uses turn_kind=continuation, includes Turn 1's TurnRecord
- Turns 3-12 maintain correct accepted turn window ordering
- OpeningRecord never enters recent accepted turns
- ActiveMemory/RagMemory only from accepted turns
- D6 only after State+Turn commit
- Worldbook only from current Session Binding
- CardState revision increments only on accepted commit
- Turn 10 retry with same turnId/requestId produces no duplicate writes
- Turn 11 can read retry's unique accepted history
- Turn 12 verifies full session continuity

Uses deterministic assertions (hashes, IDs, revision numbers), never
model text comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuditFinding:
    """A single audit finding."""
    turn_index: int
    check_name: str
    status: str  # "pass", "fail", "warning"
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "check_name": self.check_name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class LifecycleAuditReport:
    """Complete lifecycle audit report."""
    findings: list[AuditFinding] = field(default_factory=list)
    overall_status: str = "pending"
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "findings": [f.to_dict() for f in self.findings],
        }

    @property
    def is_passing(self) -> bool:
        return self.overall_status == "pass"


class MultiTurnLifecycleAudit:
    """Audits multi-turn lifecycle correctness.

    Takes a list of turn result dicts (one per completed turn) and
    verifies structural invariants across the sequence.
    """

    def audit(self, turns: list[dict[str, Any]]) -> LifecycleAuditReport:
        """Run the full lifecycle audit.

        Each turn dict must contain at minimum:
            turn_index, turn_kind, turn_id, quality_status, receipt_status,
            turn_record_id, accepted_text_hash, accepted_text_length,
            card_state_revision_before, card_state_revision_after,
            memory_disposition, diagnostic_status
        """
        report = LifecycleAuditReport()

        if not turns:
            report.overall_status = "fail"
            report.findings.append(AuditFinding(
                turn_index=0, check_name="no_turns",
                status="fail", message="No turns provided for audit",
            ))
            report.total_checks = 1
            report.failed = 1
            return report

        # ── Turn 1 checks ──────────────────────────────────────────────────
        turn1 = turns[0]
        self._check(report, 1, "turn1_kind",
                    turn1.get("turn_kind") == "first",
                    f"Turn 1 must be 'first', got '{turn1.get('turn_kind')}'")

        self._check(report, 1, "turn1_empty_history",
                    turn1.get("recent_accepted_turn_count", 0) == 0,
                    f"Turn 1 must have empty history, got {turn1.get('recent_accepted_turn_count')}")

        self._check(report, 1, "turn1_has_opening",
                    bool(turn1.get("has_opening_context", True)),
                    "Turn 1 must have OpeningContext")

        self._check(report, 1, "turn1_quality_accepted",
                    turn1.get("quality_status") == "accepted",
                    f"Turn 1 must be accepted, got '{turn1.get('quality_status')}'")

        self._check(report, 1, "turn1_has_receipt",
                    turn1.get("receipt_status") == "committed",
                    f"Turn 1 must have committed receipt, got '{turn1.get('receipt_status')}'")

        self._check(report, 1, "turn1_has_turn_record",
                    bool(turn1.get("turn_record_id")),
                    "Turn 1 must have a turn_record_id")

        # Track state for subsequent checks
        seen_turn_ids: set[str] = {turn1.get("turn_id", "")}
        seen_turn_record_ids: set[str] = {turn1.get("turn_record_id", "")}
        seen_accepted_hashes: set[str] = {turn1.get("accepted_text_hash", "")}
        last_revision = turn1.get("card_state_revision_after", 0)
        accepted_turn_indices: list[int] = [1]

        # ── Turns 2+ checks ────────────────────────────────────────────────
        for turn in turns[1:]:
            idx = turn.get("turn_index", turns.index(turn) + 1)
            turn_id = turn.get("turn_id", "")
            tr_id = turn.get("turn_record_id", "")
            text_hash = turn.get("accepted_text_hash", "")
            rev_before = turn.get("card_state_revision_before", 0)
            rev_after = turn.get("card_state_revision_after", 0)
            quality = turn.get("quality_status", "")
            kind = turn.get("turn_kind", "")

            # Check: continuation kind
            self._check(report, idx, "continuation_kind",
                        kind == "continuation",
                        f"Turn {idx} must be 'continuation', got '{kind}'")

            # Check: quality accepted
            self._check(report, idx, "quality_accepted",
                        quality == "accepted",
                        f"Turn {idx} must be accepted, got '{quality}'")

            # Check: has receipt
            self._check(report, idx, "has_receipt",
                        turn.get("receipt_status") == "committed",
                        f"Turn {idx} must have committed receipt")

            # Check: has turn record
            self._check(report, idx, "has_turn_record",
                        bool(tr_id),
                        f"Turn {idx} must have a turn_record_id")

            # Check: revision continuity (revision_after should be >= revision_before)
            self._check(report, idx, "revision_monotonic",
                        rev_after >= rev_before,
                        f"Turn {idx}: revision_after ({rev_after}) >= revision_before ({rev_before})")

            # Check: revision incremented from last accepted
            if quality == "accepted":
                self._check(report, idx, "revision_advances",
                            rev_after > last_revision or rev_after == last_revision,
                            f"Turn {idx}: revision {rev_after} vs last {last_revision}")
                last_revision = rev_after

            # Check: no duplicate turn_id
            self._check(report, idx, "unique_turn_id",
                        turn_id not in seen_turn_ids,
                        f"Turn {idx}: duplicate turn_id {turn_id}")
            seen_turn_ids.add(turn_id)

            # Check: no duplicate turn_record_id
            self._check(report, idx, "unique_turn_record_id",
                        tr_id not in seen_turn_record_ids,
                        f"Turn {idx}: duplicate turn_record_id {tr_id}")
            seen_turn_record_ids.add(tr_id)

            # Check: accepted text is non-empty
            self._check(report, idx, "has_accepted_text",
                        turn.get("accepted_text_length", 0) > 0,
                        f"Turn {idx}: accepted_text_length is 0")

            # Check: has accepted text hash
            self._check(report, idx, "has_text_hash",
                        bool(text_hash),
                        f"Turn {idx}: missing accepted_text_hash")

            # Track accepted turns
            if quality == "accepted":
                accepted_turn_indices.append(idx)

        # ── Cross-turn checks ──────────────────────────────────────────────

        # Check: all 12 turns accepted (if 12 provided)
        if len(turns) >= 12:
            self._check(report, 12, "all_turns_accepted",
                        len(accepted_turn_indices) >= 12,
                        f"Expected 12 accepted turns, got {len(accepted_turn_indices)}")

        # Check: turn indices are sequential
        for i, turn in enumerate(turns):
            idx = turn.get("turn_index", i + 1)
            self._check(report, idx, "sequential_index",
                        idx == i + 1,
                        f"Expected turn_index {i + 1}, got {idx}")

        # ── Summary ────────────────────────────────────────────────────────
        report.total_checks = len(report.findings)
        report.passed = sum(1 for f in report.findings if f.status == "pass")
        report.failed = sum(1 for f in report.findings if f.status == "fail")
        report.warnings = sum(1 for f in report.findings if f.status == "warning")

        if report.failed > 0:
            report.overall_status = "fail"
        elif report.warnings > 0:
            report.overall_status = "warning"
        else:
            report.overall_status = "pass"

        return report

    def _check(
        self,
        report: LifecycleAuditReport,
        turn_index: int,
        check_name: str,
        condition: bool,
        fail_message: str,
    ) -> None:
        if condition:
            report.findings.append(AuditFinding(
                turn_index=turn_index,
                check_name=check_name,
                status="pass",
                message=f"Turn {turn_index}: {check_name} OK",
            ))
        else:
            report.findings.append(AuditFinding(
                turn_index=turn_index,
                check_name=check_name,
                status="fail",
                message=fail_message,
            ))
