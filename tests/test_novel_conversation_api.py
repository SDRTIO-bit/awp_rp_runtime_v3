"""Test conversation REST API endpoints (no pytest-aiohttp dependency)."""

from __future__ import annotations

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from awp_rp_runtime_v3.runtime.novel_conversation_store import (
    NovelConversationStore,
)


def _build_app(tmp_path, project_id="test-project"):
    from awp_rp_runtime_v3.runtime.novel_conversation_api import (
        register_conversation_routes,
    )

    class _FakeWorkspace:
        def __init__(self, root, pid):
            self.root = root
            self.project_id = pid

    class _FakeCatalog:
        def __init__(self, root, pid):
            self._ws = _FakeWorkspace(root, pid)

        def require(self, pid):
            return self._ws

        def list(self):
            return [self._ws]

        def registry(self, pid):
            raise RuntimeError("not needed")

    app = web.Application()
    register_conversation_routes(
        app, None, workspace_catalog=_FakeCatalog(tmp_path, project_id)
    )
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_branches(tmp_path):
    store = NovelConversationStore(tmp_path, "test-project")
    store.append("book", "author_message_saved", {"text": "hello"})

    async with TestClient(TestServer(_build_app(tmp_path))) as client:
        resp = await client.get(
            "/awp/api/v1/novels/test-project/editor-rooms/book/conversations"
        )
        assert resp.status == 200
        data = await resp.json()
        branches = data["data"]
        assert len(branches) == 1
        assert branches[0]["branch_id"] == "main"


@pytest.mark.asyncio
async def test_create_new_root_branch(tmp_path):
    async with TestClient(TestServer(_build_app(tmp_path))) as client:
        resp = await client.post(
            "/awp/api/v1/novels/test-project/editor-rooms/book/conversations",
            json={"title": "新对话"},
        )
        assert resp.status == 201
        data = await resp.json()
        assert data["data"]["title"] == "新对话"


@pytest.mark.asyncio
async def test_create_child_branch(tmp_path):
    store = NovelConversationStore(tmp_path, "test-project")
    event = store.append("book", "author_message_saved", {"text": "A"})

    async with TestClient(TestServer(_build_app(tmp_path))) as client:
        resp = await client.post(
            "/awp/api/v1/novels/test-project/editor-rooms/book/conversations",
            json={
                "parent_branch_id": "main",
                "fork_event_id": event.event_id,
                "title": "子分支",
            },
        )
        assert resp.status == 201
        data = await resp.json()
        assert data["data"]["parent_branch_id"] == "main"


@pytest.mark.asyncio
async def test_fork_after_effect_returns_409(tmp_path):
    store = NovelConversationStore(tmp_path, "test-project")
    store.append("book", "author_message_saved", {"text": "A"})
    store.append("book", "project_file_changed", {"path": "outline.md"})

    async with TestClient(TestServer(_build_app(tmp_path))) as client:
        resp = await client.post(
            "/awp/api/v1/novels/test-project/editor-rooms/book/conversations",
            json={
                "parent_branch_id": "main",
                "fork_event_id": 2,
                "title": "撤销改动",
            },
        )
        assert resp.status == 409
        data = await resp.json()
        assert data["code"] == "branch_has_effects"


@pytest.mark.asyncio
async def test_rename_branch(tmp_path):
    store = NovelConversationStore(tmp_path, "test-project")
    store.append("book", "author_message_saved", {"text": "A"})

    async with TestClient(TestServer(_build_app(tmp_path))) as client:
        resp = await client.patch(
            "/awp/api/v1/novels/test-project/editor-rooms/book/conversations/main",
            json={"title": "新标题"},
        )
        assert resp.status == 200

    branches = store.list_branches("book")
    assert branches[0].title == "新标题"


@pytest.mark.asyncio
async def test_reject_patch_with_unknown_fields(tmp_path):
    async with TestClient(TestServer(_build_app(tmp_path))) as client:
        resp = await client.patch(
            "/awp/api/v1/novels/test-project/editor-rooms/book/conversations/main",
            json={"status": "deleted"},
        )
        assert resp.status == 400


@pytest.mark.asyncio
async def test_search(tmp_path):
    store = NovelConversationStore(tmp_path, "test-project")
    store.append("book", "author_message_saved", {"text": "第三章冲突设置"})

    async with TestClient(TestServer(_build_app(tmp_path))) as client:
        resp = await client.get(
            "/awp/api/v1/novels/test-project/editor-rooms/book/conversation-search?q=冲突"
        )
        assert resp.status == 200
        data = await resp.json()
        hits = data["data"]
        assert len(hits) >= 1


@pytest.mark.asyncio
async def test_list_project_files(tmp_path):
    (tmp_path / "outline.md").write_text("x", encoding="utf-8")
    (tmp_path / "characters.md").write_text("x", encoding="utf-8")

    async with TestClient(TestServer(_build_app(tmp_path))) as client:
        resp = await client.get(
            "/awp/api/v1/novels/test-project/project-files"
        )
        assert resp.status == 200
        data = await resp.json()
        files = data["data"]
        assert "outline.md" in files
        for f in files:
            assert "\\" not in f
