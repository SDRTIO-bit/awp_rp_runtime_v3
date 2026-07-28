"""Request-level aiohttp smoke coverage for the novel HTTP API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_llm_factory import (
    ROLE_NAMES,
    NovelLLMFactory,
)
from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog
from awp_rp_runtime_v3.scripts.awp_server import create_app


def _catalog_with_projects(
    tmp_path: Path, project_ids: tuple[str, ...]
) -> NovelWorkspaceCatalog:
    for project_id in project_ids:
        project_dir = tmp_path / "novels" / project_id
        project_dir.mkdir(parents=True)
        (project_dir / ".novel_cli.json").write_text(
            json.dumps(
                {"project_id": project_id, "db_path": str(project_dir / "novel.db")}
            ),
            encoding="utf-8",
        )

    catalog = NovelWorkspaceCatalog(tmp_path)
    for project_id in project_ids:
        catalog.registry(project_id).novel_project_store.create(
            NovelProject(
                project_id=project_id,
                title=project_id,
                genre="",
                target_platform="",
                target_reader="",
                core_emotion="",
                one_sentence_pitch="",
                status="draft",
                config={"llm_overrides": {}},
            )
        )
    return catalog


@pytest.fixture
def api_app(tmp_path):
    catalog = _catalog_with_projects(tmp_path, ("project-a", "project-b"))
    factory = NovelLLMFactory.get_instance()
    factory.reset()
    app = create_app(
        registry_factory=lambda: catalog.registry("project-a"),
        workspace_catalog=catalog,
    )
    yield app, factory
    factory.reset()


@pytest.mark.asyncio
async def test_health_request_reports_workspace_count(api_app):
    app, _ = api_app

    async with TestClient(TestServer(app)) as client:
        response = await client.get("/awp/api/v1/health")
        body = await response.json()

    assert response.status == 200
    assert body == {"data": {"status": "ok", "projects": 2}}


@pytest.mark.asyncio
async def test_projects_and_prompts_requests_return_project_data(api_app):
    app, _ = api_app

    async with TestClient(TestServer(app)) as client:
        projects_response = await client.get("/awp/api/v1/novels")
        prompts_response = await client.get(
            "/awp/api/v1/novels/project-a/prompts"
        )
        projects_body = await projects_response.json()
        prompts_body = await prompts_response.json()

    assert projects_response.status == 200
    assert {project["project_id"] for project in projects_body["data"]} == {
        "project-a",
        "project-b",
    }
    assert prompts_response.status == 200
    assert prompts_body["data"]


@pytest.mark.asyncio
async def test_llm_config_get_returns_defaults_without_secrets(api_app):
    app, _ = api_app

    async with TestClient(TestServer(app)) as client:
        response = await client.get(
            "/awp/api/v1/novels/project-a/llm-config"
        )
        body = await response.json()

    assert response.status == 200
    data = body["data"]
    assert data["overrides"] == {}
    assert set(data["defaults"]) == set(ROLE_NAMES)
    assert all(
        set(config) == {"model", "max_tokens", "thinking_level", "provider"}
        for config in data["defaults"].values()
    )


@pytest.mark.asyncio
async def test_llm_config_put_persists_without_mutating_global_singleton(api_app):
    app, factory = api_app
    factory.set_project_overrides({"writer": {"model": "singleton-sentinel"}})
    overrides = {
        "writer": {
            "model": "project-a-model",
            "max_tokens": 4242,
            "thinking_level": "off",
        }
    }

    async with TestClient(TestServer(app)) as client:
        put_response = await client.put(
            "/awp/api/v1/novels/project-a/llm-config",
            json={"overrides": overrides},
        )
        get_response = await client.get(
            "/awp/api/v1/novels/project-a/llm-config"
        )
        put_body = await put_response.json()
        get_body = await get_response.json()

    assert put_response.status == 200
    assert put_body["data"] == {"ok": True, "overrides": overrides}
    assert get_response.status == 200
    assert get_body["data"]["overrides"] == overrides
    assert factory.get_project_overrides() == {
        "writer": {"model": "singleton-sentinel"}
    }


@pytest.mark.asyncio
async def test_llm_config_projects_do_not_cross_contaminate(api_app):
    app, _ = api_app
    project_a = {"writer": {"model": "model-a"}}
    project_b = {"writer": {"model": "model-b"}}

    async with TestClient(TestServer(app)) as client:
        response_a = await client.put(
            "/awp/api/v1/novels/project-a/llm-config",
            json={"overrides": project_a},
        )
        response_b = await client.put(
            "/awp/api/v1/novels/project-b/llm-config",
            json={"overrides": project_b},
        )
        get_a = await client.get("/awp/api/v1/novels/project-a/llm-config")
        get_b = await client.get("/awp/api/v1/novels/project-b/llm-config")
        body_a = await get_a.json()
        body_b = await get_b.json()

    assert response_a.status == 200
    assert response_b.status == 200
    assert body_a["data"]["overrides"] == project_a
    assert body_b["data"]["overrides"] == project_b


@pytest.mark.asyncio
async def test_custom_llm_config_persists_per_project_without_secrets(api_app):
    app, _ = api_app
    custom_a = {"writer": {
        "provider": "openai-compatible",
        "model": "vendor-a",
        "api_base": "https://a.example/v1",
        "api_key_env": "VENDOR_A_KEY",
    }}
    custom_b = {"writer": {
        "provider": "openai-compatible",
        "model": "vendor-b",
        "api_base": "https://b.example/v1",
        "api_key_env": "VENDOR_B_KEY",
    }}

    async with TestClient(TestServer(app)) as client:
        await client.put("/awp/api/v1/novels/project-a/llm-config", json={"overrides": custom_a})
        await client.put("/awp/api/v1/novels/project-b/llm-config", json={"overrides": custom_b})
        body_a = await (await client.get("/awp/api/v1/novels/project-a/llm-config")).json()
        body_b = await (await client.get("/awp/api/v1/novels/project-b/llm-config")).json()

    assert body_a["data"]["overrides"] == custom_a
    assert body_b["data"]["overrides"] == custom_b
    assert "VENDOR_A_KEY" in json.dumps(body_a)
    assert "VENDOR_B_KEY" in json.dumps(body_b)
    assert "vendor-a-secret" not in json.dumps(body_a)


@pytest.mark.asyncio
async def test_llm_config_put_rejects_unknown_role(api_app):
    app, _ = api_app

    async with TestClient(TestServer(app)) as client:
        response = await client.put(
            "/awp/api/v1/novels/project-a/llm-config",
            json={"overrides": {"unknown-role": {"model": "x"}}},
        )
        body = await response.json()

    assert response.status == 400
    assert body["data"]["error"] == "unknown role: unknown-role"


class _StubDraft:
    """Minimal stand-in for ChapterDraft.to_dict()."""

    def __init__(self, **payload):
        self._payload = payload

    def to_dict(self) -> dict:
        return self._payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("route", "engine_method", "payload"),
    [
        ("chapters/2/write", "write_chapter", None),
        ("chapters/2/revise", "revise_chapter", {"feedback": "节奏太慢"}),
    ],
)
async def test_chapter_routes_pass_project_id_to_engine(
    api_app, monkeypatch, route, engine_method, payload
):
    """The chapter handlers must reach the engine with the routed project id.

    Regression: ``write_chapter``/``revise_chapter``/``batch_write`` referenced
    an undefined local ``project_id`` when building the registry, so every
    request raised ``NameError`` and the bare ``except Exception`` reported it
    as an opaque HTTP 500.
    """
    app, _ = api_app
    seen: dict[str, object] = {}

    def fake(self, **kwargs):
        seen.update(kwargs)
        return _StubDraft(chapter_index=kwargs["chapter_index"], text="ok")

    monkeypatch.setattr(
        f"awp_rp_runtime_v3.runtime.novel_api.NovelEngine.{engine_method}",
        fake,
        raising=True,
    )

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            f"/awp/api/v1/novels/project-a/{route}",
            json=payload if payload is not None else {},
        )
        body = await response.json()

    assert response.status == 200, body
    assert seen["project_id"] == "project-a"
    assert seen["chapter_index"] == 2
    assert body["data"]["chapter_index"] == 2


@pytest.mark.asyncio
async def test_batch_write_route_passes_project_id_to_engine(api_app, monkeypatch):
    """``batch_write`` had the same undefined ``project_id`` defect."""
    app, _ = api_app
    seen: dict[str, object] = {}

    def fake_batch(self, **kwargs):
        seen.update(kwargs)
        return [_StubDraft(chapter_index=index) for index in (1, 2)]

    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_api.NovelEngine.batch_write",
        fake_batch,
        raising=True,
    )

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/awp/api/v1/novels/project-a/batch-write",
            json={"chapter_start": 1, "chapter_end": 2},
        )
        body = await response.json()

    assert response.status == 200, body
    assert seen["project_id"] == "project-a"
    assert body["data"]["count"] == 2
