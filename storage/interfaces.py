"""Abstract storage interfaces used by novel memory."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..contracts.active_memory import ActiveMemoryEntry
from ..contracts.memory_commit_plan import MemoryCommitReceipt
from ..contracts.memory_recall_request import MemoryRecallRequest
from ..contracts.memory_recall_result import MemoryRecallResult
from ..contracts.memory_retention_decision import MemoryRetentionResult
from ..contracts.rag_memory import RagMemoryEntry


class ActiveMemoryStore(ABC):
    @abstractmethod
    def get_all(self, card_id: str, session_id: str) -> list[ActiveMemoryEntry]:
        """Return active records for the novel memory scope."""

    @abstractmethod
    def upsert(
        self, card_id: str, session_id: str, entry: ActiveMemoryEntry
    ) -> None:
        """Create or replace an active-memory record."""

    @abstractmethod
    def resolve(self, card_id: str, session_id: str, memory_id: str) -> None:
        """Mark an active-memory record resolved."""

    @abstractmethod
    def delete(self, card_id: str, session_id: str, memory_id: str) -> None:
        """Delete one active-memory record."""

    @abstractmethod
    def get_active_count(self, card_id: str, session_id: str) -> int:
        """Count active records."""

    @abstractmethod
    def set_status(
        self,
        card_id: str,
        session_id: str,
        memory_id: str,
        status: str,
        reason: str = "",
    ) -> None:
        """Update lifecycle status."""

    @abstractmethod
    def touch_recall(self, card_id: str, session_id: str, memory_id: str) -> None:
        """Record one recall."""

    @abstractmethod
    def recall(
        self, card_id: str, session_id: str, request: MemoryRecallRequest
    ) -> MemoryRecallResult:
        """Recall matching active-memory records."""

    @abstractmethod
    def record_receipt(self, receipt: MemoryCommitReceipt) -> None:
        """Persist an idempotent commit receipt."""

    @abstractmethod
    def get_receipt_by_idempotency_key(
        self, card_id: str, session_id: str, idempotency_key: str
    ) -> MemoryCommitReceipt | None:
        """Load a prior commit receipt."""


class RagMemoryStore(ABC):
    @abstractmethod
    def save(self, card_id: str, session_id: str, entry: RagMemoryEntry) -> None:
        """Create or replace a RAG-memory record."""

    @abstractmethod
    def search(
        self,
        card_id: str,
        session_id: str,
        query: str,
        limit: int = 10,
    ) -> list[RagMemoryEntry]:
        """Search active RAG-memory records."""

    @abstractmethod
    def get_by_entity(
        self, card_id: str, session_id: str, entity: str
    ) -> list[RagMemoryEntry]:
        """Return records mentioning an entity."""

    @abstractmethod
    def set_status(
        self, card_id: str, session_id: str, memory_id: str, status: str
    ) -> None:
        """Update lifecycle status."""

    @abstractmethod
    def touch_recall(self, card_id: str, session_id: str, memory_id: str) -> None:
        """Record one recall."""

    @abstractmethod
    def recall(
        self, card_id: str, session_id: str, request: MemoryRecallRequest
    ) -> MemoryRecallResult:
        """Recall matching RAG-memory records."""

    @abstractmethod
    def record_receipt(self, receipt: MemoryCommitReceipt) -> None:
        """Persist an idempotent commit receipt."""

    @abstractmethod
    def get_receipt_by_idempotency_key(
        self, card_id: str, session_id: str, idempotency_key: str
    ) -> MemoryCommitReceipt | None:
        """Load a prior commit receipt."""


class RecallLogStore(ABC):
    @abstractmethod
    def log_recall(self, result: MemoryRecallResult) -> None:
        """Persist recall diagnostics."""


class RetentionDecisionStore(ABC):
    @abstractmethod
    def log_retention(self, result: MemoryRetentionResult) -> None:
        """Persist a retention decision."""
