"""Project-bound business tools exposed to the embedded Pi Agent only."""

from __future__ import annotations

import json
from typing import Any

from .novel_engine import NovelEngine
from .novel_trace import NovelStreamCallbacks


class NovelPiToolService:
    """Execute the small Pi tool allowlist without exposing paths or stores."""

    ALLOWED = frozenset({
        "project_status",
        "read_chapter",
        "plan_chapter",
        "write_chapter",
        "audit_chapter",
    })

    def __init__(self, registry, *, project_id: str, callbacks=None):
        self._registry = registry
        self._project_id = project_id
        self._callbacks = callbacks

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, object]:
        if name not in self.ALLOWED:
            raise ValueError(f"Pi tool is not allowed: {name}")
        if name == "project_status":
            return {"ok": True, "content": self._status()}

        chapter = self._chapter_argument(args)
        if name == "read_chapter":
            return {"ok": True, "content": self._read_chapter(chapter)}
        if name == "plan_chapter":
            plan = self._engine().plan_chapter(
                project_id=self._project_id,
                chapter_index=chapter,
                task_description=str(args.get("task_description", "")),
            )
            return {"ok": True, "content": f"第{chapter}章已规划：{plan.title}"}
        if name == "write_chapter":
            draft = self._engine().write_chapter_stream(
                project_id=self._project_id,
                chapter_index=chapter,
                write_guidance=str(args.get("write_guidance", "")),
            )
            return {
                "ok": True,
                "content": f"第{chapter}章完成：{draft.char_count}字，{draft.status}",
            }

        report = self._engine().audit_chapter(
            project_id=self._project_id,
            chapter_index=chapter,
        )
        return {"ok": True, "content": json.dumps(report, ensure_ascii=False)}

    def _engine(self) -> NovelEngine:
        callbacks = self._callbacks
        return NovelEngine(
            self._registry,
            callbacks=NovelStreamCallbacks(
                on_phase=getattr(callbacks, "on_phase", None),
                on_beat=getattr(callbacks, "on_beat", None),
                on_chunk=getattr(callbacks, "on_chunk", None),
                on_error=getattr(callbacks, "on_error", None),
            ),
        )

    def _chapter_argument(self, args: dict[str, Any]) -> int:
        try:
            chapter = int(args.get("chapter", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("chapter must be a positive integer") from exc
        if chapter < 1:
            raise ValueError("chapter must be a positive integer")
        return chapter

    def _status(self) -> str:
        project = self._registry.novel_project_store.load(self._project_id)
        if not project:
            raise ValueError(f"Project not found: {self._project_id}")
        plans = self._registry.novel_chapter_plan_store.list_by_project(self._project_id)
        generated = 0
        for plan in plans:
            if self._registry.novel_chapter_draft_store.load_latest(plan.chapter_id):
                generated += 1
        return (
            f"《{project.title}》\n"
            f"项目: {self._project_id}\n"
            f"章节计划: {len(plans)}\n"
            f"已生成: {generated}"
        )

    def _read_chapter(self, chapter: int) -> str:
        plan = self._registry.novel_chapter_plan_store.load_by_index(
            self._project_id, chapter
        )
        if not plan:
            return f"第{chapter}章尚未规划。"
        draft = self._registry.novel_chapter_draft_store.load_latest(plan.chapter_id)
        if not draft or not draft.text:
            return f"第{chapter}章尚未生成。"
        preview = draft.text[:2000]
        return (
            f"第{chapter}章《{plan.title}》\n"
            f"字数: {draft.char_count} | 状态: {draft.status}\n\n"
            f"{preview}\n\n...（共 {draft.char_count} 字）"
        )
