"""MemoryService — coordinates memory operations."""

from __future__ import annotations

from ..contracts.memory_commit_plan import ActiveMemoryEntry, RagMemoryEntry
from ..storage.interfaces import ActiveMemoryStore, RagMemoryStore


class MemoryService:
    """Coordinates memory operations."""

    def __init__(
        self,
        active_store: ActiveMemoryStore,
        rag_store: RagMemoryStore,
    ):
        self.active_store = active_store
        self.rag_store = rag_store

    def get_active_memories(
        self, card_id: str, session_id: str
    ) -> list[ActiveMemoryEntry]:
        """Get all active memories."""
        return self.active_store.get_all(card_id, session_id)

    def search_rag(
        self, card_id: str, session_id: str, query: str, limit: int = 10
    ) -> list[RagMemoryEntry]:
        """Search RAG memories."""
        return self.rag_store.search(card_id, session_id, query, limit)
