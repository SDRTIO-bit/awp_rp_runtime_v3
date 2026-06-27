"""WorldbookService — coordinates worldbook operations."""

from __future__ import annotations

from typing import Any


class WorldbookService:
    """Coordinates worldbook operations."""

    def get_active_entries(
        self,
        card_state: dict[str, Any],
        worldbook_entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Get active worldbook entries based on CardState conditions.

        V1: returns all entries (condition evaluation is TODO).
        """
        return worldbook_entries
