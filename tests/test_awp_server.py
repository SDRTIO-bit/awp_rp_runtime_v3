from __future__ import annotations

import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog
from awp_rp_runtime_v3.scripts.awp_server import create_app


@pytest.mark.asyncio
async def test_health_reports_discovered_workspaces(tmp_path):
    project = tmp_path / "novels" / "book"
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps(
            {"project_id": "book-1", "db_path": str(project / "novel.db")}
        ),
        encoding="utf-8",
    )
    app = create_app(workspace_catalog=NovelWorkspaceCatalog(tmp_path))

    async with TestClient(TestServer(app)) as client:
        response = await client.get("/awp/api/v1/health")
        body = await response.json()

    assert response.status == 200
    assert body == {"data": {"status": "ok", "projects": 1}}
