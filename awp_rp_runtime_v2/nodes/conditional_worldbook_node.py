"""ConditionalWorldbookNode — filters worldbook entries by CardState conditions.

Input: card_state, worldbook_entries
Output: active_worldbook_entries
"""

from __future__ import annotations

from typing import Any


class ConditionalWorldbookNode:
    """Filter worldbook entries based on CardState conditions."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "card_state": ("CARD_STATE",),
                "worldbook_entries": ("WORLDBOOK_ENTRIES",),
            },
        }

    RETURN_TYPES = ("WORLDBOOK_ENTRIES",)
    RETURN_NAMES = ("active_entries",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        card_state: dict[str, Any],
        worldbook_entries: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]]]:
        """Filter entries by conditions.

        First-match-wins within branchGroupId.
        V1: simple condition check (no eval/exec).
        """
        # For V1, return all entries (condition evaluation is TODO)
        return (worldbook_entries,)
