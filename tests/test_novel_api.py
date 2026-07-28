"""Boundary and smoke tests for the novel HTTP application."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from awp_rp_runtime_v3.runtime.novel_api import NovelApiHandlers
from awp_rp_runtime_v3.runtime.novel_llm_factory import NovelLLMFactory
from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog
from awp_rp_runtime_v3.scripts.awp_server import create_app


def test_novel_app_registers_only_novel_and_static_routes():
    app = create_app(registry_factory=lambda: object())
    paths = {
        resource.canonical
        for resource in app.router.resources()
        if isinstance(resource.canonical, str)
    }

    assert "/awp/api/v1/novels" in paths
    assert "/awp" in paths
    assert not any("/sessions" in path or "/cards" in path for path in paths)


def test_llm_config_routes_registered():
    app = create_app(registry_factory=lambda: object())
    paths = {
        resource.canonical
        for resource in app.router.resources()
        if isinstance(resource.canonical, str)
    }
    assert "/awp/api/v1/novels/{project_id}/llm-config" in paths


def test_novel_app_does_not_import_comfyui_server():
    import sys

    create_app(registry_factory=lambda: object())

    assert "server" not in sys.modules


def test_health_endpoint_returns_ok():
    app = create_app(registry_factory=lambda: object())
    paths = {
        resource.canonical
        for resource in app.router.resources()
        if isinstance(resource.canonical, str)
    }
    assert "/awp/api/v1/health" in paths


def test_novel_routes_registered():
    app = create_app(registry_factory=lambda: object())
    paths = {
        resource.canonical
        for resource in app.router.resources()
        if isinstance(resource.canonical, str)
    }

    # Core novel resource paths
    assert "/awp/api/v1/novels" in paths
    assert "/awp/api/v1/novels/{project_id}/llm-config" in paths

    # List project route (no project_id in path)
    list_paths = [p for p in paths if p == "/awp/api/v1/novels"]
    assert len(list_paths) == 1


# ---------------------------------------------------------------------------
# LLM config endpoint — singleton isolation
# ---------------------------------------------------------------------------


class _FakeRequest:
    """Minimal stand-in for aiohttp web.Request used by handler tests."""

    def __init__(self, match_info: dict[str, str], body: dict):
        self.match_info = match_info
        self._body = body

    async def json(self) -> dict:
        return self._body


def _catalog_with_project(tmp_path: Path, project_id: str) -> NovelWorkspaceCatalog:
    project = tmp_path / "novels" / project_id
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps(
            {"project_id": project_id, "db_path": str(project / "novel.db")}
        ),
        encoding="utf-8",
    )
    catalog = NovelWorkspaceCatalog(tmp_path)
    from awp_rp_runtime_v3.contracts.novel_project import NovelProject as NP

    reg = catalog.registry(project_id)
    reg.novel_project_store.create(
        NP(
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


@pytest.mark.asyncio
async def test_update_llm_config_does_not_mutate_global_singleton(tmp_path):
    """PUT /llm-config must persist overrides to the project DB only and
    must NOT call NovelLLMFactory.set_project_overrides."""
    catalog = _catalog_with_project(tmp_path, "proj-x")
    handlers = NovelApiHandlers(
        registry_factory=lambda: catalog.registry("proj-x"),
        workspace_catalog=catalog,
    )

    factory = NovelLLMFactory.get_instance()
    factory.reset()
    # Seed the singleton with a sentinel so we can detect mutation
    factory.set_project_overrides({"writer": {"model": "sentinel-before"}})

    request = _FakeRequest(
        {"project_id": "proj-x"},
        {"overrides": {"writer": {"model": "updated-via-api", "max_tokens": 4242}}},
    )
    response = await handlers.update_llm_config(request)

    assert response.status == 200
    # Singleton must still hold the sentinel, not the API payload
    singleton_overrides = factory.get_project_overrides()
    assert singleton_overrides.get("writer", {}).get("model") == "sentinel-before"

    # The project DB must have the new overrides persisted
    project = catalog.registry("proj-x").novel_project_store.load("proj-x")
    assert project is not None
    persisted = getattr(project, "config", {}).get("llm_overrides", {})
    assert persisted.get("writer", {}).get("model") == "updated-via-api"
    assert persisted.get("writer", {}).get("max_tokens") == 4242

    factory.reset()
    catalog.close()


@pytest.mark.asyncio
async def test_update_llm_config_accepts_custom_provider_fields(tmp_path):
    catalog = _catalog_with_project(tmp_path, "proj-custom")
    handlers = NovelApiHandlers(
        registry_factory=lambda: catalog.registry("proj-custom"),
        workspace_catalog=catalog,
    )

    response = await handlers.update_llm_config(
        _FakeRequest(
            {"project_id": "proj-custom"},
            {"overrides": {"writer": {
                "provider": "openai-compatible",
                "model": "vendor-model",
                "api_base": "https://vendor.example/v1",
                "api_key_env": "VENDOR_API_KEY",
            }}},
        )
    )

    assert response.status == 200
    catalog.close()


@pytest.mark.asyncio
async def test_update_llm_config_rejects_incomplete_custom_provider(tmp_path):
    catalog = _catalog_with_project(tmp_path, "proj-invalid")
    handlers = NovelApiHandlers(
        registry_factory=lambda: catalog.registry("proj-invalid"),
        workspace_catalog=catalog,
    )

    response = await handlers.update_llm_config(
        _FakeRequest(
            {"project_id": "proj-invalid"},
            {"overrides": {"writer": {"provider": "openai-compatible", "model": "vendor-model"}}},
        )
    )

    assert response.status == 400
    catalog.close()


@pytest.mark.asyncio
async def test_get_llm_config_reports_the_project_editor_provider(tmp_path):
    catalog = _catalog_with_project(tmp_path, "proj-editor")
    project = catalog.registry("proj-editor").novel_project_store.load("proj-editor")
    assert project is not None
    catalog.registry("proj-editor").novel_project_store.update(
        project.__class__(
            **{
                **project.__dict__,
                "config": {"llm_overrides": {"brain": {"provider": "opencode", "model": "editor-model"}}},
            }
        )
    )
    handlers = NovelApiHandlers(
        registry_factory=lambda: catalog.registry("proj-editor"),
        workspace_catalog=catalog,
    )

    response = await handlers.get_llm_config(_FakeRequest({"project_id": "proj-editor"}, {}))
    body = json.loads(response.text)

    assert response.status == 200
    assert body["data"]["defaults"]["brain"]["provider"] == "opencode"
    assert body["data"]["defaults"]["brain"]["model"] == "editor-model"
    catalog.close()


@pytest.mark.asyncio
async def test_llm_connection_test_uses_role_connection_and_never_returns_key(tmp_path, monkeypatch):
    catalog = _catalog_with_project(tmp_path, "proj-connection")
    handlers = NovelApiHandlers(
        registry_factory=lambda: catalog.registry("proj-connection"),
        workspace_catalog=catalog,
    )
    monkeypatch.setenv("VENDOR_API_KEY", "secret-value")

    class _Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return b'{"data":[{"id":"vendor-model"}]}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: _Response())
    response = await handlers.test_llm_connection(
        _FakeRequest(
            {"project_id": "proj-connection"},
            {"role": "brain", "config": {
                "provider": "openai-compatible", "model": "vendor-model",
                "api_base": "https://vendor.example/v1", "api_key_env": "VENDOR_API_KEY",
            }},
        )
    )
    body = json.loads(response.text)

    assert response.status == 200
    assert body["data"] == {"ok": True, "model_count": 1}
    assert "secret-value" not in response.text
    catalog.close()


@pytest.mark.asyncio
async def test_llm_models_returns_sorted_provider_models(tmp_path, monkeypatch):
    catalog = _catalog_with_project(tmp_path, "proj-models")
    handlers = NovelApiHandlers(
        registry_factory=lambda: catalog.registry("proj-models"),
        workspace_catalog=catalog,
    )
    monkeypatch.setenv("VENDOR_API_KEY", "secret-value")

    class _Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return b'{"data":[{"id":"z-model"},{"id":"a-model"},{"id":"a-model"}]}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: _Response())
    response = await handlers.list_llm_models(
        _FakeRequest(
            {"project_id": "proj-models"},
            {"role": "brain", "config": {
                "provider": "openai-compatible", "model": "placeholder",
                "api_base": "https://vendor.example/v1", "api_key_env": "VENDOR_API_KEY",
            }},
        )
    )
    body = json.loads(response.text)

    assert response.status == 200
    assert body["data"] == {"models": ["a-model", "z-model"]}
    assert "secret-value" not in response.text
    catalog.close()


@pytest.mark.asyncio
async def test_update_llm_config_persists_direct_key_when_no_matching_environment_variable(tmp_path):
    catalog = _catalog_with_project(tmp_path, "proj-direct-key")
    handlers = NovelApiHandlers(
        registry_factory=lambda: catalog.registry("proj-direct-key"),
        workspace_catalog=catalog,
    )

    response = await handlers.update_llm_config(
        _FakeRequest(
            {"project_id": "proj-direct-key"},
            {"overrides": {"brain": {
                "provider": "openai-compatible", "model": "vendor-model",
                "api_base": "https://vendor.example/v1", "api_key": "direct-test-key",
            }}},
        )
    )
    project = catalog.registry("proj-direct-key").novel_project_store.load("proj-direct-key")

    assert response.status == 200
    assert project is not None
    saved = project.config["llm_overrides"]["brain"]
    assert saved["api_key"] == "direct-test-key"
    assert "api_key_env" not in saved
    catalog.close()


@pytest.mark.asyncio
async def test_update_llm_config_prefers_a_matching_environment_variable_name(tmp_path, monkeypatch):
    catalog = _catalog_with_project(tmp_path, "proj-env-key")
    handlers = NovelApiHandlers(
        registry_factory=lambda: catalog.registry("proj-env-key"),
        workspace_catalog=catalog,
    )
    monkeypatch.setenv("VENDOR_API_KEY", "environment-secret")

    response = await handlers.update_llm_config(
        _FakeRequest(
            {"project_id": "proj-env-key"},
            {"overrides": {"brain": {
                "provider": "openai-compatible", "model": "vendor-model",
                "api_base": "https://vendor.example/v1", "api_key": "VENDOR_API_KEY",
            }}},
        )
    )
    project = catalog.registry("proj-env-key").novel_project_store.load("proj-env-key")

    assert response.status == 200
    assert project is not None
    saved = project.config["llm_overrides"]["brain"]
    assert saved["api_key_env"] == "VENDOR_API_KEY"
    assert "api_key" not in saved
    catalog.close()
