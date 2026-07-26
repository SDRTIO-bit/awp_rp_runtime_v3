from __future__ import annotations

import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog
from awp_rp_runtime_v3.scripts.awp_server import create_app


@pytest.mark.asyncio
async def test_prompt_api_versions_diff_and_restore(tmp_path):
    project = tmp_path / "novels" / "book"
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps({"project_id": "p1", "db_path": str(project / "novel.db")}),
        encoding="utf-8",
    )
    catalog = NovelWorkspaceCatalog(tmp_path)
    app = create_app(workspace_catalog=catalog)

    async with TestClient(TestServer(app)) as client:
        current = await (await client.get(
            "/awp/api/v1/novels/p1/prompts/editor"
        )).json()
        saved_response = await client.put(
            "/awp/api/v1/novels/p1/prompts/editor",
            json={"content": "更严格的项目编辑", "expected_revision": 0},
        )
        diff = await (await client.get(
            "/awp/api/v1/novels/p1/prompts/editor/diff"
        )).json()
        restored_response = await client.post(
            "/awp/api/v1/novels/p1/prompts/editor/restore",
            json={"revision": 0, "expected_revision": 1},
        )
        saved = await saved_response.json()
        restored = await restored_response.json()

    assert current["data"]["source"] == "system"
    assert saved["data"]["revision"] == 1
    assert diff["data"]["diff"]
    assert restored["data"]["revision"] == 2
    assert restored["data"]["content"] == current["data"]["content"]
