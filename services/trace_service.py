"""TraceService — coordinates execution trace operations."""

from __future__ import annotations

from ..contracts.execution_trace import ExecutionTrace
from ..storage.interfaces import TraceStore


class TraceService:
    """Coordinates execution trace operations."""

    def __init__(self, store: TraceStore):
        self.store = store

    def save_trace(self, trace: ExecutionTrace) -> None:
        """Save an execution trace."""
        self.store.save(trace)

    def get_trace(self, trace_id: str) -> ExecutionTrace | None:
        """Get a trace by ID."""
        return self.store.load(trace_id)

    def get_turn_trace(self, turn_id: str) -> ExecutionTrace | None:
        """Get trace for a specific turn."""
        return self.store.get_by_turn(turn_id)
