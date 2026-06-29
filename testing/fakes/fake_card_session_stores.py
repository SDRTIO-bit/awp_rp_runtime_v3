"""In-memory fake stores for card session bootstrap testing."""

from __future__ import annotations

from ...storage.card_session_interfaces import (
    CardSessionBindingStore, OpeningRecordStore,
    WorldbookBindingStore, BootstrapReceiptStore,
)
from ...contracts.card_session_binding import CardSessionBinding
from ...contracts.opening_record import OpeningRecord
from ...contracts.worldbook_binding import WorldbookBinding
from ...contracts.card_session_bootstrap_receipt import CardSessionBootstrapReceipt


class FakeCardSessionBindingStore(CardSessionBindingStore):
    def __init__(self):
        self._data: dict[str, CardSessionBinding] = {}

    def save(self, binding: CardSessionBinding) -> None:
        self._data[binding.session_id] = binding

    def load(self, session_id: str) -> CardSessionBinding | None:
        return self._data.get(session_id)

    def exists(self, session_id: str) -> bool:
        return session_id in self._data

    def list_all(self) -> list[CardSessionBinding]:
        return sorted(
            self._data.values(),
            key=lambda binding: getattr(binding, "created_at", ""),
            reverse=True,
        )


class FakeOpeningRecordStore(OpeningRecordStore):
    def __init__(self):
        self._data: dict[str, OpeningRecord] = {}
        self._by_session: dict[str, OpeningRecord] = {}

    def save(self, record: OpeningRecord) -> None:
        self._data[record.opening_record_id] = record
        self._by_session[record.session_id] = record

    def load(self, opening_record_id: str) -> OpeningRecord | None:
        return self._data.get(opening_record_id)

    def get_by_session(self, session_id: str) -> OpeningRecord | None:
        return self._by_session.get(session_id)


class FakeWorldbookBindingStore(WorldbookBindingStore):
    def __init__(self):
        self._data: dict[str, WorldbookBinding] = {}
        self._by_session: dict[str, WorldbookBinding] = {}

    def save(self, binding: WorldbookBinding) -> None:
        self._data[binding.worldbook_binding_id] = binding
        self._by_session[binding.session_id] = binding

    def load(self, worldbook_binding_id: str) -> WorldbookBinding | None:
        return self._data.get(worldbook_binding_id)

    def get_by_session(self, session_id: str) -> WorldbookBinding | None:
        return self._by_session.get(session_id)


class FakeBootstrapReceiptStore(BootstrapReceiptStore):
    def __init__(self):
        self._data: dict[str, CardSessionBootstrapReceipt] = {}
        self._by_request: dict[str, CardSessionBootstrapReceipt] = {}

    def save(self, receipt: CardSessionBootstrapReceipt) -> None:
        self._data[receipt.receipt_id] = receipt
        self._by_request[receipt.request_id] = receipt

    def load(self, receipt_id: str) -> CardSessionBootstrapReceipt | None:
        return self._data.get(receipt_id)

    def get_by_request(self, request_id: str) -> CardSessionBootstrapReceipt | None:
        return self._by_request.get(request_id)
