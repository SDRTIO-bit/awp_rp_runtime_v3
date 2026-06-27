"""CardGreetingSanitizer — sanitize greeting content for safe display."""

from __future__ import annotations

import re

from ..contracts.card_quarantine_record import (
    CardQuarantineRecord, QuarantineKind, QuarantineAction, QuarantineSeverity,
)

_PATTERNS: list[tuple[str, re.Pattern, str, str]] = [
    (QuarantineKind.SETVAR, re.compile(r"\{\{setvar:[^}]*\}\}", re.I), QuarantineSeverity.HIGH, "Variable write tag"),
    (QuarantineKind.GETVAR, re.compile(r"\{\{getvar:[^}]*\}\}", re.I), QuarantineSeverity.MEDIUM, "Variable read tag"),
    (QuarantineKind.ADDVAR, re.compile(r"\{\{addvar:[^}]*\}\}", re.I), QuarantineSeverity.HIGH, "Variable add tag"),
    (QuarantineKind.EJS, re.compile(r"<%[\s\S]*?%>"), QuarantineSeverity.HIGH, "EJS template"),
    (QuarantineKind.SCRIPT_TAG, re.compile(r"<script[\s>][\s\S]*?</script>", re.I), QuarantineSeverity.CRITICAL, "Script tag"),
    ("status_bar", re.compile(r"\{\{status_bar\}\}", re.I), QuarantineSeverity.LOW, "Status bar placeholder"),
]


def sanitize_greeting_content(
    raw_content: str, greeting_id: str, source_path: str,
) -> tuple[str, list[CardQuarantineRecord]]:
    safe = raw_content
    recs: list[CardQuarantineRecord] = []
    for kind, pat, sev, reason in _PATTERNS:
        matches = list(pat.finditer(safe))
        if matches:
            for m in matches:
                recs.append(CardQuarantineRecord(
                    record_id=f"q_{kind}_{greeting_id}_{len(recs)}", kind=kind,
                    source_path=source_path, severity=sev,
                    evidence_preview=m.group(0)[:120],
                    action=QuarantineAction.SANITIZED_FOR_DISPLAY, reason=reason,
                ))
            safe = pat.sub("", safe)
    safe = re.sub(r"\n{3,}", "\n\n", safe).strip()
    return safe, recs
