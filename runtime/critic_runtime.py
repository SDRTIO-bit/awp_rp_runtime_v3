"""CriticRuntime — quality gate for candidate text.

Checks:
- Minimum length
- Format compliance
- Character consistency
- Scene consistency
- No tool output / JSON / debug info
"""

from __future__ import annotations

from typing import Any

from ..contracts.quality_decision import QualityDecision, QualityVerdict
from ..contracts.round_snapshot import RoundSnapshot


class CriticRuntime:
    """Quality gate runtime.

    Checks candidate text before any state/memory writes.
    Only accepted text proceeds to commits.
    """

    def __init__(self, llm_provider: Any):
        self.llm_provider = llm_provider

    def check(
        self,
        candidate_text: str,
        snapshot: RoundSnapshot,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> QualityDecision:
        """Run quality checks on candidate text.

        Returns QualityDecision with verdict and details.
        """
        # Run LLM-based quality check
        decision = self.llm_provider.check_quality(candidate_text)

        # Set retry info
        decision.turn_id = snapshot.trace_id
        decision.retry_count = retry_count
        decision.max_retries = max_retries

        # Run deterministic checks
        deterministic_checks = self._run_deterministic_checks(candidate_text, snapshot)
        decision.checks.extend(deterministic_checks)

        # If any deterministic check fails, override to rejected
        if any(not c["passed"] for c in deterministic_checks):
            decision.verdict = QualityVerdict.REJECTED
            decision.rejection_reasons.extend(
                c["details"] for c in deterministic_checks if not c["passed"]
            )

        return decision

    def _run_deterministic_checks(
        self, text: str, snapshot: RoundSnapshot
    ) -> list[dict[str, Any]]:
        """Run deterministic (non-LLM) quality checks."""
        checks = []

        # Length check
        min_len = 100  # Minimum for testing
        checks.append({
            "name": "min_length",
            "passed": len(text) >= min_len,
            "details": f"Length {len(text)} {'>=' if len(text) >= min_len else '<'} min {min_len}",
        })

        # No JSON check
        has_json = "{" in text and "}" in text and ":" in text
        checks.append({
            "name": "no_json",
            "passed": not has_json,
            "details": "Contains JSON-like content" if has_json else "No JSON detected",
        })

        # No debug markers
        debug_markers = ["DEBUG", "TODO", "FIXME", "```"]
        has_debug = any(marker in text for marker in debug_markers)
        checks.append({
            "name": "no_debug",
            "passed": not has_debug,
            "details": "Contains debug markers" if has_debug else "No debug markers",
        })

        return checks
