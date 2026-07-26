from __future__ import annotations

import asyncio
import json

import pytest

from awp_rp_runtime_v3.contracts.novel_authoring import AuthorChapterPlan
from awp_rp_runtime_v3.contracts.novel_authoring import AuthorPlanStatus
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_authoring_service import NovelAuthoringService
from awp_rp_runtime_v3.runtime.novel_editor_session_manager import (
    EditorSessionManager,
)
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_trace import NovelPipelineCancelled
from awp_rp_runtime_v3.runtime.novel_pi_tool_service import NovelPiToolService
from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog


def _setup(tmp_path):
    project = tmp_path / "novels" / "book"
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps(
            {"project_id": "p1", "db_path": str(project / "novel.db")}
        ),
        encoding="utf-8",
    )
    catalog = NovelWorkspaceCatalog(tmp_path)
    registry = catalog.registry("p1")
    registry.novel_project_store.create(
        NovelProject(
            project_id="p1",
            title="测试小说",
            config={"novel_dir": str(project)},
        )
    )
    authoring = NovelAuthoringService(project, "p1")
    proposal_turn = authoring.next_turn()
    plan = authoring.save_plan(
        AuthorChapterPlan.model_validate(
            {
                "plan_id": "chapter-1",
                "project_id": "p1",
                "chapter_index": 1,
                "purpose": "让她选择留下",
                "confirmed_events": ["她回到礼堂"],
                "scenes": [
                    {
                        "scene_id": "s1",
                        "summary": "她回到礼堂",
                        "change": "她决定留下",
                    }
                ],
                "proposal_turn": proposal_turn,
                "status": "pending_confirmation",
            }
        )
    )
    return project, catalog, registry, authoring, plan


class _Socket:
    def __init__(self):
        self.frames = []
        self.received = asyncio.Event()

    async def send_json(self, frame):
        self.frames.append(frame)
        self.received.set()


@pytest.mark.asyncio
async def test_execute_streams_skips_writer_quality_and_saved_draft(
    tmp_path, monkeypatch
):
    _, catalog, _, _, plan = _setup(tmp_path)
    manager = EditorSessionManager(catalog)
    key = manager.key("p1", "chapter:1")
    socket = _Socket()
    subscription = await manager.subscribe(key, socket)
    await manager.handle_author_action(
        key, "approve_plan", plan.plan_id, plan.revision
    )

    def fake_write(self, **kwargs):
        self._safe_on_phase("skipped", "architect", {"author_led": True})
        self._safe_on_phase("skipped", "director", {"author_led": True})
        self._safe_on_phase(
            "skipped", "autonomous_npc_planning", {"author_led": True}
        )
        self._safe_on_phase("start", "writer", {})
        self._safe_on_chunk("她回到")
        self._safe_on_chunk("礼堂。")
        self._safe_on_phase(
            "end",
            "quality",
            {"verdict": "accept", "blocking_reasons": [], "warnings": []},
        )
        self._safe_on_draft_saved(
            {
                "draft_id": "draft-1",
                "revision": 1,
                "status": "accepted",
            }
        )
        return type(
            "Draft", (), {"char_count": 6, "status": "accepted"}
        )()

    monkeypatch.setattr(NovelEngine, "write_chapter_stream", fake_write)
    await manager.handle_author_action(
        key, "execute_plan", plan.plan_id, plan.revision
    )
    await asyncio.sleep(0)

    event_types = [frame["type"] for frame in socket.frames]
    assert event_types.count("writer_delta") == 2
    assert "draft_version_saved" in event_types
    skipped = {
        frame["payload"]["phase"]
        for frame in socket.frames
        if frame["type"] == "pipeline_phase"
        and frame["payload"]["event"] == "skipped"
    }
    assert skipped == {"architect", "director", "autonomous_npc_planning"}
    await subscription.close()
    await manager.close()


@pytest.mark.asyncio
async def test_cancelled_writer_keeps_approved_plan_and_commits_nothing(
    tmp_path, monkeypatch
):
    _, catalog, registry, authoring, plan = _setup(tmp_path)
    manager = EditorSessionManager(catalog)
    key = manager.key("p1", "chapter:1")
    socket = _Socket()
    subscription = await manager.subscribe(key, socket)
    await manager.handle_author_action(
        key, "approve_plan", plan.plan_id, plan.revision
    )

    original_execute = NovelPiToolService.execute

    def cancellable_execute(self, name, args):
        if name != "execute_author_plan":
            return original_execute(self, name, args)
        self._callbacks.on_chunk("未完成正文")
        while not self._callbacks.should_cancel():
            pass
        raise NovelPipelineCancelled("author cancelled")

    monkeypatch.setattr(NovelPiToolService, "execute", cancellable_execute)
    task = asyncio.create_task(
        manager.handle_author_action(
            key, "execute_plan", plan.plan_id, plan.revision
        )
    )
    for _ in range(50):
        await asyncio.sleep(0.01)
        if any(frame["type"] == "writer_delta" for frame in socket.frames):
            break
    await manager.cancel(key)
    await task
    await asyncio.sleep(0)

    assert authoring.get_plan(plan.plan_id).status is AuthorPlanStatus.APPROVED
    assert registry.novel_chapter_draft_store.load_latest(
        f"author-p1-ch1-v{plan.revision}"
    ) is None
    assert registry.novel_ledger_store.list_by_project("p1") == []
    assert any(frame["type"] == "turn_cancelled" for frame in socket.frames)
    await subscription.close()
    await manager.close()
