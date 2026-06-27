"""CardFormatValidate — validate the structure of a parsed card payload."""

from __future__ import annotations

from typing import Any

from ..contracts.card_import_issue import CardImportIssue, IssueSeverity, IssueCategory


def validate_card_format(data: dict[str, Any]) -> list[CardImportIssue]:
    issues: list[CardImportIssue] = []
    spec = data.get("spec")
    if spec is None:
        issues.append(CardImportIssue(issue_id="missing_spec", severity=IssueSeverity.ERROR,
            category=IssueCategory.FORMAT, message="Missing 'spec' field", source_path="spec"))
    elif not isinstance(spec, str) or not spec:
        issues.append(CardImportIssue(issue_id="empty_spec", severity=IssueSeverity.WARNING,
            category=IssueCategory.FORMAT, message="'spec' is empty or not a string", source_path="spec"))
    card_data = data.get("data")
    if card_data is None:
        issues.append(CardImportIssue(issue_id="missing_data", severity=IssueSeverity.ERROR,
            category=IssueCategory.FORMAT, message="Missing 'data' field", source_path="data"))
        return issues
    if not isinstance(card_data, dict):
        issues.append(CardImportIssue(issue_id="invalid_data_type", severity=IssueSeverity.ERROR,
            category=IssueCategory.FORMAT, message=f"'data' must be dict, got {type(card_data).__name__}", source_path="data"))
        return issues
    if not card_data.get("name"):
        issues.append(CardImportIssue(issue_id="missing_name", severity=IssueSeverity.WARNING,
            category=IssueCategory.FORMAT, message="Missing 'name', will default to 'Unknown'", source_path="data.name"))
    if not card_data.get("first_mes") and not card_data.get("alternate_greetings"):
        issues.append(CardImportIssue(issue_id="no_greetings", severity=IssueSeverity.WARNING,
            category=IssueCategory.GREETING, message="No first_mes or alternate_greetings", source_path="data.first_mes"))
    cb = card_data.get("character_book")
    if cb is not None:
        if not isinstance(cb, dict):
            issues.append(CardImportIssue(issue_id="invalid_worldbook", severity=IssueSeverity.ERROR,
                category=IssueCategory.WORLDBOOK, message=f"'character_book' must be dict", source_path="data.character_book"))
        elif "entries" in cb and not isinstance(cb["entries"], list):
            issues.append(CardImportIssue(issue_id="invalid_wb_entries", severity=IssueSeverity.ERROR,
                category=IssueCategory.WORLDBOOK, message="'entries' must be list", source_path="data.character_book.entries"))
    return issues
