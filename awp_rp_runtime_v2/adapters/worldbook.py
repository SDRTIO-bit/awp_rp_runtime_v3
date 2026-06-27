"""Worldbook adapter — interface for loading worldbook entries.

Supports conditional entries with branchGroupId and branchOrder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class WorldbookAdapter(ABC):
    """Interface for worldbook loading."""

    @abstractmethod
    def load_worldbook(self, worldbook_path: str) -> list[dict[str, Any]]:
        """Load worldbook entries from file."""
        ...

    @abstractmethod
    def filter_by_conditions(
        self,
        entries: list[dict[str, Any]],
        card_state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Filter entries by CardState conditions (first-match-wins)."""
        ...
