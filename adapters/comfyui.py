"""ComfyUI adapter — interface for ComfyUI integration.

This adapter bridges RP Runtime V2 with ComfyUI's node system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ComfyUIAdapter(ABC):
    """Interface for ComfyUI integration."""

    @abstractmethod
    def get_node_inputs(self, node_id: str) -> dict[str, Any]:
        """Get inputs for a node."""
        ...

    @abstractmethod
    def set_node_outputs(self, node_id: str, outputs: dict[str, Any]) -> None:
        """Set outputs for a node."""
        ...

    @abstractmethod
    def get_workflow_context(self) -> dict[str, Any]:
        """Get current workflow context."""
        ...
