"""In-memory fake stores for card import testing."""

from __future__ import annotations

from ...storage.card_import_interfaces import CardDefinitionStore, CardSourceStore, CardImportReportStore
from ...contracts.card_definition import CardDefinition
from ...contracts.card_source_snapshot import CardSourceSnapshot
from ...contracts.card_import_report import CardImportReport


class FakeCardDefinitionStore(CardDefinitionStore):
    def __init__(self):
        self._data: dict[tuple[str, int], CardDefinition] = {}

    def save(self, d: CardDefinition) -> None:
        self._data[(d.card_id, d.card_version)] = d

    def load(self, card_id: str, card_version: int) -> CardDefinition | None:
        return self._data.get((card_id, card_version))

    def get_latest(self, card_id: str) -> CardDefinition | None:
        ms = [d for (cid, _), d in self._data.items() if cid == card_id]
        return max(ms, key=lambda d: d.card_version) if ms else None

    def get_by_source_hash(self, h: str) -> CardDefinition | None:
        for d in self._data.values():
            if d.source_hash == h:
                return d
        return None

    def list_all(self, status: str = "") -> list[CardDefinition]:
        r = list(self._data.values())
        if status:
            r = [d for d in r if d.status == status]
        return sorted(r, key=lambda d: (d.card_id, d.card_version))

    def update_status(self, card_id: str, card_version: int, status: str) -> None:
        k = (card_id, card_version)
        if k in self._data:
            o = self._data[k]
            self._data[k] = CardDefinition(
                schema_id=o.schema_id, schema_version=o.schema_version,
                card_id=o.card_id, card_version=o.card_version,
                source_id=o.source_id, source_hash=o.source_hash,
                name=o.name, display_name=o.display_name, status=status,
                profile=dict(o.profile), greetings=list(o.greetings),
                worldbook_catalog=list(o.worldbook_catalog),
                worldbook_chunks=list(o.worldbook_chunks),
                structure_hints=dict(o.structure_hints),
                quarantine_summary=dict(o.quarantine_summary),
                import_report_ref=o.import_report_ref,
                created_at=o.created_at, updated_at=o.updated_at, trace_id=o.trace_id,
            )

    def get_next_version(self, card_id: str) -> int:
        return max((cv for (cid, cv) in self._data if cid == card_id), default=0) + 1


class FakeCardSourceStore(CardSourceStore):
    def __init__(self):
        self._data: dict[str, CardSourceSnapshot] = {}

    def save(self, s: CardSourceSnapshot) -> None:
        self._data[s.source_id] = s

    def load(self, source_id: str) -> CardSourceSnapshot | None:
        return self._data.get(source_id)

    def get_by_hash(self, h: str) -> CardSourceSnapshot | None:
        for s in self._data.values():
            if s.source_hash == h:
                return s
        return None


class FakeCardImportReportStore(CardImportReportStore):
    def __init__(self):
        self._data: dict[str, CardImportReport] = {}

    def save(self, r: CardImportReport) -> None:
        self._data[r.report_id] = r

    def load(self, report_id: str) -> CardImportReport | None:
        return self._data.get(report_id)

    def get_by_card(self, card_id: str, card_version: int = 0) -> list[CardImportReport]:
        rs = [r for r in self._data.values() if r.card_id == card_id]
        if card_version > 0:
            rs = [r for r in rs if r.card_version == card_version]
        return sorted(rs, key=lambda r: r.card_version)
