"""Persistent store registry for the novel runtime."""

from __future__ import annotations

from ..storage.sqlite.database import Database
from ..storage.sqlite.active_memory_store import SqliteActiveMemoryStore
from ..storage.sqlite.rag_memory_store import SqliteRagMemoryStore
from ..storage.sqlite.novel_stores import (
    SqliteNovelProjectStore,
    SqliteNovelVolumeStore,
    SqliteNovelChapterPlanStore,
    SqliteNovelChapterDraftStore,
    SqliteNovelLedgerStore,
    SqliteNovelCharacterStore,
    SqliteNovelBatchProgressStore,
    SqliteNovelReferenceBookStore,
    SqliteNovelPlanStore,
)


class SessionRuntimeStoreRegistry:
    """Holds the novel and novel-memory stores for one database.

    Constructed once per Database instance. All stores share the same
    underlying SQLite connection. Thread-safe via SQLite's WAL mode.
    """

    def __init__(self, db: Database):
        self._db = db
        self.active_memory_store = SqliteActiveMemoryStore(db)
        self.rag_memory_store = SqliteRagMemoryStore(db)
        self.novel_project_store = SqliteNovelProjectStore(db)
        self.novel_volume_store = SqliteNovelVolumeStore(db)
        self.novel_chapter_plan_store = SqliteNovelChapterPlanStore(db)
        self.novel_chapter_draft_store = SqliteNovelChapterDraftStore(db)
        self.novel_ledger_store = SqliteNovelLedgerStore(db)
        self.novel_character_store = SqliteNovelCharacterStore(db)
        self.novel_batch_progress_store = SqliteNovelBatchProgressStore(db)
        self.novel_reference_book_store = SqliteNovelReferenceBookStore(db)
        self.novel_plan_store = SqliteNovelPlanStore(db)

    @property
    def db(self) -> Database:
        return self._db
