"""RetryRuntime — handles turn retry on quality gate rejection.

Retry does NOT duplicate state or memory writes.
It only re-runs the writer with feedback from the rejection.
"""

from __future__ import annotations

from ..contracts.quality_decision import QualityDecision
from ..policies.retry_policy import RetryPolicy, RetryValidation


class RetryRuntime:
    """Handles turn retry on quality gate rejection."""

    def __init__(self, policy: RetryPolicy | None = None):
        self.policy = policy or RetryPolicy()

    def can_retry(self, quality_decision: QualityDecision) -> RetryValidation:
        """Check if retry is allowed based on current retry count."""
        return self.policy.can_retry(quality_decision.retry_count)

    def build_retry_context(self, quality_decision: QualityDecision) -> str:
        """Build context for retry from rejection details."""
        parts = ["Previous attempt was rejected:"]
        for reason in quality_decision.rejection_reasons:
            parts.append(f"- {reason}")
        parts.append("Please address these issues in the new attempt.")
        return "\n".join(parts)
