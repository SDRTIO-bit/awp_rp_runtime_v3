"""Preset adapter — interface for loading presets.

Presets define style, length, format, and model configuration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PresetAdapter(ABC):
    """Interface for preset loading."""

    @abstractmethod
    def load_preset(self, preset_path: str) -> dict[str, Any]:
        """Load a preset from file."""
        ...

    @abstractmethod
    def get_style(self, preset: dict[str, Any]) -> str:
        """Get writing style from preset."""
        ...

    @abstractmethod
    def get_length_config(self, preset: dict[str, Any]) -> dict[str, int]:
        """Get min/max length config."""
        ...
