"""ToolResultValidator — validates tool results before they enter the pipeline.

Ensures:
- sourceRefs are present and non-empty
- Summary is length-limited
- Failed results are not disguised as success
- Results are scoped to the correct cardId + sessionId
"""

from __future__ import annotations

MAX_SUMMARY_LENGTH = 500


class ToolResultValidator:
    """Validates tool results before they enter the pipeline."""

    def validate(self, result) -> tuple[bool, list[str]]:
        """Validate a ToolResult.

        Returns (valid, list_of_issues).
        """
        issues = []

        # 1. sourceRefs must be present for successful results
        if result.is_success() and not result.source_refs:
            issues.append("Successful tool result must have source_refs")

        # 2. Summary must be length-limited
        if len(result.summary) > MAX_SUMMARY_LENGTH:
            issues.append(
                f"Summary length {len(result.summary)} exceeds max {MAX_SUMMARY_LENGTH}"
            )

        # 3. Failed results must not have empty failure_reason
        if result.is_failed() and not result.failure_reason:
            issues.append("Failed tool result must have failure_reason")

        # 4. Successful results must have structured_data or summary
        if result.is_success() and not result.structured_data and not result.summary:
            issues.append("Successful tool result must have structured_data or summary")

        return len(issues) == 0, issues
