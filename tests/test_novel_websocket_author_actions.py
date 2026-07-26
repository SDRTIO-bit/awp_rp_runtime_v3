from __future__ import annotations

import asyncio
import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from awp_rp_runtime_v3.contracts.novel_authoring import AuthorChapterPlan
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_authoring_service import NovelAuthoringService
from awp_rp_runtime_v3.runtime.novel_editor_session_manager import (
    EditorSessionManager,
)
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog
from awp_rp_runtime_v3.scripts.awp_server import create_app


def _setup(tmp_path, *, unresolved: bool = False):
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
                "unresolved_questions": ["谁受伤？"] if unresolved else [],
                "proposal_turn": proposal_turn,
                "status": "pending_confirmation",
            }
        )
    )
    return project, catalog, registry, authoring, plan


async def _receive_type(ws, event_type: str):
    for _ in range(20):
        frame = await ws.receive_json(timeout=2)
        if frame["type"] == event_type:
            return frame
    raise AssertionError(f"event not received: {event_type}")


@pytest.mark.asyncio
async def test_approve_and_execute_are_distinct_durable_author_actions(
    tmp_path, monkeypatch
):
    project, catalog, registry, authoring, plan = _setup(tmp_path)
    manager = EditorSessionManager(catalog)
    monkeypatch.setattr(
        NovelEngine,
        "write_chapter_stream",
        lambda self, **kwargs: type(
            "Draft", (), {"char_count": 120, "status": "accepted"}
        )(),
    )
    app = create_app(
        workspace_catalog=catalog,
        editor_session_manager=manager,
    )

    async with TestClient(TestServer(app)) as client:
        ws = await client.ws_connect(
            "/awp/ws/v1/novels/p1/editor/chapter:1"
        )
        await ws.send_json(
            {
                "type": "approve_plan",
                "plan_id": plan.plan_id,
                "revision": plan.revision,
            }
        )
        approved = await _receive_type(ws, "author_plan_approved")
        assert approved["payload"]["revision"] == plan.revision
        assert authoring.get_plan(plan.plan_id).status.value == "approved"

        await ws.send_json(
            {
                "type": "execute_plan",
                "plan_id": plan.plan_id,
                "revision": plan.revision,
            }
        )
        started = await _receive_type(ws, "pipeline_phase")
        assert started["payload"]["phase"] == "author_plan_compile"
        executed = await _receive_type(ws, "author_plan_executed")
        assert executed["payload"]["revision"] == plan.revision
        await ws.close()

    journal = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            project / ".awp" / "authoring" / "journal"
        ).glob("*.jsonl")
    )
    assert '"source":"web_action"' in journal
    assert "我确认这个计划。" in journal
    assert "现在执行这个计划。" in journal


@pytest.mark.asyncio
@pytest.mark.parametrize("unresolved", [False, True])
async def test_rejected_actions_never_call_writer(
    tmp_path, monkeypatch, unresolved
):
    _, catalog, _, _, plan = _setup(tmp_path, unresolved=unresolved)
    writer_calls: list[int] = []
    monkeypatch.setattr(
        NovelEngine,
        "write_chapter_stream",
        lambda self, **kwargs: writer_calls.append(kwargs["chapter_index"]),
    )
    manager = EditorSessionManager(catalog)
    socket = type(
        "Socket",
        (),
        {
            "frames": [],
            "send_json": lambda self, frame: _append_frame(self, frame),
        },
    )()
    subscription = await manager.subscribe(
        manager.key("p1", "chapter:1"), socket
    )

    action = "approve_plan" if unresolved else "execute_plan"
    await manager.handle_author_action(
        manager.key("p1", "chapter:1"),
        action,
        plan.plan_id,
        plan.revision,
    )
    await asyncio.sleep(0)

    assert writer_calls == []
    assert any(frame["type"] == "action_rejected" for frame in socket.frames)
    await subscription.close()
    await manager.close()


async def _append_frame(socket, frame):
    socket.frames.append(frame)

