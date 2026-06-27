"""RetryPolicy — rules for retry and continue operations.

Enforces:
- Max retries per turn
- Continue must be based on last accepted turn
- Retry does not duplicate state/memory writes
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetryValidation:
    """Result of retry policy validation."""
    valid: bool
    errors: list[str]


class RetryPolicy:
    """Policy for retry and continue operations.

    Pure policy — no side effects, no I/O.
    """

    MAX_RETRIES = 3

    def can_retry(self, current_retry_count: int) -> RetryValidation:
        """Check if a retry is allowed."""
        errors = []
        if current_retry_count >= self.MAX_RETRIES:
            errors.append(
                f"Max retries exceeded: {current_retry_count} >= {self.MAX_RETRIES}"
            )
        return RetryValidation(valid=len(errors) == 0, errors=errors)

    def validate_continue(
        self,
        last_turn_id: str | None,
        requested_turn_id: str | None,
    ) -> RetryValidation:
        """Validate that continue is based on last accepted turn."""
        errors = []
        if last_turn_id is None:
            errors.append("No previous turn to continue from")
        elif requested_turn_id is not None and requested_turn_id != last_turn_id:
            errors.append(
                f"Continue must be based on last accepted turn: "
                f"expected {last_turn_id}, got {requested_turn_id}"
            )
        return RetryValidation(valid=len(errors) == 0, errors=errors)
