from __future__ import annotations

import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog
from awp_rp_runtime_v3.scripts.awp_server import create_app


def _catalog(tmp_path):
    project = tmp_path / "novels" / "book"
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps(
            {"project_id": "p1", "db_path": str(project / "novel.db")}
        ),
        encoding="utf-8",
    )
    catalog = NovelWorkspaceCatalog(tmp_path)
    catalog.registry("p1").novel_project_store.create(
        NovelProject(project_id="p1", title="测试")
    )
    return catalog


@pytest.mark.asyncio
async def test_document_api_saves_lists_and_reads_exact_versions(tmp_path):
    catalog = _catalog(tmp_path)
    app = create_app(workspace_catalog=catalog)

    async with TestClient(TestServer(app)) as client:
        first = await client.put(
            "/awp/api/v1/novels/p1/documents/world",
            json={"content": "世界 v1", "expected_revision": 0},
        )
        second = await client.put(
            "/awp/api/v1/novels/p1/documents/world",
            json={"content": "世界 v2", "expected_revision": 1},
        )
        versions = await client.get(
            "/awp/api/v1/novels/p1/documents/world/versions"
        )
        exact = await client.get(
            "/awp/api/v1/novels/p1/documents/world/versions/1"
        )
        versions_body = await versions.json()
        exact_body = await exact.json()

    assert first.status == 200
    assert second.status == 200
    assert [item["revision"] for item in versions_body["data"]] == [
        2,
        1,
    ]
    assert exact_body["data"]["content"] == "世界 v1"


@pytest.mark.asyncio
async def test_document_api_returns_conflict_and_rejects_unknown_kind(tmp_path):
    catalog = _catalog(tmp_path)
    app = create_app(workspace_catalog=catalog)

    async with TestClient(TestServer(app)) as client:
        await client.put(
            "/awp/api/v1/novels/p1/documents/outline",
            json={"content": "v1", "expected_revision": 0},
        )
        conflict = await client.put(
            "/awp/api/v1/novels/p1/documents/outline",
            json={"content": "冲突", "expected_revision": 0},
        )
        unknown = await client.get(
            "/awp/api/v1/novels/p1/documents/not-a-kind"
        )
        conflict_body = await conflict.json()

    assert conflict.status == 409
    assert conflict_body["data"]["current_revision"] == 1
    assert unknown.status == 400
