"""Character card adapter — interface for loading character cards.

Supports multiple card formats (Tavern, CAI, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CharacterCardAdapter(ABC):
    """Interface for character card loading."""

    @abstractmethod
    def load_card(self, card_path: str) -> dict[str, Any]:
        """Load a character card from file."""
        ...

    @abstractmethod
    def get_character_name(self, card: dict[str, Any]) -> str:
        """Extract character name from card."""
        ...

    @abstractmethod
    def get_system_prompt(self, card: dict[str, Any]) -> str:
        """Extract system prompt from card."""
        ...
