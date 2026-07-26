from __future__ import annotations

import json

import pytest
from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from awp_rp_runtime_v3.runtime.novel_editor_session_manager import (
    EditorSessionManager,
)
from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog
from awp_rp_runtime_v3.scripts.awp_server import create_app


class _StreamingRuntime:
    def __init__(self, callbacks):
        self.callbacks = callbacks

    def handle_message(self, text: str) -> str:
        self.callbacks.on_chat("先确定事故")
        self.callbacks.on_chat("伤害了谁。")
        return "先确定事故伤害了谁。"

    def abort(self) -> None:
        return None

    def close(self) -> None:
        return None


def _catalog(tmp_path):
    project = tmp_path / "novels" / "book"
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps(
            {"project_id": "p1", "db_path": str(project / "novel.db")}
        ),
        encoding="utf-8",
    )
    return NovelWorkspaceCatalog(tmp_path)


@pytest.mark.asyncio
async def test_websocket_streams_real_editor_deltas_and_durable_completion(
    tmp_path,
):
    catalog = _catalog(tmp_path)
    manager = EditorSessionManager(
        catalog,
        runtime_factory=lambda registry, callbacks, *args, **kwargs: _StreamingRuntime(
            callbacks
        ),
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
                "type": "author_message",
                "client_message_id": "client-1",
                "text": "第一章从礼堂事故开始",
            }
        )
        frames = [await ws.receive_json(timeout=2) for _ in range(4)]
        await ws.close()

    assert frames[0]["type"] == "author_message_saved"
    assert "".join(
        frame["payload"]["text"]
        for frame in frames
        if frame["type"] == "editor_delta"
    ) == "先确定事故伤害了谁。"
    assert frames[-1]["type"] == "editor_message_completed"
    assert all(isinstance(frame["event_id"], int) for frame in frames)


@pytest.mark.asyncio
async def test_websocket_replays_after_event_id_and_rejects_invalid_frames(
    tmp_path,
):
    catalog = _catalog(tmp_path)
    manager = EditorSessionManager(
        catalog,
        runtime_factory=lambda registry, callbacks, *args, **kwargs: _StreamingRuntime(
            callbacks
        ),
    )
    key = manager.key("p1", "book")
    await manager.handle_author_message(key, "总纲", "client-book")
    app = create_app(
        workspace_catalog=catalog,
        editor_session_manager=manager,
    )

    async with TestClient(TestServer(app)) as client:
        ws = await client.ws_connect("/awp/ws/v1/novels/p1/editor/book")
        await ws.send_json({"type": "resume_from", "event_id": 3})
        replayed = await ws.receive_json(timeout=2)
        assert replayed["event_id"] == 4

        await ws.send_json({"type": "unknown"})
        error = await ws.receive_json(timeout=2)
        assert error["type"] == "protocol_error"

        await ws.send_json(
            {
                "type": "author_message",
                "client_message_id": "too-long",
                "text": "x" * 20001,
            }
        )
        error = await ws.receive_json(timeout=2)
        assert error["type"] == "protocol_error"
        await ws.close()


@pytest.mark.asyncio
async def test_websocket_returns_structured_error_for_unbound_project(tmp_path):
    catalog = _catalog(tmp_path)
    manager = EditorSessionManager(catalog)
    app = create_app(
        workspace_catalog=catalog,
        editor_session_manager=manager,
    )

    async with TestClient(TestServer(app)) as client:
        ws = await client.ws_connect(
            "/awp/ws/v1/novels/not-p1/editor/chapter:1"
        )
        frame = await ws.receive_json(timeout=2)
        closed = await ws.receive(timeout=2)

    assert frame["type"] == "protocol_error"
    assert closed.type in {WSMsgType.CLOSE, WSMsgType.CLOSED}

