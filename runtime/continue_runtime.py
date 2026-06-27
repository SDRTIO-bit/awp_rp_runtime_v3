"""ContinueRuntime — handles turn continuation.

Continue must be based on the last accepted TurnRecord.
It does NOT duplicate state or memory writes.
"""

from __future__ import annotations

from ..contracts.turn_record import TurnRecord
from ..policies.retry_policy import RetryPolicy, RetryValidation
from ..storage.interfaces import TurnRecordStore


class ContinueRuntime:
    """Handles turn continuation."""

    def __init__(
        self,
        store: TurnRecordStore,
        policy: RetryPolicy | None = None,
    ):
        self.store = store
        self.policy = policy or RetryPolicy()

    def validate_continue(
        self,
        card_id: str,
        session_id: str,
        requested_turn_id: str | None = None,
    ) -> tuple[TurnRecord | None, RetryValidation]:
        """Validate that continue is based on last accepted turn.

        Returns (last_turn, validation).
        """
        last_turn = self.store.get_last_accepted(card_id, session_id)
        validation = self.policy.validate_continue(
            last_turn.turn_id if last_turn else None,
            requested_turn_id,
        )
        return last_turn, validation
