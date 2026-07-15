import json

import pytest

from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_draft import ChapterDraft
from awp_rp_runtime_v3.contracts.novel_ledger import LedgerItem
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_pi_read_service import NovelPiReadService
from awp_rp_runtime_v3.runtime.novel_role_context import NovelRoleContext
from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from awp_rp_runtime_v3.storage.sqlite.database import Database


@pytest.fixture
def registry(tmp_path):
    database = Database(str(tmp_path / "novel.db"))
    database.initialize()
    reg = SessionRuntimeStoreRegistry(database)
    reg.novel_project_store.create(NovelProject(project_id="p1", title="本项目"))
    reg.novel_project_store.create(NovelProject(project_id="p2", title="其他项目"))
    reg.novel_chapter_plan_store.save(ChapterPlan(
        chapter_id="p1-ch1",
        project_id="p1",
        chapter_index=1,
        title="第一章",
    ))
    reg.novel_chapter_draft_store.save(ChapterDraft(
        draft_id="p1-d1",
        chapter_id="p1-ch1",
        text="只属于本项目的正文",
        char_count=9,
        status="accepted",
    ))
    reg.novel_character_store.save(NovelCharacter(
        character_id="p1-c1",
        project_id="p1",
        name="陈默",
    ))
    return reg


@pytest.fixture
def service(registry):
    context = NovelRoleContext(
        registry=registry,
        project_id="p1",
        chapter_index=1,
        artifacts={"write_packet": {"packet_id": "packet-1", "intent": "写第一章"}},
    )
    return NovelPiReadService(context)


def test_read_service_rejects_write_tools(service):
    with pytest.raises(ValueError, match="unsupported Pi role read tool"):
        service.execute("write_chapter", {"chapter_index": 1})


def test_read_service_cannot_select_another_project(service):
    with pytest.raises(ValueError, match="unexpected arguments"):
        service.execute("read_chapter", {"project_id": "p2", "chapter_index": 1})


def test_read_chapter_is_bound_to_context_project(service):
    result = service.execute("read_chapter", {"chapter_index": 1})

    payload = json.loads(result["content"])
    assert payload["chapter_index"] == 1
    assert payload["text"] == "只属于本项目的正文"
    assert "其他项目" not in result["content"]


def test_read_service_truncates_large_payload(registry):
    registry.novel_ledger_store.upsert(LedgerItem(
        item_id="large-ledger",
        project_id="p1",
        section="open_threads",
        entity="大条目",
        content="长" * (NovelPiReadService.MAX_CONTENT_CHARS + 500),
    ))
    service = NovelPiReadService(NovelRoleContext(
        registry=registry,
        project_id="p1",
        chapter_index=1,
    ))

    result = service.execute("read_ledger", {"limit": 200})

    assert len(result["content"]) <= NovelPiReadService.MAX_CONTENT_CHARS
    assert result["truncated"] is True


def test_read_write_packet_uses_active_context_artifact(service):
    result = service.execute("read_write_packet", {})

    assert json.loads(result["content"])["packet_id"] == "packet-1"

