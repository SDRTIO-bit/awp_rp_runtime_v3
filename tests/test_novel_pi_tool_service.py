import pytest

from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_draft import ChapterDraft
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_pi_tool_service import NovelPiToolService
from awp_rp_runtime_v3.storage.sqlite.database import Database
from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry


@pytest.fixture
def reg(tmp_path):
    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    registry.novel_project_store.create(NovelProject(project_id="p1", title="测试小说"))
    registry.novel_chapter_plan_store.save(
        ChapterPlan(chapter_id="ch1", project_id="p1", chapter_index=1, target_chars=100)
    )
    return registry


def test_write_routes_through_streaming_engine(monkeypatch, reg):
    calls = []

    monkeypatch.setattr(
        NovelEngine,
        "write_chapter_stream",
        lambda self, **kwargs: calls.append(kwargs)
        or ChapterDraft(text="正文", char_count=2, status="accepted"),
    )

    result = NovelPiToolService(reg, project_id="p1").execute(
        "write_chapter", {"chapter": 1}
    )

    assert result["ok"] is True
    assert calls == [{"project_id": "p1", "chapter_index": 1, "write_guidance": ""}]


def test_audit_does_not_create_draft(monkeypatch, reg):
    monkeypatch.setattr(
        NovelEngine,
        "audit_chapter",
        lambda self, **kwargs: {"chapter": kwargs["chapter_index"], "verdict": "accept"},
    )

    result = NovelPiToolService(reg, project_id="p1").execute(
        "audit_chapter", {"chapter": 1}
    )

    assert result["ok"] is True
    assert reg.novel_chapter_draft_store.load_latest("ch1") is None


def test_service_refuses_unbound_or_unapproved_tool(reg):
    service = NovelPiToolService(reg, project_id="p1")

    with pytest.raises(ValueError, match="not allowed"):
        service.execute("fetch_url", {"url": "https://example.invalid"})
