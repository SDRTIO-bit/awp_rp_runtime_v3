from __future__ import annotations

import pytest

from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_draft import ChapterDraft
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.contracts.novel_revision import (
    ChapterRevisionPlan,
    RevisionBatchStatus,
    RevisionPatch,
)
from awp_rp_runtime_v3.runtime.novel_chapter_revision_service import (
    NovelChapterRevisionService,
)


@pytest.fixture
def reg(tmp_path):
    from awp_rp_runtime_v3.runtime.session_runtime_registry import (
        SessionRuntimeStoreRegistry,
    )
    from awp_rp_runtime_v3.storage.sqlite.database import Database

    db = Database(str(tmp_path / "test.db"))
    db.initialize()
    return SessionRuntimeStoreRegistry(db)


def test_read_chapter_returns_all_paragraphs_and_accepted_revision(reg):
    reg.novel_project_store.create(NovelProject(project_id="p1"))
    reg.novel_chapter_plan_store.save(ChapterPlan(
        chapter_id="ch1", project_id="p1", chapter_index=1, title="第一章"
    ))
    reg.novel_chapter_draft_store.save(ChapterDraft(
        draft_id="draft-ch1-r1",
        chapter_id="ch1",
        revision=1,
        status="accepted",
        text="第一段。\n\n第二段。",
        char_count=9,
    ))
    reg.novel_chapter_draft_store.save(ChapterDraft(
        draft_id="draft-ch1-r2",
        chapter_id="ch1",
        revision=2,
        status="rejected",
        text="不应读取。",
        char_count=5,
    ))

    chapter = NovelChapterRevisionService(reg, project_id="p1").read_chapter(1)

    assert chapter.accepted_revision == 1
    assert chapter.title == "第一章"
    assert [item.paragraph_id for item in chapter.paragraphs] == ["r1:p1", "r1:p2"]
    assert [item.text for item in chapter.paragraphs] == ["第一段。", "第二段。"]


def test_apply_approved_patch_creates_new_accepted_revision(reg):
    reg.novel_project_store.create(NovelProject(project_id="p1"))
    reg.novel_chapter_plan_store.save(ChapterPlan(
        chapter_id="ch1", project_id="p1", chapter_index=1, title="第一章"
    ))
    reg.novel_chapter_draft_store.save(ChapterDraft(
        draft_id="draft-ch1-r1", chapter_id="ch1", revision=1,
        status="accepted", text="旧第一段。\n\n第二段。", char_count=11,
    ))
    service = NovelChapterRevisionService(reg, project_id="p1")
    chapter = service.read_chapter(1)
    plan = ChapterRevisionPlan(
        plan_id="revision-one",
        project_id="p1",
        chapter_index=1,
        base_revision=1,
        status=RevisionBatchStatus.APPROVED,
        patches=(RevisionPatch(
            patch_id="patch-one", chapter_index=1, base_revision=1,
            paragraph_id="r1:p1",
            expected_paragraph_hash=chapter.paragraphs[0].sha256,
            operation="replace", replacement_text="新第一段。",
            reason="删去解释，保留回避。",
        ),),
    )

    service.save_plan(plan)
    applied = service.apply_plan("revision-one", expected_revision=1)

    assert applied.revision == 2
    assert applied.status == "accepted"
    assert applied.source == "editor_patch"
    assert applied.text == "新第一段。\n\n第二段。"
    assert reg.novel_chapter_draft_store.load("draft-ch1-r1").text == "旧第一段。\n\n第二段。"


def test_revision_plan_requires_later_turn_to_approve(reg):
    reg.novel_project_store.create(NovelProject(project_id="p1"))
    reg.novel_chapter_plan_store.save(ChapterPlan(
        chapter_id="ch1", project_id="p1", chapter_index=1, title="第一章"
    ))
    service = NovelChapterRevisionService(reg, project_id="p1")
    plan = ChapterRevisionPlan(
        plan_id="revision-turns",
        project_id="p1",
        chapter_index=1,
        base_revision=1,
        status=RevisionBatchStatus.PENDING_CONFIRMATION,
        patches=(RevisionPatch(
            patch_id="patch-turns", chapter_index=1, base_revision=1,
            paragraph_id="r1:p1", expected_paragraph_hash="a" * 64,
            operation="replace", replacement_text="新文本", reason="修改原因",
        ),),
        proposal_turn=2,
    )
    service.save_plan(plan)

    with pytest.raises(ValueError, match="later author turn"):
        service.approve_plan("revision-turns", turn=2)

    approved = service.approve_plan("revision-turns", turn=3)

    assert approved.status == RevisionBatchStatus.APPROVED


def test_export_current_writes_only_accepted_drafts_and_manifest(reg, tmp_path):
    reg.novel_project_store.create(NovelProject(project_id="p1"))
    reg.novel_chapter_plan_store.save(ChapterPlan(
        chapter_id="ch1", project_id="p1", chapter_index=1, title="第一章"
    ))
    reg.novel_chapter_draft_store.save(ChapterDraft(
        draft_id="draft-ch1-r1", chapter_id="ch1", revision=1,
        status="accepted", text="接受正文。", char_count=5,
    ))
    reg.novel_chapter_draft_store.save(ChapterDraft(
        draft_id="draft-ch1-r2", chapter_id="ch1", revision=2,
        status="rejected", text="拒稿正文。", char_count=5,
    ))

    manifest = NovelChapterRevisionService(reg, project_id="p1").export_current(tmp_path)

    assert (tmp_path / "output" / "chapter_01.md").read_text(encoding="utf-8") == "接受正文。"
    assert manifest["chapters"][0]["revision"] == 1
