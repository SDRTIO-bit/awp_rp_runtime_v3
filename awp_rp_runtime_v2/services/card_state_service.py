"""CardStateService — coordinates CardState operations.

High-level service that coordinates store, policy, and runtime.
"""

from __future__ import annotations

from ..contracts.card_state import CardState
from ..storage.interfaces import CardStateStore


class CardStateService:
    """Coordinates CardState operations."""

    def __init__(self, store: CardStateStore):
        self.store = store

    def initialize(self, card_id: str, session_id: str, greeting: str = "") -> CardState:
        """Initialize or load CardState."""
        return self.store.initialize(card_id, session_id, greeting)

    def load(self, card_id: str, session_id: str) -> CardState | None:
        """Load current CardState."""
        return self.store.load(card_id, session_id)

    def get_revision(self, card_id: str, session_id: str) -> int:
        """Get current revision number."""
        state = self.store.load(card_id, session_id)
        return state.revision if state else 0
