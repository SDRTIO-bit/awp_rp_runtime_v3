"""CardSecurityScan — scan a character card for dangerous content."""

from __future__ import annotations

import re
from typing import Any

from ..contracts.card_quarantine_record import (
    CardQuarantineRecord, QuarantineKind, QuarantineAction, QuarantineSeverity,
)
from ..contracts.card_import_issue import CardImportIssue, IssueSeverity, IssueCategory

_SECURITY_PATTERNS: list[tuple[str, str, re.Pattern, str]] = [
    (QuarantineKind.JAVASCRIPT, QuarantineSeverity.CRITICAL, re.compile(r"new\s+Function\s*\(", re.I), "JavaScript Function constructor"),
    (QuarantineKind.EVAL, QuarantineSeverity.CRITICAL, re.compile(r"\beval\s*\(", re.I), "eval() call"),
    (QuarantineKind.EJS, QuarantineSeverity.HIGH, re.compile(r"<%[\s\S]*?%>"), "EJS template"),
    (QuarantineKind.SETVAR, QuarantineSeverity.HIGH, re.compile(r"\{\{setvar:", re.I), "{{setvar:}} write"),
    (QuarantineKind.GETVAR, QuarantineSeverity.MEDIUM, re.compile(r"\{\{getvar:", re.I), "{{getvar:}} read"),
    (QuarantineKind.ADDVAR, QuarantineSeverity.HIGH, re.compile(r"\{\{addvar:", re.I), "{{addvar:}} addition"),
    (QuarantineKind.SCRIPT_TAG, QuarantineSeverity.CRITICAL, re.compile(r"<script[\s>]"), "<script> tag"),
    (QuarantineKind.IFRAME, QuarantineSeverity.HIGH, re.compile(r"<iframe[\s>]"), "<iframe> tag"),
    (QuarantineKind.FETCH, QuarantineSeverity.HIGH, re.compile(r"\bfetch\s*\(", re.I), "fetch() call"),
    (QuarantineKind.IMPORT_URL, QuarantineSeverity.HIGH, re.compile(r"\bimport\s*\(", re.I), "Dynamic import()"),
    (QuarantineKind.REGEX_SCRIPT, QuarantineSeverity.MEDIUM, re.compile(r"regexScript|regex_script", re.I), "Regex script"),
    (QuarantineKind.VARIABLE_EXEC, QuarantineSeverity.MEDIUM, re.compile(r"\{\{var:", re.I), "{{var:}} syntax"),
]

_VAR_PATTERNS = [
    re.compile(r"\{\{getvar:", re.I), re.compile(r"\{\{setvar:", re.I),
    re.compile(r"\{\{addvar:", re.I), re.compile(r"\{\{var:", re.I),
    re.compile(r"<%[\s\S]*?%>"), re.compile(r"awpVariableCondition", re.I),
]


def _collect_strings(obj: Any, depth: int = 10) -> list[str]:
    if depth <= 0:
        return []
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _collect_strings(v, depth - 1)]
    if isinstance(obj, list):
        return [s for item in obj for s in _collect_strings(item, depth - 1)]
    return []


class CardSecurityScanner:

    def scan(self, data: dict[str, Any]) -> tuple[list[CardQuarantineRecord], list[CardImportIssue], dict[str, Any]]:
        records: list[CardQuarantineRecord] = []
        issues: list[CardImportIssue] = []
        kind_counts: dict[str, int] = {}
        vars_detected = False

        for text in _collect_strings(data):
            for kind, sev, pat, desc in _SECURITY_PATTERNS:
                matches = list(pat.finditer(text))
                if matches:
                    cnt = len(matches)
                    kind_counts[kind] = kind_counts.get(kind, 0) + cnt
                    start = max(0, matches[0].start() - 20)
                    end = min(len(text), matches[0].end() + 80)
                    ev = text[start:end][:120]
                    records.append(CardQuarantineRecord(
                        record_id=f"q_{kind}_{len(records)}", kind=kind,
                        severity=sev, evidence_preview=ev,
                        action=QuarantineAction.QUARANTINED, reason=desc,
                    ))
                    sev_level = IssueSeverity.WARNING if sev in (QuarantineSeverity.LOW, QuarantineSeverity.MEDIUM) else IssueSeverity.ERROR
                    issues.append(CardImportIssue(
                        issue_id=f"sec_{kind}_{len(issues)}", severity=sev_level,
                        category=IssueCategory.SECURITY, message=f"{desc} ({cnt}x)", evidence_preview=ev,
                    ))
            for vp in _VAR_PATTERNS:
                if vp.search(text):
                    vars_detected = True
                    break

        return records, issues, {"quarantine_count": len(records), "kind_counts": kind_counts, "variables_detected": vars_detected}
