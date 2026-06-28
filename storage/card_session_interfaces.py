"""Card session storage interfaces — abstract contracts for session bootstrap stores.

Implementations must be swappable (SQLite, in-memory for tests).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..contracts.card_session_binding import CardSessionBinding
from ..contracts.opening_record import OpeningRecord
from ..contracts.worldbook_binding import WorldbookBinding
from ..contracts.card_session_bootstrap_receipt import CardSessionBootstrapReceipt


class CardSessionBindingStore(ABC):
    """Interface for CardSessionBinding persistence."""

    @abstractmethod
    def save(self, binding: CardSessionBinding) -> None:
        ...

    @abstractmethod
    def load(self, session_id: str) -> CardSessionBinding | None:
        ...

    @abstractmethod
    def exists(self, session_id: str) -> bool:
        ...

    @abstractmethod
    def list_all(self) -> list[CardSessionBinding]:
        """List all session bindings, newest first."""
        ...


class OpeningRecordStore(ABC):
    """Interface for OpeningRecord persistence."""

    @abstractmethod
    def save(self, record: OpeningRecord) -> None:
        ...

    @abstractmethod
    def load(self, opening_record_id: str) -> OpeningRecord | None:
        ...

    @abstractmethod
    def get_by_session(self, session_id: str) -> OpeningRecord | None:
        ...


class WorldbookBindingStore(ABC):
    """Interface for WorldbookBinding persistence."""

    @abstractmethod
    def save(self, binding: WorldbookBinding) -> None:
        ...

    @abstractmethod
    def load(self, worldbook_binding_id: str) -> WorldbookBinding | None:
        ...

    @abstractmethod
    def get_by_session(self, session_id: str) -> WorldbookBinding | None:
        ...


class BootstrapReceiptStore(ABC):
    """Interface for CardSessionBootstrapReceipt persistence."""

    @abstractmethod
    def save(self, receipt: CardSessionBootstrapReceipt) -> None:
        ...

    @abstractmethod
    def load(self, receipt_id: str) -> CardSessionBootstrapReceipt | None:
        ...

    @abstractmethod
    def get_by_request(self, request_id: str) -> CardSessionBootstrapReceipt | None:
        ...
