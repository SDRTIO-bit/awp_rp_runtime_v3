"""ComfyUI History Collector — parses /history/{promptId} responses.

Extracts node-level execution results from ComfyUI's history API.
"""

from __future__ import annotations

from typing import Any


class ComfyHistoryCollector:
    """Parse and query ComfyUI history data."""

    def __init__(self) -> None:
        self._history: dict[str, Any] = {}

    def load(self, history_data: dict[str, Any]) -> None:
        """Load history data from /history/{promptId} response."""
        self._history = history_data or {}

    def get_output_nodes(self) -> dict[str, Any]:
        """Get all output nodes from the history."""
        outputs = {}
        for prompt_id, prompt_data in self._history.items():
            prompt_outputs = prompt_data.get("outputs", {})
            for node_id, node_output in prompt_outputs.items():
                outputs[node_id] = node_output
        return outputs

    def get_node_output(self, node_id: str) -> dict[str, Any] | None:
        """Get output for a specific node."""
        for prompt_id, prompt_data in self._history.items():
            outputs = prompt_data.get("outputs", {})
            if node_id in outputs:
                return outputs[node_id]
        return None

    def get_execution_status(self) -> dict[str, str]:
        """Get execution status for all nodes."""
        status = {}
        for prompt_id, prompt_data in self._history.items():
            status_info = prompt_data.get("status", {})
            status_str = status_info.get("status_str", "unknown")
            status[prompt_id] = status_str
        return status

    def get_prompt_ids(self) -> list[str]:
        """Get all prompt IDs in the history."""
        return list(self._history.keys())

    def has_prompt(self, prompt_id: str) -> bool:
        """Check if a prompt_id exists in history."""
        return prompt_id in self._history
