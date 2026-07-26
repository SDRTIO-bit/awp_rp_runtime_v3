"""Standalone HTTP server for AWP Novel Runtime.

Usage:
    python scripts/awp_server.py
    python scripts/awp_server.py --port 8189 --db-path ./novels.db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT.parent))

from aiohttp import web

from awp_rp_runtime_v3.runtime.novel_api import register_novel_routes
from awp_rp_runtime_v3.runtime.runtime_store_factory import RuntimeStoreFactory
from awp_rp_runtime_v3.runtime.session_runtime_registry import (
    SessionRuntimeStoreRegistry,
)

_WEB_DIST = _PROJECT_ROOT / "frontend" / "dist"


def _default_registry_factory() -> SessionRuntimeStoreRegistry:
    return RuntimeStoreFactory.from_env().registry


def _safe_asset_path(tail: str) -> Path | None:
    if not tail:
        return None
    root = _WEB_DIST.resolve()
    candidate = (root / tail).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


async def _serve_spa(request: web.Request) -> web.Response:
    tail = request.match_info.get("tail", "")
    asset = _safe_asset_path(tail)
    if asset is not None and asset.is_file():
        return web.FileResponse(asset)

    index = _WEB_DIST / "index.html"
    if index.is_file():
        return web.FileResponse(index)
    return web.Response(
        text="Novel panel not built. Run: cd web && npm run build",
        content_type="text/plain",
        status=404,
    )


def create_app(
    registry_factory: Callable[[], SessionRuntimeStoreRegistry] | None = None,
) -> web.Application:
    """Create an aiohttp app with novel and SPA routes only."""

    app = web.Application()
    register_novel_routes(app, registry_factory or _default_registry_factory)
    app.router.add_get("/awp", _serve_spa)
    app.router.add_get("/awp/{tail:.*}", _serve_spa)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="AWP Novel Runtime server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8188)
    parser.add_argument("--db-path")
    args = parser.parse_args()
    if args.db_path:
        os.environ["AWP_DB_PATH"] = str(Path(args.db_path).resolve())
    web.run_app(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
