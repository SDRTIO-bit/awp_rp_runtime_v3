"""Card import storage interfaces — abstract contracts for card import stores.

Implementations must be swappable (SQLite, in-memory for tests).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..contracts.card_definition import CardDefinition
from ..contracts.card_source_snapshot import CardSourceSnapshot
from ..contracts.card_import_report import CardImportReport


class CardDefinitionStore(ABC):
    """Interface for CardDefinition persistence."""

    @abstractmethod
    def save(self, definition: CardDefinition) -> None:
        """Save a card definition. Overwrites if same card_id + card_version."""
        ...

    @abstractmethod
    def load(self, card_id: str, card_version: int) -> CardDefinition | None:
        """Load a card definition by ID and version. Returns None if not found."""
        ...

    @abstractmethod
    def get_latest(self, card_id: str) -> CardDefinition | None:
        """Load the latest version of a card definition. Returns None if not found."""
        ...

    @abstractmethod
    def get_by_source_hash(self, source_hash: str) -> CardDefinition | None:
        """Load a card definition by source hash. Returns None if not found."""
        ...

    @abstractmethod
    def list_all(self, status: str = "") -> list[CardDefinition]:
        """List all card definitions, optionally filtered by status."""
        ...

    @abstractmethod
    def update_status(self, card_id: str, card_version: int, status: str) -> None:
        """Update the status of a card definition."""
        ...

    @abstractmethod
    def get_next_version(self, card_id: str) -> int:
        """Get the next version number for a card ID."""
        ...


class CardSourceStore(ABC):
    """Interface for CardSourceSnapshot persistence."""

    @abstractmethod
    def save(self, snapshot: CardSourceSnapshot) -> None:
        """Save a source snapshot."""
        ...

    @abstractmethod
    def load(self, source_id: str) -> CardSourceSnapshot | None:
        """Load a source snapshot by ID. Returns None if not found."""
        ...

    @abstractmethod
    def get_by_hash(self, source_hash: str) -> CardSourceSnapshot | None:
        """Load a source snapshot by hash. Returns None if not found."""
        ...


class CardImportReportStore(ABC):
    """Interface for CardImportReport persistence."""

    @abstractmethod
    def save(self, report: CardImportReport) -> None:
        """Save an import report."""
        ...

    @abstractmethod
    def load(self, report_id: str) -> CardImportReport | None:
        """Load an import report by ID. Returns None if not found."""
        ...

    @abstractmethod
    def get_by_card(self, card_id: str, card_version: int = 0) -> list[CardImportReport]:
        """Get import reports for a card. If card_version is 0, returns all versions."""
        ...
