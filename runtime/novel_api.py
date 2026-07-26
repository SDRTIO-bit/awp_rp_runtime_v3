"""Standalone HTTP handlers for the novel-writing runtime.

This module deliberately has no ComfyUI or RP imports.  A registry factory is
injected so the same routes can be tested without opening the production
database.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable

from aiohttp import web

from ..contracts.novel_character import NovelCharacter
from ..contracts.novel_project import NovelProject
from .novel_engine import NovelEngine
from .novel_document_service import (
    DocumentConflictError,
    NovelDocumentService,
)
from .novel_planner_adapter import NovelPlannerAdapter
from .session_runtime_registry import SessionRuntimeStoreRegistry
from .novel_workspace_catalog import NovelWorkspaceCatalog
from .novel_prompt_service import NovelPromptService

RegistryFactory = Callable[[], SessionRuntimeStoreRegistry]


def _json(data: Any, status: int = 200) -> web.Response:
    return web.json_response(
        {"data": data},
        status=status,
        dumps=lambda value: json.dumps(value, ensure_ascii=False, default=str),
    )


def _chapter_index(raw: str) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 1 else None


class NovelApiHandlers:
    """Request handlers bound to a novel store registry factory."""

    def __init__(
        self,
        registry_factory: RegistryFactory,
        workspace_catalog: NovelWorkspaceCatalog | None = None,
    ):
        self._registry_factory = registry_factory
        self._workspace_catalog = workspace_catalog

    def _registry(self, project_id: str = "") -> SessionRuntimeStoreRegistry:
        if self._workspace_catalog is not None and project_id:
            return self._workspace_catalog.registry(project_id)
        return self._registry_factory()

    def _document_service(self, project_id: str) -> NovelDocumentService:
        if self._workspace_catalog is None:
            raise KeyError("workspace catalog is unavailable")
        workspace = self._workspace_catalog.require(project_id)
        return NovelDocumentService(
            workspace,
            self._workspace_catalog.registry(project_id),
        )

    def _prompt_service(self, project_id: str) -> NovelPromptService:
        if self._workspace_catalog is None:
            raise KeyError("workspace catalog is unavailable")
        return NovelPromptService(
            self._workspace_catalog.require(project_id)
        )

    async def list_prompts(self, request: web.Request) -> web.Response:
        try:
            prompts = await asyncio.to_thread(
                self._prompt_service(
                    request.match_info["project_id"]
                ).list_roles
            )
            return _json(
                [item.model_dump(mode="json") for item in prompts]
            )
        except (KeyError, FileNotFoundError) as exc:
            return _json({"error": str(exc)}, 404)

    async def get_prompt(self, request: web.Request) -> web.Response:
        try:
            prompt = await asyncio.to_thread(
                self._prompt_service(
                    request.match_info["project_id"]
                ).resolve,
                request.match_info["role"],
            )
            return _json(prompt.model_dump(mode="json"))
        except ValueError as exc:
            return _json({"error": str(exc)}, 400)
        except (KeyError, FileNotFoundError) as exc:
            return _json({"error": str(exc)}, 404)

    async def save_prompt(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            content = body.get("content")
            expected = body.get("expected_revision")
            if not isinstance(content, str) or not isinstance(expected, int):
                raise ValueError(
                    "content and integer expected_revision are required"
                )
            prompt = await asyncio.to_thread(
                self._prompt_service(
                    request.match_info["project_id"]
                ).save_override,
                request.match_info["role"],
                content,
                expected,
            )
            return _json(prompt.model_dump(mode="json"))
        except DocumentConflictError as exc:
            return _json(
                {
                    "error": str(exc),
                    "current_revision": exc.current_revision,
                },
                409,
            )
        except (TypeError, ValueError) as exc:
            return _json({"error": str(exc)}, 400)
        except (KeyError, FileNotFoundError) as exc:
            return _json({"error": str(exc)}, 404)

    async def list_prompt_versions(
        self, request: web.Request
    ) -> web.Response:
        try:
            versions = await asyncio.to_thread(
                self._prompt_service(
                    request.match_info["project_id"]
                ).list_versions,
                request.match_info["role"],
            )
            return _json(
                [item.model_dump(mode="json") for item in versions]
            )
        except ValueError as exc:
            return _json({"error": str(exc)}, 400)
        except KeyError as exc:
            return _json({"error": str(exc)}, 404)

    async def prompt_diff(self, request: web.Request) -> web.Response:
        try:
            raw_revision = request.query.get("revision")
            revision = (
                None if raw_revision in (None, "") else int(raw_revision)
            )
            diff = await asyncio.to_thread(
                self._prompt_service(
                    request.match_info["project_id"]
                ).diff,
                request.match_info["role"],
                revision,
            )
            return _json({"diff": diff})
        except (TypeError, ValueError) as exc:
            return _json({"error": str(exc)}, 400)
        except (KeyError, FileNotFoundError) as exc:
            return _json({"error": str(exc)}, 404)

    async def restore_prompt(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            revision = body.get("revision")
            expected = body.get("expected_revision")
            if (
                not isinstance(revision, int)
                or not isinstance(expected, int)
            ):
                raise ValueError(
                    "revision and expected_revision must be integers"
                )
            prompt = await asyncio.to_thread(
                self._prompt_service(
                    request.match_info["project_id"]
                ).restore,
                request.match_info["role"],
                revision,
                expected,
            )
            return _json(prompt.model_dump(mode="json"))
        except DocumentConflictError as exc:
            return _json(
                {"error": str(exc), "current_revision": exc.current_revision},
                409,
            )
        except (TypeError, ValueError) as exc:
            return _json({"error": str(exc)}, 400)
        except (KeyError, FileNotFoundError) as exc:
            return _json({"error": str(exc)}, 404)

    async def get_document(self, request: web.Request) -> web.Response:
        try:
            document = await asyncio.to_thread(
                self._document_service(
                    request.match_info["project_id"]
                ).read,
                request.match_info["kind"],
                request.query.get("resource_id", ""),
            )
            return _json(document.model_dump(mode="json"))
        except ValueError as exc:
            return _json({"error": str(exc)}, 400)
        except (KeyError, FileNotFoundError) as exc:
            return _json({"error": str(exc)}, 404)

    async def list_document_versions(
        self, request: web.Request
    ) -> web.Response:
        try:
            versions = await asyncio.to_thread(
                self._document_service(
                    request.match_info["project_id"]
                ).list_versions,
                request.match_info["kind"],
                request.query.get("resource_id", ""),
            )
            return _json(
                [item.model_dump(mode="json") for item in versions]
            )
        except ValueError as exc:
            return _json({"error": str(exc)}, 400)
        except KeyError as exc:
            return _json({"error": str(exc)}, 404)

    async def get_document_version(
        self, request: web.Request
    ) -> web.Response:
        try:
            revision = int(request.match_info["revision"])
            document = await asyncio.to_thread(
                self._document_service(
                    request.match_info["project_id"]
                ).read_version,
                request.match_info["kind"],
                revision,
                request.query.get("resource_id", ""),
            )
            return _json(document.model_dump(mode="json"))
        except (TypeError, ValueError) as exc:
            return _json({"error": str(exc)}, 400)
        except (KeyError, FileNotFoundError) as exc:
            return _json({"error": str(exc)}, 404)

    async def save_document(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("request body must be an object")
            content = body.get("content")
            expected_revision = body.get("expected_revision")
            if not isinstance(content, str):
                raise ValueError("content must be text")
            if (
                not isinstance(expected_revision, int)
                or isinstance(expected_revision, bool)
            ):
                raise ValueError("expected_revision must be an integer")
            document = await asyncio.to_thread(
                self._document_service(
                    request.match_info["project_id"]
                ).save,
                request.match_info["kind"],
                content,
                expected_revision,
                request.query.get("resource_id", ""),
            )
            return _json(document.model_dump(mode="json"))
        except DocumentConflictError as exc:
            return _json(
                {
                    "error": str(exc),
                    "current_revision": exc.current_revision,
                },
                409,
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return _json({"error": str(exc)}, 400)
        except (KeyError, FileNotFoundError) as exc:
            return _json({"error": str(exc)}, 404)

    async def create_project(self, request: web.Request) -> web.Response:
        body = await request.json()
        project = NovelProject(
            project_id=body.get("project_id", f"novel-{uuid.uuid4().hex[:8]}"),
            title=body.get("title", ""),
            genre=body.get("genre", ""),
            target_platform=body.get("target_platform", ""),
            target_reader=body.get("target_reader", ""),
            core_emotion=body.get("core_emotion", ""),
            one_sentence_pitch=body.get("one_sentence_pitch", ""),
            status="planning",
        )
        try:
            self._registry().novel_project_store.create(project)
            return _json(project.to_dict())
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def list_projects(self, _request: web.Request) -> web.Response:
        try:
            if self._workspace_catalog is not None:
                projects = []
                for workspace in self._workspace_catalog.list():
                    project = self._workspace_catalog.registry(
                        workspace.project_id
                    ).novel_project_store.load(workspace.project_id)
                    projects.append(
                        project.to_dict()
                        if project is not None
                        else {
                            "project_id": workspace.project_id,
                            "title": workspace.root.name,
                            "status": "local",
                        }
                    )
                return _json(projects)
            projects = self._registry().novel_project_store.list_all()
            return _json([project.to_dict() for project in projects])
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def get_project(self, request: web.Request) -> web.Response:
        try:
            project_id = request.match_info["project_id"]
            registry = (
                self._workspace_catalog.registry(project_id)
                if self._workspace_catalog is not None
                else self._registry()
            )
            project = registry.novel_project_store.load(project_id)
            if project is None:
                return _json({"error": "Project not found"}, 404)
            return _json(project.to_dict())
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def delete_project(self, request: web.Request) -> web.Response:
        project_id = request.match_info["project_id"]
        try:
            registry = self._registry()
            registry.novel_plan_store.delete(project_id)
            registry.novel_project_store.delete(project_id)
            return _json({"success": True})
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def get_outline(self, request: web.Request) -> web.Response:
        try:
            project_id = request.match_info["project_id"]
            plan = self._registry(project_id).novel_plan_store.load(project_id)
            if plan is None:
                return _json({"error": "Outline not found for this project"}, 404)
            return _json(plan.to_dict())
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def list_chapters(self, request: web.Request) -> web.Response:
        try:
            project_id = request.match_info["project_id"]
            plans = self._registry(project_id).novel_chapter_plan_store.list_by_project(project_id)
            return _json([plan.to_dict() for plan in plans])
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def plan_chapter(self, request: web.Request) -> web.Response:
        project_id = request.match_info["project_id"]
        body = await request.json()
        chapter_index = body.get("chapter_index", 1)
        if not isinstance(chapter_index, int) or chapter_index < 1:
            return _json({"error": "chapter_index must be >= 1"}, 400)
        try:
            plan = await asyncio.to_thread(
                NovelEngine(self._registry()).plan_chapter,
                project_id=project_id,
                chapter_index=chapter_index,
                task_description=body.get("task_description", ""),
            )
            return _json(plan.to_dict())
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def get_chapter_plan(self, request: web.Request) -> web.Response:
        idx = _chapter_index(request.match_info["idx"])
        if idx is None:
            return _json({"error": "Invalid chapter index"}, 400)
        try:
            project_id = request.match_info["project_id"]
            plan = self._registry(project_id).novel_chapter_plan_store.load_by_index(project_id, idx)
            if plan is None:
                return _json({"error": "Plan not found"}, 404)
            return _json(plan.to_dict())
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def write_chapter(self, request: web.Request) -> web.Response:
        idx = _chapter_index(request.match_info["idx"])
        if idx is None:
            return _json({"error": "Invalid chapter index"}, 400)
        try:
            draft = await asyncio.to_thread(
                NovelEngine(self._registry()).write_chapter,
                project_id=request.match_info["project_id"],
                chapter_index=idx,
            )
            return _json(draft.to_dict())
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def list_drafts(self, request: web.Request) -> web.Response:
        idx = _chapter_index(request.match_info["idx"])
        if idx is None:
            return _json({"error": "Invalid chapter index"}, 400)
        try:
            registry = self._registry(request.match_info["project_id"])
            plan = registry.novel_chapter_plan_store.load_by_index(
                request.match_info["project_id"], idx
            )
            if plan is None:
                return _json({"error": "Chapter not found"}, 404)
            drafts = registry.novel_chapter_draft_store.list_by_chapter(plan.chapter_id)
            return _json([draft.to_dict() for draft in drafts])
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def revise_chapter(self, request: web.Request) -> web.Response:
        idx = _chapter_index(request.match_info["idx"])
        if idx is None:
            return _json({"error": "Invalid chapter index"}, 400)
        body = await request.json()
        try:
            draft = await asyncio.to_thread(
                NovelEngine(self._registry()).revise_chapter,
                project_id=request.match_info["project_id"],
                chapter_index=idx,
                feedback=body.get("feedback", ""),
            )
            return _json(draft.to_dict())
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def batch_write(self, request: web.Request) -> web.Response:
        body = await request.json()
        chapter_start = body.get("chapter_start", 1)
        chapter_end = body.get("chapter_end", 3)
        if (
            not isinstance(chapter_start, int)
            or not isinstance(chapter_end, int)
            or chapter_start < 1
            or chapter_end < chapter_start
        ):
            return _json({"error": "Invalid chapter range"}, 400)
        try:
            drafts = await asyncio.to_thread(
                NovelEngine(self._registry()).batch_write,
                project_id=request.match_info["project_id"],
                chapter_start=chapter_start,
                chapter_end=chapter_end,
            )
            return _json(
                {"drafts": [draft.to_dict() for draft in drafts], "count": len(drafts)}
            )
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def list_ledger(self, request: web.Request) -> web.Response:
        try:
            project_id = request.match_info["project_id"]
            items = self._registry(project_id).novel_ledger_store.list_by_project(project_id, request.query.get("section", ""))
            return _json([item.to_dict() for item in items])
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def list_characters(self, request: web.Request) -> web.Response:
        try:
            project_id = request.match_info["project_id"]
            characters = self._registry(project_id).novel_character_store.list_by_project(project_id)
            return _json([character.to_dict() for character in characters])
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def autonomy_summary(self, request: web.Request) -> web.Response:
        project_id = request.match_info["project_id"]
        try:
            registry = self._registry()
            if registry.novel_project_store.load(project_id) is None:
                return _json({"error": "Project not found"}, 404)
            agendas = registry.novel_ledger_store.list_by_project(
                project_id, "npc_agenda"
            )
            actions = registry.novel_ledger_store.list_by_project(
                project_id, "npc_action"
            )
            chapter_counts: dict[str, int] = {}
            for item in actions:
                key = str(item.source_chapter or 0)
                chapter_counts[key] = chapter_counts.get(key, 0) + 1
            return _json(
                {
                    "project_id": project_id,
                    "active_count": sum(item.status == "active" for item in agendas),
                    "stale_count": sum(item.status == "stale" for item in agendas),
                    "chapter_action_counts": chapter_counts,
                }
            )
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def promote_character_state(self, request: web.Request) -> web.Response:
        project_id = request.match_info["project_id"]
        character_id = request.match_info["character_id"]
        body = await request.json()
        patch = body.get("patch")
        if not isinstance(patch, dict):
            return _json({"error": "patch must be an object"}, 400)
        forbidden = {"identity", "motivation", "known_fact_ids"}.intersection(patch)
        if forbidden:
            return _json(
                {"error": f"Forbidden keys in patch: {', '.join(sorted(forbidden))}"},
                400,
            )
        source_item_id = body.get("source_item_id", "")
        try:
            registry = self._registry()
            character = registry.novel_character_store.load(character_id)
            if character is None or character.project_id != project_id:
                return _json(
                    {"error": "Character not found or does not belong to project"}, 400
                )
            source = registry.novel_ledger_store.load(source_item_id)
            if (
                source is None
                or source.project_id != project_id
                or source.section != "npc_action"
            ):
                return _json(
                    {
                        "error": (
                            "source_item_id must reference an npc_action ledger "
                            "item in this project"
                        )
                    },
                    400,
                )
            now = datetime.now(timezone.utc).isoformat()
            state = dict(character.current_state)
            state.update(patch)
            state.update(promoted_from_item_id=source_item_id, promoted_at=now)
            updated: NovelCharacter = replace(
                character, current_state=state, updated_at=now
            )
            registry.novel_character_store.save(updated)
            return _json(
                {
                    "character_id": character_id,
                    "project_id": project_id,
                    "promoted_from_item_id": source_item_id,
                    "current_state": state,
                }
            )
        except Exception as exc:
            return _json({"error": str(exc)[:200]}, 500)

    async def plan_from_concept(self, request: web.Request) -> web.Response:
        body = await request.json()
        concept = body.get("concept", "")
        if not concept:
            return _json({"error": "concept is required"}, 400)
        try:
            plan = await asyncio.to_thread(
                NovelPlannerAdapter(self._registry()).plan_novel,
                concept=concept,
                title=body.get("title", ""),
                genre=body.get("genre", ""),
                target_platform=body.get("target_platform", ""),
                additional_requirements=body.get("additional_requirements", ""),
            )
            return _json(plan.to_dict())
        except Exception as exc:
            return _json({"error": str(exc)[:500]}, 500)


def register_novel_routes(
    app: web.Application,
    registry_factory: RegistryFactory,
    workspace_catalog: NovelWorkspaceCatalog | None = None,
) -> None:
    """Register the complete novel-only API surface on ``app``."""

    handlers = NovelApiHandlers(registry_factory, workspace_catalog)
    prefix = "/awp/api/v1/novels"

    app.router.add_get(prefix, handlers.list_projects)
    app.router.add_post(prefix, handlers.create_project)
    app.router.add_post(f"{prefix}/plan", handlers.plan_from_concept)
    app.router.add_get(
        f"{prefix}/{{project_id}}/prompts",
        handlers.list_prompts,
    )
    app.router.add_get(
        f"{prefix}/{{project_id}}/prompts/{{role}}/versions",
        handlers.list_prompt_versions,
    )
    app.router.add_get(
        f"{prefix}/{{project_id}}/prompts/{{role}}/diff",
        handlers.prompt_diff,
    )
    app.router.add_post(
        f"{prefix}/{{project_id}}/prompts/{{role}}/restore",
        handlers.restore_prompt,
    )
    app.router.add_get(
        f"{prefix}/{{project_id}}/prompts/{{role}}",
        handlers.get_prompt,
    )
    app.router.add_put(
        f"{prefix}/{{project_id}}/prompts/{{role}}",
        handlers.save_prompt,
    )
    app.router.add_get(
        f"{prefix}/{{project_id}}/documents/{{kind}}/versions/{{revision}}",
        handlers.get_document_version,
    )
    app.router.add_get(
        f"{prefix}/{{project_id}}/documents/{{kind}}/versions",
        handlers.list_document_versions,
    )
    app.router.add_get(
        f"{prefix}/{{project_id}}/documents/{{kind}}",
        handlers.get_document,
    )
    app.router.add_put(
        f"{prefix}/{{project_id}}/documents/{{kind}}",
        handlers.save_document,
    )
    app.router.add_get(f"{prefix}/{{project_id}}", handlers.get_project)
    app.router.add_delete(f"{prefix}/{{project_id}}", handlers.delete_project)
    app.router.add_get(f"{prefix}/{{project_id}}/outline", handlers.get_outline)
    app.router.add_get(f"{prefix}/{{project_id}}/chapters", handlers.list_chapters)
    app.router.add_post(
        f"{prefix}/{{project_id}}/chapters/plan", handlers.plan_chapter
    )
    app.router.add_get(
        f"{prefix}/{{project_id}}/chapters/{{idx}}/plan",
        handlers.get_chapter_plan,
    )
    app.router.add_post(
        f"{prefix}/{{project_id}}/chapters/{{idx}}/write", handlers.write_chapter
    )
    app.router.add_get(
        f"{prefix}/{{project_id}}/chapters/{{idx}}/drafts", handlers.list_drafts
    )
    app.router.add_post(
        f"{prefix}/{{project_id}}/chapters/{{idx}}/revise",
        handlers.revise_chapter,
    )
    app.router.add_post(
        f"{prefix}/{{project_id}}/batch-write", handlers.batch_write
    )
    app.router.add_get(f"{prefix}/{{project_id}}/ledger", handlers.list_ledger)
    app.router.add_get(
        f"{prefix}/{{project_id}}/characters", handlers.list_characters
    )
    app.router.add_get(
        f"{prefix}/{{project_id}}/autonomy-summary", handlers.autonomy_summary
    )
    app.router.add_post(
        f"{prefix}/{{project_id}}/characters/{{character_id}}/state-promotions",
        handlers.promote_character_state,
    )


__all__ = ["NovelApiHandlers", "register_novel_routes"]
