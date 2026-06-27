"""Adapters for external systems.

These interfaces define boundaries for LLM providers, ComfyUI integration,
character cards, worldbooks, and presets. Implementations are swappable.
"""

from .llm_provider import LLMProviderInterface
from .comfyui import ComfyUIAdapter
from .character_card import CharacterCardAdapter
from .worldbook import WorldbookAdapter
from .preset import PresetAdapter

__all__ = [
    "LLMProviderInterface",
    "ComfyUIAdapter",
    "CharacterCardAdapter",
    "WorldbookAdapter",
    "PresetAdapter",
]
