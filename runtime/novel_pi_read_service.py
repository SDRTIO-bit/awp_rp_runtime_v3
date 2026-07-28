"""Project-bound, read-only tools exposed to Pi novel role sessions."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from .novel_role_context import NovelRoleContext


class NovelPiReadService:
    """Read novel state without accepting paths, project ids, or write actions."""

    MAX_CONTENT_CHARS = 24_000
    TOOL_NAMES = frozenset({
        "project_status",
        "read_project_contract",
        "read_chapter_plan",
        "read_chapter",
        "read_ledger",
        "read_characters",
        "read_write_packet",
    })
    _ALLOWED_ARGUMENTS = {
        "project_status": frozenset(),
        "read_project_contract": frozenset(),
        "read_chapter_plan": frozenset({"chapter_index"}),
        "read_chapter": frozenset({"chapter_index"}),
        "read_ledger": frozenset({"section", "limit"}),
        "read_characters": frozenset({"limit"}),
        "read_write_packet": frozenset(),
    }

    def __init__(self, context: NovelRoleContext):
        self._context = context

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self.TOOL_NAMES:
            raise ValueError(f"unsupported Pi role read tool: {name}")
        if not isinstance(arguments, dict):
            raise ValueError("Pi role tool arguments must be an object")
        unexpected = set(arguments) - self._ALLOWED_ARGUMENTS[name]
        if unexpected:
            raise ValueError(f"unexpected arguments for {name}: {sorted(unexpected)}")

        payload = getattr(self, f"_{name}")(arguments)
        serialized = json.dumps(self._jsonable(payload), ensure_ascii=False, separators=(",", ":"))
        truncated = len(serialized) > self.MAX_CONTENT_CHARS
        if truncated:
            marker = "\n...[truncated]"
            serialized = serialized[: self.MAX_CONTENT_CHARS - len(marker)] + marker
        return {"ok": True, "content": serialized, "truncated": truncated}

    @property
    def _registry(self):
        return self._context.registry

    def _project_status(self, arguments: dict[str, Any]) -> dict[str, Any]:
        project_id = self._context.project_id
        project = self._registry.novel_project_store.load(project_id)
        plans = self._registry.novel_chapter_plan_store.list_by_project(project_id)
        ledger = self._registry.novel_ledger_store.list_by_project(project_id)
        characters = self._registry.novel_character_store.list_by_project(project_id)
        return {
            "project": self._jsonable(project),
            "chapter_count": len(plans),
            "ledger_count": len(ledger),
            "character_count": len(characters),
            "active_chapter_index": self._context.chapter_index,
        }

    def _read_project_contract(self, arguments: dict[str, Any]) -> dict[str, Any]:
        project_id = self._context.project_id
        project = self._registry.novel_project_store.load(project_id)
        volumes = self._registry.novel_volume_store.list_by_project(project_id)
        return {
            "project": self._jsonable(project),
            "volumes": [self._jsonable(volume) for volume in volumes],
        }

    def _read_chapter_plan(self, arguments: dict[str, Any]) -> dict[str, Any]:
        chapter_index = self._chapter_index(arguments)
        plan = self._registry.novel_chapter_plan_store.load_by_index(
            self._context.project_id,
            chapter_index,
        )
        return {
            "chapter_index": chapter_index,
            "found": plan is not None,
            "plan": self._jsonable(plan),
        }

    def _read_chapter(self, arguments: dict[str, Any]) -> dict[str, Any]:
        chapter_index = self._chapter_index(arguments)
        plan = self._registry.novel_chapter_plan_store.load_by_index(
            self._context.project_id,
            chapter_index,
        )
        draft = None
        if plan is not None:
            draft = self._registry.novel_chapter_draft_store.load_latest_accepted(plan.chapter_id)
        return {
            "chapter_index": chapter_index,
            "found": draft is not None,
            "plan": self._jsonable(plan),
            "text": getattr(draft, "text", "") if draft is not None else "",
            "draft": self._jsonable(draft),
        }

    def _read_ledger(self, arguments: dict[str, Any]) -> dict[str, Any]:
        section = str(arguments.get("section", "") or "")
        limit = self._bounded_limit(arguments.get("limit", 50), maximum=200)
        items = self._registry.novel_ledger_store.list_by_project(
            self._context.project_id,
            section=section,
        )[:limit]
        return {
            "section": section,
            "items": [self._jsonable(item) for item in items],
        }

    def _read_characters(self, arguments: dict[str, Any]) -> dict[str, Any]:
        limit = self._bounded_limit(arguments.get("limit", 50), maximum=100)
        characters = self._registry.novel_character_store.list_by_project(
            self._context.project_id
        )[:limit]
        return {"characters": [self._jsonable(character) for character in characters]}

    def _read_write_packet(self, arguments: dict[str, Any]) -> Any:
        packet = self._context.artifacts.get("write_packet")
        return self._jsonable(packet) if packet is not None else {}

    def _chapter_index(self, arguments: dict[str, Any]) -> int:
        raw = arguments.get("chapter_index", self._context.chapter_index)
        try:
            chapter_index = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("chapter_index must be an integer") from exc
        if chapter_index < 1:
            raise ValueError("chapter_index must be positive")
        return chapter_index

    @staticmethod
    def _bounded_limit(raw: Any, *, maximum: int) -> int:
        try:
            limit = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit must be an integer") from exc
        return max(1, min(limit, maximum))

    @classmethod
    def _jsonable(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): cls._jsonable(nested) for key, nested in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._jsonable(nested) for nested in value]
        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            return cls._jsonable(to_dict())
        if is_dataclass(value):
            return cls._jsonable(asdict(value))
        return str(value)

