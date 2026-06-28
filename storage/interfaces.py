"""Storage interfaces — abstract contracts for all stores.

Implementations must be swappable (SQLite, in-memory for tests).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..contracts.card_state import CardState
from ..contracts.card_state_commit import CardStateCommitRequest, CardStateCommitResult
from ..contracts.turn_record import TurnRecord
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.active_memory import ActiveMemoryRecord, ActiveMemoryEntry
from ..contracts.rag_memory import RagMemoryRecord, RagMemoryEntry
from ..contracts.memory_commit_plan import (
    ActiveMemoryEntry as _LegacyActiveEntry,
    RagMemoryEntry as _LegacyRagEntry,
    MemoryCommitReceipt,
)
from ..contracts.memory_recall_request import MemoryRecallRequest
from ..contracts.memory_recall_result import MemoryRecallResult
from ..contracts.memory_retention_decision import MemoryRetentionResult
from ..contracts.execution_trace import ExecutionTrace


class CardStateStore(ABC):
    """Interface for CardState persistence."""

    @abstractmethod
    def initialize(
        self, card_id: str, session_id: str, greeting: str = ""
    ) -> CardState:
        """Initialize a new CardState. Idempotent."""
        ...

    @abstractmethod
    def load(self, card_id: str, session_id: str) -> CardState | None:
        """Load current CardState. Returns None if not found."""
        ...

    @abstractmethod
    def commit(
        self,
        request: CardStateCommitRequest,
        new_state: CardState,
    ) -> CardStateCommitResult:
        """Commit a state update atomically.

        Must check: revision, patchId, validate all ops, write receipt in same tx.
        """
        ...

    @abstractmethod
    def get_patch_log(self, card_id: str, session_id: str) -> list[dict[str, Any]]:
        """Get all patch receipts for a card+session."""
        ...


class TurnRecordStore(ABC):
    """Interface for TurnRecord persistence."""

    @abstractmethod
    def save(self, record: TurnRecord) -> None:
        """Save a turn record. Raises DuplicateTurnError if turn_id exists."""
        ...

    @abstractmethod
    def load(self, turn_id: str) -> TurnRecord | None:
        """Load a turn record by ID."""
        ...

    @abstractmethod
    def get_recent(
        self, card_id: str, session_id: str, limit: int = 5
    ) -> list[TurnRecord]:
        """Get most recent turn records, newest first."""
        ...

    @abstractmethod
    def get_last_accepted(
        self, card_id: str, session_id: str
    ) -> TurnRecord | None:
        """Get the last accepted turn record."""
        ...

    @abstractmethod
    def get_next_turn_index(self, card_id: str, session_id: str) -> int:
        """Get the next turn index for this card+session."""
        ...

    @abstractmethod
    def list_by_session(self, session_id: str) -> list[TurnRecord]:
        """List all turns for a session, ordered by turn_index ascending."""
        ...


class RoundSnapshotStore(ABC):
    """Interface for RoundSnapshot persistence."""

    @abstractmethod
    def save(self, snapshot: RoundSnapshot) -> None:
        """Save a round snapshot."""
        ...

    @abstractmethod
    def load(self, snapshot_id: str) -> RoundSnapshot | None:
        """Load a snapshot by ID."""
        ...


class ActiveMemoryStore(ABC):
    """Interface for active memory persistence."""

    @abstractmethod
    def get_all(self, card_id: str, session_id: str) -> list[ActiveMemoryEntry]:
        ...

    @abstractmethod
    def upsert(self, card_id: str, session_id: str, entry: ActiveMemoryEntry) -> None:
        ...

    @abstractmethod
    def resolve(self, card_id: str, session_id: str, memory_id: str) -> None:
        ...

    @abstractmethod
    def delete(self, card_id: str, session_id: str, memory_id: str) -> None:
        ...

    @abstractmethod
    def get_active_count(self, card_id: str, session_id: str) -> int:
        """Number of active memories for this card+session."""
        ...

    @abstractmethod
    def set_status(
        self, card_id: str, session_id: str, memory_id: str, status: str, reason: str = ""
    ) -> None:
        """Set lifecycle status (active/resolved/superseded/expired/evicted/conflicted)."""
        ...

    @abstractmethod
    def touch_recall(self, card_id: str, session_id: str, memory_id: str) -> None:
        """Mark a memory as recalled (update last_recalled_at, recall_count)."""
        ...

    @abstractmethod
    def recall(self, card_id: str, session_id: str, request: MemoryRecallRequest) -> MemoryRecallResult:
        """Deterministic recall with filters. Excludes stale by default."""
        ...

    @abstractmethod
    def record_receipt(self, receipt: MemoryCommitReceipt) -> None:
        """Persist an idempotent commit receipt."""
        ...

    @abstractmethod
    def get_receipt_by_idempotency_key(
        self, card_id: str, session_id: str, idempotency_key: str
    ) -> MemoryCommitReceipt | None:
        ...


class RagMemoryStore(ABC):
    """Interface for RAG memory persistence."""

    @abstractmethod
    def save(self, card_id: str, session_id: str, entry: RagMemoryEntry) -> None:
        ...

    @abstractmethod
    def search(self, card_id: str, session_id: str, query: str, limit: int = 10) -> list[RagMemoryEntry]:
        ...

    @abstractmethod
    def get_by_entity(self, card_id: str, session_id: str, entity: str) -> list[RagMemoryEntry]:
        ...

    @abstractmethod
    def set_status(
        self, card_id: str, session_id: str, memory_id: str, status: str
    ) -> None:
        ...

    @abstractmethod
    def touch_recall(self, card_id: str, session_id: str, memory_id: str) -> None:
        ...

    @abstractmethod
    def recall(self, card_id: str, session_id: str, request: MemoryRecallRequest) -> MemoryRecallResult:
        """FTS5 + entity/alias/tag/status/scope filters, deterministically ordered."""
        ...

    @abstractmethod
    def record_receipt(self, receipt: MemoryCommitReceipt) -> None:
        ...

    @abstractmethod
    def get_receipt_by_idempotency_key(
        self, card_id: str, session_id: str, idempotency_key: str
    ) -> MemoryCommitReceipt | None:
        ...


class TraceStore(ABC):
    """Interface for execution trace persistence."""

    @abstractmethod
    def save(self, trace: ExecutionTrace) -> None:
        ...

    @abstractmethod
    def load(self, trace_id: str) -> ExecutionTrace | None:
        ...

    @abstractmethod
    def get_by_turn(self, turn_id: str) -> ExecutionTrace | None:
        ...


class RecallLogStore(ABC):
    """Interface for memory recall diagnostics persistence."""

    @abstractmethod
    def log_recall(self, result: MemoryRecallResult) -> None:
        ...

    @abstractmethod
    def get_recent(self, card_id: str, session_id: str, limit: int = 20) -> list[dict]:
        ...


class RetentionDecisionStore(ABC):
    """Interface for retention decision audit persistence."""

    @abstractmethod
    def log_retention(self, result: MemoryRetentionResult) -> None:
        ...

    @abstractmethod
    def get_by_turn(self, card_id: str, session_id: str, turn_id: str) -> list[dict]:
        ...


# Custom exceptions
class RevisionConflictError(Exception):
    def __init__(self, expected: int, actual: int):
        self.expected = expected
        self.actual = actual
        super().__init__(f"Revision conflict: expected {expected}, got {actual}")


class DuplicatePatchError(Exception):
    def __init__(self, patch_id: str):
        self.patch_id = patch_id
        super().__init__(f"Duplicate patch: {patch_id}")


class DuplicateTurnError(Exception):
    def __init__(self, turn_id: str):
        self.turn_id = turn_id
        super().__init__(f"Duplicate turn: {turn_id}")
