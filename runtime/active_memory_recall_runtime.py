"""ActiveMemoryRecallRuntime — deterministic L2 recall.

Reads active memories scoped to cardId+sessionId, applies deterministic filters
(entity / status / importance / confidence / query), and returns a
MemoryRecallResult with diagnostics. Never queries other sessions or cards.
"""

from __future__ import annotations

from ..contracts.memory_recall_request import MemoryRecallRequest
from ..contracts.memory_recall_result import MemoryRecallResult
from ..storage.interfaces import ActiveMemoryStore, RecallLogStore


class ActiveMemoryRecallRuntime:

    def __init__(self, store: ActiveMemoryStore, recall_log: RecallLogStore | None = None):
        self.store = store
        self.recall_log = recall_log

    def recall(self, request: MemoryRecallRequest) -> MemoryRecallResult:
        """Recall active memories deterministically. card+session scoped."""
        result = self.store.recall(request.card_id, request.session_id, request)
        if self.recall_log is not None:
            self.recall_log.log_recall(result)
        return result
