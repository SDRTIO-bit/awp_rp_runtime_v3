"""ComfyUI WebSocket Collector — collects execution events from ComfyUI WS.

Listens for:
  - executing (node started)
  - executed (node completed)
  - cached (node used cache)
  - error (node failed)
  - progress (progress updates)
  - execution_complete (all done)

Only used by comfy-api-e2e suite.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any


class ComfyWebSocketCollector:
    """Collect ComfyUI WebSocket execution events.

    In V1, this is a stub that can be used with a real WebSocket connection
    or can be populated manually for testing.
    """

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._events_by_type: dict[str, list[dict[str, Any]]] = {}
        self._prompt_id: str = ""
        self._completed: bool = False
        self._error: str | None = None
        self._lock = threading.Lock()

    def set_prompt_id(self, prompt_id: str) -> None:
        self._prompt_id = prompt_id

    def add_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Add an event (called by WS handler or test fixture)."""
        with self._lock:
            event = {
                "event_type": event_type,
                "timestamp": time.time(),
                "prompt_id": self._prompt_id,
                "data": data,
            }
            self._events.append(event)
            if event_type not in self._events_by_type:
                self._events_by_type[event_type] = []
            self._events_by_type[event_type].append(event)

            if event_type == "execution_complete":
                self._completed = True
            elif event_type == "execution_error":
                self._completed = True
                self._error = data.get("error", "unknown error")

    def get_all_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)

    def get_events_by_type(self, event_type: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events_by_type.get(event_type, []))

    def get_executed_nodes(self) -> list[str]:
        """Get list of node IDs that were executed."""
        with self._lock:
            return [
                e["data"].get("node_id", "")
                for e in self._events_by_type.get("executed", [])
            ]

    def get_cached_nodes(self) -> list[str]:
        """Get list of node IDs that used cache."""
        with self._lock:
            return [
                e["data"].get("node_id", "")
                for e in self._events_by_type.get("cached", [])
            ]

    def get_error_nodes(self) -> list[dict[str, Any]]:
        """Get list of nodes that errored."""
        with self._lock:
            return [
                {"node_id": e["data"].get("node_id", ""), "error": e["data"].get("error", "")}
                for e in self._events_by_type.get("error", [])
            ]

    def is_completed(self) -> bool:
        with self._lock:
            return self._completed

    def has_error(self) -> bool:
        with self._lock:
            return self._error is not None

    def get_error(self) -> str | None:
        with self._lock:
            return self._error

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._events_by_type.clear()
            self._completed = False
            self._error = None
