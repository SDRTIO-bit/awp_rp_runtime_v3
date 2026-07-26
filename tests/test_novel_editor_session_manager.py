from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from awp_rp_runtime_v3.runtime.novel_editor_session_manager import (
    EditorRoomKey,
    EditorSessionManager,
)
from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog


class _Socket:
    def __init__(self):
        self.frames: list[dict] = []

    async def send_json(self, frame: dict) -> None:
        self.frames.append(frame)


class _Runtime:
    def __init__(self, callbacks, answer: str = "先确定事故伤害了谁。"):
        self.callbacks = callbacks
        self.answer = answer
        self.aborted = False
        self.closed = False

    def handle_message(self, text: str) -> str:
        self.callbacks.on_chat("先确定事故")
        self.callbacks.on_chat("伤害了谁。")
        return self.answer

    def abort(self) -> None:
        self.aborted = True

    def close(self) -> None:
        self.closed = True


def _catalog(tmp_path: Path) -> NovelWorkspaceCatalog:
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
async def test_manager_persists_before_pi_and_streams_real_deltas(tmp_path):
    observed_persisted: list[bool] = []

    def runtime_factory(registry, callbacks, project_dir, project_id, **kwargs):
        runtime = _Runtime(callbacks)
        original = runtime.handle_message

        def checked(text: str) -> str:
            conversation = (
                project_dir
                / ".awp"
                / "authoring"
                / "conversations"
                / "chapter-000001.jsonl"
            )
            observed_persisted.append(
                conversation.is_file()
                and "client-1" in conversation.read_text(encoding="utf-8")
            )
            return original(text)

        runtime.handle_message = checked
        return runtime

    manager = EditorSessionManager(_catalog(tmp_path), runtime_factory=runtime_factory)
    socket = _Socket()
    subscription = await manager.subscribe(
        EditorRoomKey.parse("p1", "chapter:1"), socket
    )

    await manager.handle_author_message(
        EditorRoomKey.parse("p1", "chapter:1"),
        "第一章从礼堂事故开始",
        "client-1",
    )
    await asyncio.sleep(0)

    assert observed_persisted == [True]
    assert [frame["type"] for frame in socket.frames] == [
        "author_message_saved",
        "editor_delta",
        "editor_delta",
        "editor_message_completed",
    ]
    assert "".join(
        frame["payload"]["text"]
        for frame in socket.frames
        if frame["type"] == "editor_delta"
    ) == "先确定事故伤害了谁。"
    await subscription.close()
    await manager.close()


@pytest.mark.asyncio
async def test_rooms_have_separate_runtime_sessions_and_replay(tmp_path):
    runtimes: list[_Runtime] = []

    def runtime_factory(registry, callbacks, project_dir, project_id, **kwargs):
        runtime = _Runtime(callbacks)
        runtimes.append(runtime)
        return runtime

    manager = EditorSessionManager(_catalog(tmp_path), runtime_factory=runtime_factory)
    chapter_one = EditorRoomKey.parse("p1", "chapter:1")
    chapter_two = EditorRoomKey.parse("p1", "chapter:2")
    await manager.handle_author_message(chapter_one, "第一章", "c1")
    await manager.handle_author_message(chapter_two, "第二章", "c2")

    socket = _Socket()
    subscription = await manager.subscribe(chapter_one, socket, after_event_id=0)
    await asyncio.sleep(0)

    assert len(runtimes) == 2
    assert {
        frame["payload"].get("client_message_id")
        for frame in socket.frames
        if frame["type"] == "author_message_saved"
    } == {"c1"}
    await subscription.close()
    await manager.close()
    assert all(runtime.closed for runtime in runtimes)


@pytest.mark.asyncio
async def test_cancel_targets_only_the_selected_room(tmp_path):
    runtimes: dict[str, _Runtime] = {}

    def runtime_factory(
        registry, callbacks, project_dir, project_id, *, session_id, **kwargs
    ):
        runtime = _Runtime(callbacks)
        runtimes[session_id] = runtime
        return runtime

    manager = EditorSessionManager(_catalog(tmp_path), runtime_factory=runtime_factory)
    first = EditorRoomKey.parse("p1", "chapter:1")
    second = EditorRoomKey.parse("p1", "chapter:2")
    await manager.ensure_runtime(first)
    await manager.ensure_runtime(second)

    await manager.cancel(first)

    assert sum(runtime.aborted for runtime in runtimes.values()) == 1
    await manager.close()

