"""RagMemoryRecallRuntime — deterministic L3 recall (FTS5 + filters).

Uses SQLite FTS5 (or the store's keyword search) as the real V1 retrieval.
An optional EmbeddingRetrievalAdapter interface is reserved for future vector
retrieval, but M1 must NOT force a paid embedding API.

Recall is always scoped to cardId+sessionId. resolved/expired/conflicted records
are downgraded (excluded from high-priority results) by default. Any hit
conflicting with CardState is downgraded/ignored by the MemoryContextAssembler,
never by free LLM judgement.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..contracts.memory_recall_request import MemoryRecallRequest
from ..contracts.memory_recall_result import MemoryRecallResult
from ..storage.interfaces import RagMemoryStore, RecallLogStore


class EmbeddingRetrievalAdapter(Protocol):
    """Reserved for future vector retrieval. NOT required in M1.

    M1 must not force a paid embedding API. This interface exists only so a
    future adapter can be plugged in without changing the recall contract.
    """

    def embed(self, text: str) -> list[float]:
        ...

    def search(self, card_id: str, session_id: str, vector: list[float], limit: int) -> list[dict[str, Any]]:
        ...


class RagMemoryRecallRuntime:

    def __init__(
        self,
        store: RagMemoryStore,
        recall_log: RecallLogStore | None = None,
        embedding_adapter: EmbeddingRetrievalAdapter | None = None,
    ):
        self.store = store
        self.recall_log = recall_log
        # Reserved for future use; M1 does not invoke it.
        self.embedding_adapter = embedding_adapter

    def recall(self, request: MemoryRecallRequest) -> MemoryRecallResult:
        """Recall RAG memories deterministically. card+session scoped.

        In M1 the real retrieval is the store's FTS5/keyword search. The
        embedding adapter is intentionally NOT used even if provided.
        """
        result = self.store.recall(request.card_id, request.session_id, request)
        if self.recall_log is not None:
            self.recall_log.log_recall(result)
        return result
