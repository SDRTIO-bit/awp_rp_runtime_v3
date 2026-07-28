from __future__ import annotations

import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_draft import ChapterDraft
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog
from awp_rp_runtime_v3.scripts.awp_server import create_app


def _catalog(tmp_path):
    project = tmp_path / "novels" / "book"
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps({"project_id": "p1", "db_path": str(project / "novel.db")}),
        encoding="utf-8",
    )
    catalog = NovelWorkspaceCatalog(tmp_path)
    registry = catalog.registry("p1")
    registry.novel_project_store.create(NovelProject(project_id="p1", title="测试"))
    registry.novel_chapter_plan_store.save(
        ChapterPlan(chapter_id="ch1", project_id="p1", chapter_index=1, title="第一章")
    )
    registry.novel_chapter_draft_store.save(
        ChapterDraft(
            draft_id="draft-ch1-r1", chapter_id="ch1", revision=1,
            text="第一段。\n\n第二段。", char_count=9, status="accepted",
        )
    )
    return catalog, project


@pytest.mark.asyncio
async def test_revision_read_and_export_return_accepted_chapter(tmp_path):
    catalog, project = _catalog(tmp_path)
    app = create_app(workspace_catalog=catalog)

    async with TestClient(TestServer(app)) as client:
        chapter = await client.get("/awp/api/v1/novels/p1/chapters/1/accepted")
        exported = await client.post("/awp/api/v1/novels/p1/exports/current")
        chapter_body = await chapter.json()
        export_body = await exported.json()

    assert chapter.status == 200
    assert chapter_body["data"]["accepted_revision"] == 1
    assert [p["paragraph_id"] for p in chapter_body["data"]["paragraphs"]] == [
        "r1:p1", "r1:p2"
    ]
    assert exported.status == 200
    assert export_body["data"]["chapters"][0]["revision"] == 1
    assert (project / "output" / "manifest.json").is_file()


@pytest.mark.asyncio
async def test_apply_stale_revision_plan_returns_current_revision(tmp_path):
    catalog, _project = _catalog(tmp_path)
    app = create_app(workspace_catalog=catalog)
    plan = {
        "plan_id": "revision-api-one",
        "project_id": "p1",
        "chapter_index": 1,
        "base_revision": 1,
        "status": "pending_confirmation",
        "proposal_turn": 1,
        "patches": [{
            "patch_id": "patch-api-one", "chapter_index": 1, "base_revision": 1,
            "paragraph_id": "r1:p1",
            "expected_paragraph_hash": "f0ca8e0960f34b0b3a5b15d1d62d5d5d863f9cc11f23c5ea1c8d21a0ca8f7e8c",
            "operation": "replace", "replacement_text": "新的第一段。", "reason": "修订",
        }],
    }
    # The intentionally incorrect hash is irrelevant: stale version is checked first.
    catalog.registry("p1").novel_chapter_draft_store.save(
        ChapterDraft(
            draft_id="draft-ch1-r2", chapter_id="ch1", revision=2,
            text="更新后的第一段。", char_count=9, status="accepted",
        )
    )

    async with TestClient(TestServer(app)) as client:
        saved = await client.post("/awp/api/v1/novels/p1/revision-plans", json=plan)
        approved = await client.post(
            "/awp/api/v1/novels/p1/revision-plans/revision-api-one/approve",
            json={"author_turn": 2},
        )
        applied = await client.post(
            "/awp/api/v1/novels/p1/revision-plans/revision-api-one/apply",
            json={"expected_revision": 1, "author_turn": 3},
        )
        body = await applied.json()

    assert saved.status == 200
    assert approved.status == 200
    assert applied.status == 409
    assert body["data"]["current_revision"] == 2


@pytest.mark.asyncio
async def test_author_skill_api_saves_then_explicitly_activates(tmp_path):
    catalog, project = _catalog(tmp_path)
    app = create_app(workspace_catalog=catalog)
    skill = {
        "skill_id": "voice-check", "version": 1,
        "content": "---\nname: voice-check\ndescription: 检查角色口吻\n---\n只报告证据。",
    }

    async with TestClient(TestServer(app)) as client:
        saved = await client.post("/awp/api/v1/novels/p1/skills", json=skill)
        before = await client.get("/awp/api/v1/novels/p1/skills")
        activated = await client.post(
            "/awp/api/v1/novels/p1/skills/voice-check/versions/1/activate"
        )
        after = await client.get("/awp/api/v1/novels/p1/skills")
        before_body = await before.json()
        after_body = await after.json()

    assert saved.status == 200
    assert before_body["data"]["enabled"] == []
    assert activated.status == 200
    assert after_body["data"]["enabled"][0]["skill_id"] == "voice-check"
    assert (project / ".awp" / "enabled-project-skills.json").is_file()
