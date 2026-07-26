"""Boundary tests for the standalone novel HTTP application."""

from __future__ import annotations

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


def test_novel_app_does_not_import_comfyui_server():
    import sys

    create_app(registry_factory=lambda: object())

    assert "server" not in sys.modules
