"""REST handlers for conversation CRUD, search, and project-file discovery."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from aiohttp import web

from .novel_conversation_store import NovelConversationStore
from .novel_project_context_service import NovelProjectContextService
from .session_runtime_registry import SessionRuntimeStoreRegistry


def _json(data: Any, status: int = 200) -> web.Response:
    return web.json_response(
        {"data": data},
        status=status,
        dumps=lambda value: json.dumps(value, ensure_ascii=False, default=str),
    )


def _error(message: str, status: int = 400, **extra: Any) -> web.Response:
    payload = {"error": message, **extra}
    return web.json_response(payload, status=status)


class NovelConversationApiHandlers:
    """Handlers for the conversation and project-file endpoints."""

    def __init__(
        self,
        registry_factory,
        workspace_catalog=None,
    ):
        self._registry_factory = registry_factory
        self._workspace_catalog = workspace_catalog

    def _store(self, project_id: str, room: str) -> NovelConversationStore:
        from .novel_workspace_catalog import NovelWorkspaceCatalog

        if self._workspace_catalog is not None:
            workspace = self._workspace_catalog.require(project_id)
            return NovelConversationStore(workspace.root, project_id)
        raise RuntimeError("workspace catalog unavailable")

    def _context_service(self, project_id: str) -> NovelProjectContextService:
        from .novel_workspace_catalog import NovelWorkspaceCatalog

        if self._workspace_catalog is not None:
            workspace = self._workspace_catalog.require(project_id)
            return NovelProjectContextService(workspace.root)
        raise RuntimeError("workspace catalog unavailable")

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def list_conversations(self, request: web.Request) -> web.Response:
        project_id = request.match_info["project_id"]
        room = request.match_info["room"]
        include_archived = request.query.get("archived") == "1"
        try:
            store = self._store(project_id, room)
            branches = await asyncio.to_thread(
                store.list_branches, room, include_archived=include_archived
            )
            return _json([b.model_dump(mode="json") for b in branches])
        except ValueError as exc:
            return _error(str(exc), 400)
        except (KeyError, FileNotFoundError) as exc:
            return _error(str(exc), 404)

    async def create_conversation(self, request: web.Request) -> web.Response:
        project_id = request.match_info["project_id"]
        room = request.match_info["room"]
        try:
            body = await request.json()
            title = body.get("title", "")
            if not title or len(title) > 80:
                return _error("title must be 1-80 characters", 400)
            parent_branch_id = body.get("parent_branch_id")
            fork_event_id = body.get("fork_event_id")
            confirm_effects = body.get("confirm_effects", False)

            store = self._store(project_id, room)
            branch = await asyncio.to_thread(
                store.create_branch,
                room,
                parent_branch_id=parent_branch_id,
                fork_event_id=fork_event_id,
                title=title,
                confirm_effects=confirm_effects,
            )
            return _json(branch.model_dump(mode="json"), 201)
        except ValueError as exc:
            message = str(exc)
            if "side effect" in message:
                effects = store.effects_after(
                    room, parent_branch_id or "main",
                    after_event_id=(fork_event_id or 0),
                )
                return _error(
                    message,
                    409,
                    code="branch_has_effects",
                    effects=[e.model_dump(mode="json") for e in effects],
                )
            return _error(message, 400)
        except (KeyError, FileNotFoundError) as exc:
            return _error(str(exc), 404)

    async def update_conversation(self, request: web.Request) -> web.Response:
        project_id = request.match_info["project_id"]
        room = request.match_info["room"]
        branch_id = request.match_info["branch_id"]
        try:
            body = await request.json()
            allowed = {"title", "archived"}
            unknown = set(body.keys()) - allowed
            if unknown:
                return _error(
                    f"unknown fields: {', '.join(sorted(unknown))}", 400
                )
            title = body.get("title")
            archived = body.get("archived")
            if title is not None and (not title or len(title) > 80):
                return _error("title must be 1-80 characters", 400)

            store = self._store(project_id, room)
            await asyncio.to_thread(
                store.update_branch,
                room,
                branch_id,
                title=title,
                archived=archived,
            )
            return _json({"branch_id": branch_id, "updated": True})
        except ValueError as exc:
            return _error(str(exc), 400)
        except (KeyError, FileNotFoundError) as exc:
            return _error(str(exc), 404)

    async def search_conversations(self, request: web.Request) -> web.Response:
        project_id = request.match_info["project_id"]
        room = request.match_info["room"]
        query = request.query.get("q", "")
        if not query or len(query) > 200:
            return _error("query must be 1-200 characters", 400)
        try:
            store = self._store(project_id, room)
            hits = await asyncio.to_thread(
                store.search, room, query, max_results=50
            )
            return _json([h.model_dump(mode="json") for h in hits])
        except ValueError as exc:
            return _error(str(exc), 400)
        except (KeyError, FileNotFoundError) as exc:
            return _error(str(exc), 404)

    # ------------------------------------------------------------------
    # Project files
    # ------------------------------------------------------------------

    async def list_project_files(self, request: web.Request) -> web.Response:
        project_id = request.match_info["project_id"]
        query = request.query.get("q", "")
        try:
            service = self._context_service(project_id)
            files = await asyncio.to_thread(
                service.list_files, query=query, limit=50
            )
            return _json(files)
        except ValueError as exc:
            return _error(str(exc), 400)
        except (KeyError, FileNotFoundError) as exc:
            return _error(str(exc), 404)


def register_conversation_routes(
    app: web.Application,
    registry_factory,
    workspace_catalog=None,
) -> None:
    handlers = NovelConversationApiHandlers(registry_factory, workspace_catalog)
    prefix = "/awp/api/v1/novels/{project_id}/editor-rooms/{room}"

    app.router.add_get(
        f"{prefix}/conversations",
        handlers.list_conversations,
    )
    app.router.add_post(
        f"{prefix}/conversations",
        handlers.create_conversation,
    )
    app.router.add_patch(
        f"{prefix}/conversations/{{branch_id}}",
        handlers.update_conversation,
    )
    app.router.add_get(
        f"{prefix}/conversation-search",
        handlers.search_conversations,
    )
    app.router.add_get(
        "/awp/api/v1/novels/{project_id}/project-files",
        handlers.list_project_files,
    )


__all__ = ["NovelConversationApiHandlers", "register_conversation_routes"]
