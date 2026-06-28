"""Management API — REST endpoints for the AWP RP management panel.

Provides session listing, turn history, card browsing, and session
continuation via HTTP. Designed for the React SPA frontend.

All routes are prefixed with /awp/api/v1/.
The SPA static files are served at /awp/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..runtime.runtime_store_factory import RuntimeStoreFactory

# ── Helpers ──────────────────────────────────────────────────────────────────

_MANAGEMENT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _mime_type(suffix: str) -> str:
    return {
        ".html": "text/html",
        ".js": "application/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }.get(suffix, "application/octet-stream")


# ── API Routes (only register inside ComfyUI) ────────────────────────────────

try:
    import server
    from aiohttp import web

    def _json(data: Any, status: int = 200) -> web.Response:
        return web.json_response(
            {"data": data}, status=status,
            dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str),
        )

    def _factory() -> RuntimeStoreFactory:
        return RuntimeStoreFactory.from_env()

    @server.PromptServer.instance.routes.get("/awp/api/v1/sessions")
    async def list_sessions(request):
        """List all sessions with card name, turn count, last activity."""
        factory = _factory()
        registry = factory.registry
        bindings = registry.card_session_binding_store.list_all()

        result = []
        for b in bindings:
            turns = registry.turn_record_store.list_by_session(b.session_id)
            turn_count = len(turns)
            last_turn = turns[-1] if turns else None

            card_name = b.logical_card_id
            try:
                card = registry.card_definition_store.get_latest(b.logical_card_id)
                if card:
                    card_name = card.display_name or card.name or b.logical_card_id
            except Exception:
                pass

            result.append({
                "session_id": b.session_id,
                "card_id": b.logical_card_id,
                "card_name": card_name,
                "greeting_id": b.selected_greeting_id,
                "turn_count": turn_count,
                "last_turn_time": last_turn.accepted_at if last_turn else b.created_at,
                "created_at": b.created_at,
                "status": b.status,
            })

        return _json(result)

    @server.PromptServer.instance.routes.get("/awp/api/v1/sessions/{session_id}")
    async def get_session(request):
        """Get a single session's details."""
        session_id = request.match_info["session_id"]
        factory = _factory()
        registry = factory.registry

        binding = registry.card_session_binding_store.load(session_id)
        if not binding:
            return _json({"error": "Session not found"}, 404)

        turns = registry.turn_record_store.list_by_session(session_id)
        opening = None
        try:
            opening = registry.opening_record_store.get_by_session(session_id)
        except Exception:
            pass

        card_name = binding.logical_card_id
        try:
            card = registry.card_definition_store.get_latest(binding.logical_card_id)
            if card:
                card_name = card.display_name or card.name or binding.logical_card_id
        except Exception:
            pass

        return _json({
            "session_id": binding.session_id,
            "card_id": binding.logical_card_id,
            "card_name": card_name,
            "greeting_id": binding.selected_greeting_id,
            "status": binding.status,
            "created_at": binding.created_at,
            "turn_count": len(turns),
            "opening_content": opening.safe_display_content if opening else "",
        })

    @server.PromptServer.instance.routes.get("/awp/api/v1/sessions/{session_id}/turns")
    async def list_turns(request):
        """List all turns for a session."""
        session_id = request.match_info["session_id"]
        factory = _factory()
        registry = factory.registry

        binding = registry.card_session_binding_store.load(session_id)
        if not binding:
            return _json({"error": "Session not found"}, 404)

        turns = registry.turn_record_store.list_by_session(session_id)

        result = []
        for t in turns:
            result.append({
                "turn_id": t.turn_id,
                "turn_index": t.turn_index,
                "mode": t.mode.value,
                "player_input": t.player_input,
                "writer_output": t.writer_output,
                "base_card_state_revision": t.base_card_state_revision,
                "result_card_state_revision": t.result_card_state_revision,
                "accepted_at": t.accepted_at,
                "created_at": t.created_at,
                "trace_id": t.trace_id,
            })

        return _json(result)

    @server.PromptServer.instance.routes.get("/awp/api/v1/sessions/{session_id}/opening")
    async def get_opening(request):
        """Get the opening/greeting content for a session."""
        session_id = request.match_info["session_id"]
        factory = _factory()
        registry = factory.registry

        try:
            opening = registry.opening_record_store.get_by_session(session_id)
        except Exception:
            return _json({"error": "Opening not found"}, 404)

        if not opening:
            return _json({"error": "Opening not found"}, 404)

        return _json({
            "opening_record_id": opening.opening_record_id,
            "greeting_id": opening.greeting_id,
            "content": opening.safe_display_content,
            "created_at": opening.created_at,
        })

    @server.PromptServer.instance.routes.get("/awp/api/v1/cards")
    async def list_cards(request):
        """List all imported cards with stats."""
        factory = _factory()
        registry = factory.registry

        try:
            cards = registry.card_definition_store.list_all()
        except Exception:
            cards = []

        result = []
        seen = set()
        for c in cards:
            if c.logical_card_id in seen:
                continue
            seen.add(c.logical_card_id)
            result.append({
                "card_id": c.logical_card_id,
                "version": c.card_version,
                "name": c.display_name or c.name or c.logical_card_id,
                "status": c.status,
                "greeting_count": len(c.greetings) if c.greetings else 0,
                "worldbook_count": len(c.worldbook_catalog) if c.worldbook_catalog else 0,
                "created_at": c.created_at,
            })

        return _json(result)

    @server.PromptServer.instance.routes.post("/awp/api/v1/sessions/{session_id}/continue")
    async def continue_session(request):
        """Continue a session — triggers AWPV2ContinueTurn."""
        session_id = request.match_info["session_id"]
        factory = _factory()
        registry = factory.registry

        binding = registry.card_session_binding_store.load(session_id)
        if not binding:
            return _json({"error": "Session not found"}, 404)

        try:
            from ..nodes.continue_turn_execution_node import AWPV2ContinueTurn

            node = AWPV2ContinueTurn()
            result = node.execute(
                session_id=session_id,
                director_profile_id="deepseek-v4-flash-director",
                writer_profile_id="deepseek-v4-pro-writer",
            )

            receipt = result[0] if len(result) > 0 else {}
            diagnostics = result[2] if len(result) > 2 else {}
            turn_record = result[4] if len(result) > 4 else {}

            success = diagnostics.get("outcome") == "success"
            return _json({
                "success": success,
                "turn_id": receipt.get("turn_id", ""),
                "turn_index": receipt.get("turn_index", 0),
                "quality": receipt.get("quality_verdict", ""),
                "writer_output": turn_record.get("writer_output", "")[:500] if turn_record else "",
            })
        except Exception as e:
            return _json({"error": f"Continue failed: {str(e)[:200]}"}, 500)

    # ── SPA static file serving ──────────────────────────────────────────

    @server.PromptServer.instance.routes.get("/awp")
    async def serve_spa_index(request):
        """Serve the SPA index.html."""
        index_path = _MANAGEMENT_DIR / "index.html"
        if not index_path.exists():
            return web.Response(
                text="Management panel not built yet. Run: cd web && npm run build",
                content_type="text/plain",
            )
        with open(str(index_path), "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html")

    @server.PromptServer.instance.routes.get("/awp/{tail:.*}")
    async def serve_spa_static(request):
        """Serve static files or fall back to index.html for SPA routing."""
        tail = request.match_info.get("tail", "")
        file_path = _MANAGEMENT_DIR / tail

        if file_path.exists() and file_path.is_file():
            content_type = _mime_type(file_path.suffix)
            with open(str(file_path), "rb") as f:
                return web.Response(body=f.read(), content_type=content_type)

        # SPA fallback
        index_path = _MANAGEMENT_DIR / "index.html"
        if index_path.exists():
            with open(str(index_path), "r", encoding="utf-8") as f:
                return web.Response(text=f.read(), content_type="text/html")

        return web.Response(text="Not found", status=404)

except ImportError:
    pass  # Running outside ComfyUI — API routes are not registered
