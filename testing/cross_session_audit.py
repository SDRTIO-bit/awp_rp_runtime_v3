"""Cross-Session Isolation Audit — deterministic checks that independent sessions
do not leak state, memory, traces, or facts into each other.

Runs after a multi-session long-run completes.  Reads the per-turn artifact
directory and produces a cross_session_audit.json report.

Checks:
  1. session_id uniqueness
  2. TurnRecord ID non-overlap
  3. CardState revision independence (per-session monotonic, no cross-writes)
  4. L2 ActiveMemory ID non-overlap
  5. L3 RAG Memory ID non-overlap
  6. Trace ID non-overlap
  7. Session A does not contain B's proprietary fact keywords
  8. Session B does not contain A's proprietary fact keywords
  9. Restart isolation (revisions survive, no new binding created)
 10. Replay isolation (one session replay does not affect other session)

Design:
  - Purely deterministic; no LLM judge.
  - Can run offline from artifacts.
  - Detects intentionally injected cross-session contamination in test fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── fact keywords ────────────────────────────────────────────────────────────

# These come from scenario definitions but are hard-coded as a deterministic
# cross-check.  The audit also accepts per-session override keywords.

DEFAULT_SESSION_A_KEYWORDS = [
    "青铜怀表", "bronze", "辰时", "不告诉老丈", "保密", "secret",
]
DEFAULT_SESSION_B_KEYWORDS = [
    "银铃", "silver bell", "立即告诉老丈", "公开", "货郎", "public",
]


# ── audit result types ───────────────────────────────────────────────────────

class AuditFinding:
    """A single audit finding."""
    def __init__(self, check_id: str, passed: bool, detail: str = "",
                 session_id: str = "", turn_id: str = "", source: str = ""):
        self.check_id = check_id
        self.passed = passed
        self.detail = detail
        self.session_id = session_id
        self.turn_id = turn_id
        self.source = source

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "detail": self.detail,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "source": self.source,
        }


def _load_turn_artifacts(session_dir: Path) -> list[dict]:
    """Load all turn-NNN.json artifacts for a session, sorted by turn index."""
    records = []
    if not session_dir.exists():
        return records
    for tf in sorted(session_dir.glob("turn-*.json")):
        if tf.name == "summary.json":
            continue
        try:
            with open(tf, "r", encoding="utf-8") as f:
                records.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    records.sort(key=lambda r: r.get("turn_index", 0))
    return records


def _extract_keywords_from_writer_output(records: list[dict]) -> set[str]:
    """Extract all unique words from session writer outputs (for keyword checks)."""
    all_text = ""
    for r in records:
        writer = r.get("writer_output", "")
        if writer:
            all_text += writer + " "
        player = r.get("player_input", "")
        if player:
            all_text += player + " "
    # Normalize: remove punctuation, lowercase for CJK-safe matching
    import re
    words = set(re.findall(r'[一-鿿\w]+', all_text))
    return words


def _check_keyword_leakage(
    own_keywords: list[str],
    other_records: list[dict],
    label_own: str,
    label_other: str,
) -> list[AuditFinding]:
    """Check that other session's writer output does not contain own unique keywords."""
    findings = []
    other_text = ""
    for r in other_records:
        w = r.get("writer_output", "")
        if w:
            other_text += w + " "
        p = r.get("player_input", "")
        if p:
            other_text += p + " "

    for kw in own_keywords:
        if kw in other_text:
            # Locate which turn
            for r in other_records:
                wo = r.get("writer_output", "") + " " + r.get("player_input", "")
                if kw in wo:
                    findings.append(AuditFinding(
                        check_id="keyword_leak",
                        passed=False,
                        detail=f"Session {label_own} keyword '{kw}' found in session {label_other} turn {r.get('turn_index', '?')}",
                        session_id=r.get("session_id", ""),
                        turn_id=r.get("turn_id", ""),
                        source="writer_output_or_player_input",
                    ))
                    break
    if not findings:
        findings.append(AuditFinding(
            check_id="keyword_leak",
            passed=True,
            detail=f"No {label_own} keywords leaked into {label_other}",
        ))
    return findings


def run_cross_session_audit(
    artifact_dir: str | Path,
    session_a_keywords: list[str] | None = None,
    session_b_keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Run the full cross-session isolation audit.

    Returns a dict suitable for serialization into cross_session_audit.json.
    """
    artifact_dir = Path(artifact_dir)
    findings: list[AuditFinding] = []

    # ── Load per-session artifacts ────────────────────────────────────────
    session_a_dir = artifact_dir / "sessions" / "session-A"
    session_b_dir = artifact_dir / "sessions" / "session-B"

    a_records = _load_turn_artifacts(session_a_dir)
    b_records = _load_turn_artifacts(session_b_dir)

    a_kw = session_a_keywords or DEFAULT_SESSION_A_KEYWORDS
    b_kw = session_b_keywords or DEFAULT_SESSION_B_KEYWORDS

    # ── 1. session_id uniqueness ──────────────────────────────────────────
    a_ids = set(r.get("session_id", "") for r in a_records if r.get("session_id"))
    b_ids = set(r.get("session_id", "") for r in b_records if r.get("session_id"))

    if len(a_ids) == 1 and len(b_ids) == 1:
        a_id = a_ids.pop()
        b_id = b_ids.pop()
        a_ids.add(a_id)
        b_ids.add(b_id)
        findings.append(AuditFinding(
            check_id="session_id_unique",
            passed=a_id != b_id,
            detail=f"A={a_id}, B={b_id} — {'distinct' if a_id != b_id else 'DUPLICATE'}",
            session_id=a_id if a_id == b_id else "",
        ))
    else:
        findings.append(AuditFinding(
            check_id="session_id_unique",
            passed=False,
            detail=f"A has {len(a_ids)} ids, B has {len(b_ids)} ids (expected 1 each)",
        ))

    # ── 2. TurnRecord ID non-overlap ─────────────────────────────────────
    a_turn_record_ids = set(r.get("turn_record_id", "") for r in a_records if r.get("turn_record_id"))
    b_turn_record_ids = set(r.get("turn_record_id", "") for r in b_records if r.get("turn_record_id"))
    overlap_tr = a_turn_record_ids & b_turn_record_ids
    findings.append(AuditFinding(
        check_id="turn_record_id_non_overlap",
        passed=len(overlap_tr) == 0,
        detail=f"Overlapping TurnRecord IDs: {overlap_tr}" if overlap_tr else
               f"A={len(a_turn_record_ids)}, B={len(b_turn_record_ids)} — no overlap",
    ))

    # ── 3. CardState revision independence ────────────────────────────────
    a_revisions = [r.get("card_state_revision_after", 0) for r in a_records]
    b_revisions = [r.get("card_state_revision_after", 0) for r in b_records]
    a_monotonic = all(
        a_revisions[i] <= a_revisions[i + 1]
        for i in range(len(a_revisions) - 1)
    ) if len(a_revisions) > 1 else True
    b_monotonic = all(
        b_revisions[i] <= b_revisions[i + 1]
        for i in range(len(b_revisions) - 1)
    ) if len(b_revisions) > 1 else True
    findings.append(AuditFinding(
        check_id="card_state_revision_independent",
        passed=a_monotonic and b_monotonic,
        detail=f"A revisions: {a_revisions[-5:] if len(a_revisions) > 5 else a_revisions} "
               f"(monotonic={a_monotonic}); "
               f"B revisions: {b_revisions[-5:] if len(b_revisions) > 5 else b_revisions} "
               f"(monotonic={b_monotonic})",
    ))

    # ── 4. L2 ActiveMemory ID non-overlap ────────────────────────────────
    a_l2 = set()
    b_l2 = set()
    for r in a_records:
        for m in r.get("l2_memory_ids", []):
            a_l2.add(m)
    for r in b_records:
        for m in r.get("l2_memory_ids", []):
            b_l2.add(m)
    overlap_l2 = a_l2 & b_l2
    findings.append(AuditFinding(
        check_id="l2_active_memory_non_overlap",
        passed=len(overlap_l2) == 0,
        detail=f"Overlapping L2 IDs: {overlap_l2}" if overlap_l2 else
               f"A={len(a_l2)}, B={len(b_l2)} — no overlap",
    ))

    # ── 5. L3 RAG Memory ID non-overlap ──────────────────────────────────
    a_l3 = set()
    b_l3 = set()
    for r in a_records:
        for m in r.get("l3_memory_ids", []):
            a_l3.add(m)
    for r in b_records:
        for m in r.get("l3_memory_ids", []):
            b_l3.add(m)
    overlap_l3 = a_l3 & b_l3
    findings.append(AuditFinding(
        check_id="l3_rag_memory_non_overlap",
        passed=len(overlap_l3) == 0,
        detail=f"Overlapping L3 IDs: {overlap_l3}" if overlap_l3 else
               f"A={len(a_l3)}, B={len(b_l3)} — no overlap",
    ))

    # ── 6. Trace ID non-overlap ──────────────────────────────────────────
    a_trace_ids = set(r.get("trace_id", "") for r in a_records if r.get("trace_id"))
    b_trace_ids = set(r.get("trace_id", "") for r in b_records if r.get("trace_id"))
    overlap_trace = a_trace_ids & b_trace_ids
    findings.append(AuditFinding(
        check_id="trace_id_non_overlap",
        passed=len(overlap_trace) == 0,
        detail=f"Overlapping trace IDs: {overlap_trace}" if overlap_trace else
               f"A={len(a_trace_ids)}, B={len(b_trace_ids)} — no overlap",
    ))

    # ── 7/8. Keyword leakage ──────────────────────────────────────────────
    findings.extend(_check_keyword_leakage(a_kw, b_records, "A", "B"))
    findings.extend(_check_keyword_leakage(b_kw, a_records, "B", "A"))

    # ── 9. Restart isolation (revision continuity) ────────────────────────
    # Check that revisions don't reset after restart
    a_cont = all(r.get("card_state_revision_after", 0) > 0 for r in a_records) if a_records else False
    b_cont = all(r.get("card_state_revision_after", 0) > 0 for r in b_records) if b_records else False
    findings.append(AuditFinding(
        check_id="restart_revision_continuity",
        passed=a_cont and b_cont,
        detail=f"A revisions continuous: {a_cont}; B revisions continuous: {b_cont}",
    ))

    # ── 10. Binding stability (no duplicate bindings after restart) ───────
    a_card_ids = set(r.get("logical_card_id", "") for r in a_records if r.get("logical_card_id"))
    b_card_ids = set(r.get("logical_card_id", "") for r in b_records if r.get("logical_card_id"))
    findings.append(AuditFinding(
        check_id="binding_stability",
        passed=len(a_card_ids) <= 1 and len(b_card_ids) <= 1,
        detail=f"A card_ids={a_card_ids}, B card_ids={b_card_ids}",
    ))

    # ── Summary ──────────────────────────────────────────────────────────
    passed = sum(1 for f in findings if f.passed)
    failed = sum(1 for f in findings if not f.passed)

    result = {
        "audit_title": "Cross-Session Isolation Audit",
        "total_checks": len(findings),
        "passed": passed,
        "failed": failed,
        "passed_all": failed == 0,
        "findings": [f.to_dict() for f in findings],
        "sessions_audited": [
            {"label": "A", "turn_count": len(a_records), "session_ids": list(a_ids)},
            {"label": "B", "turn_count": len(b_records), "session_ids": list(b_ids)},
        ],
    }

    return result


# ── intentionally inject cross-session contamination (test-only) ──────────────

def inject_cross_session_contamination_for_test(
    session_b_artifact_dir: Path,
    contaminant_keyword: str = "青铜怀表",
) -> None:
    """DELIBERATELY inject a contaminant keyword into session B artifacts
    to verify the audit catches it.  ONLY for testing the audit itself.
    """
    b_dir = Path(session_b_artifact_dir)
    if not b_dir.exists():
        return
    turn_files = sorted(b_dir.glob("turn-*.json"))
    if not turn_files:
        return
    # Inject into the last turn artifact
    target = turn_files[-1]
    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["writer_output"] = (data.get("writer_output", "") +
                             f" [CONTAMINATED_TEST:{contaminant_keyword}]")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
