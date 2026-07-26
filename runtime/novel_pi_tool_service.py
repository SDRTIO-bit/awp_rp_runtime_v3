"""Project-bound tools exposed to the dedicated Pi writing editor."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ..contracts.novel_authoring import AuthorChapterPlan
from .novel_author_plan_compiler import AuthorPlanCompiler
from .novel_authoring_service import NovelAuthoringService
from .novel_engine import NovelEngine
from .novel_trace import NovelStreamCallbacks


class NovelPiToolService:
    """Execute the editor allowlist without exposing paths, stores, or shell."""

    ALLOWED_TOOLS = frozenset(
        {
            "project_status",
            "read_chapter",
            "audit_chapter",
            "read_authoring_context",
            "capture_author_material",
            "save_author_plan",
            "approve_author_plan",
            "execute_author_plan",
        }
    )
    ALLOWED = ALLOWED_TOOLS

    def __init__(
        self,
        registry,
        *,
        project_id: str,
        project_dir: str | Path,
        callbacks=None,
        current_turn: int = 0,
        current_message_id: str = "",
        current_author_message: str = "",
    ):
        self._registry = registry
        self._project_id = project_id
        self._callbacks = callbacks
        self._authoring = NovelAuthoringService(project_dir, project_id)
        self._current_turn = current_turn
        self._current_message_id = current_message_id
        self._current_author_message = current_author_message

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, object]:
        if name not in self.ALLOWED_TOOLS:
            raise ValueError(f"Pi tool is not allowed: {name}")
        if name == "project_status":
            return {"ok": True, "content": self._status()}
        if name == "read_authoring_context":
            chapter = args.get("chapter")
            parsed = None if chapter in (None, "") else self._chapter_argument(args)
            return {
                "ok": True,
                "content": json.dumps(
                    self._authoring.authoring_context(parsed),
                    ensure_ascii=False,
                ),
            }
        if name == "capture_author_material":
            self._require_turn_context()
            material = self._authoring.capture_material(
                summary=str(args.get("summary", "")),
                category=str(args.get("category", "idea")),
                source_message_ids=[self._current_message_id],
            )
            return {
                "ok": True,
                "content": f"素材已保存：{material.material_id}（pending）",
            }
        if name == "save_author_plan":
            self._require_turn_context()
            plan_data = dict(args)
            plan_data.update(
                {
                    "plan_id": str(
                        args.get("plan_id")
                        or f"author-ch{args.get('chapter_index', 0)}-{uuid.uuid4().hex[:8]}"
                    ),
                    "project_id": self._project_id,
                    "status": "pending_confirmation",
                    "proposal_turn": self._current_turn,
                    "approval": None,
                }
            )
            plan = AuthorChapterPlan.model_validate(plan_data)
            saved = self._authoring.save_plan(plan)
            return {
                "ok": True,
                "content": (
                    f"作者计划已保存并等待确认：{saved.plan_id} v{saved.revision}"
                ),
            }
        if name == "approve_author_plan":
            self._require_turn_context()
            approved = self._authoring.approve_plan(
                str(args.get("plan_id", "")),
                int(args.get("revision", 0)),
                self._current_turn,
                self._current_message_id,
                self._current_author_message,
                str(args.get("confirmation_quote", "")),
            )
            return {
                "ok": True,
                "content": (
                    f"作者计划已批准：{approved.plan_id} v{approved.revision}。"
                    "尚未启动写作，请在后续作者轮次再次确认执行。"
                ),
            }
        if name == "execute_author_plan":
            return self._execute_author_plan(args)

        chapter = self._chapter_argument(args)
        if name == "read_chapter":
            return {"ok": True, "content": self._read_chapter(chapter)}
        report = self._engine().audit_chapter(
            project_id=self._project_id,
            chapter_index=chapter,
        )
        return {"ok": True, "content": json.dumps(report, ensure_ascii=False)}

    def _execute_author_plan(self, args: dict[str, Any]) -> dict[str, object]:
        self._require_turn_context()
        plan_id = str(args.get("plan_id", ""))
        revision = int(args.get("revision", 0))
        confirmation_quote = str(args.get("confirmation_quote", ""))
        plan = self._authoring.validate_execution_request(
            plan_id,
            revision,
            self._current_turn,
            self._current_author_message,
            confirmation_quote,
        )
        chapter = AuthorPlanCompiler().compile_and_save(plan, self._registry)
        draft = self._engine().write_chapter_stream(
            project_id=self._project_id,
            chapter_index=chapter.chapter_index,
            write_guidance="",
        )
        executed = self._authoring.mark_executed(
            plan_id,
            revision,
            self._current_turn,
            self._current_message_id,
            self._current_author_message,
            confirmation_quote,
        )
        return {
            "ok": True,
            "content": (
                f"第{executed.chapter_index}章完成："
                f"{draft.char_count}字，{draft.status}"
            ),
        }

    def _require_turn_context(self) -> None:
        if (
            self._current_turn < 1
            or not self._current_message_id
            or not self._current_author_message
        ):
            raise ValueError("authoring tool requires the current author turn context")

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

    @staticmethod
    def _chapter_argument(args: dict[str, Any]) -> int:
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
        generated = sum(
            bool(self._registry.novel_chapter_draft_store.load_latest(plan.chapter_id))
            for plan in plans
        )
        authoring = self._authoring.authoring_context()
        pending = sum(
            plan["status"] == "pending_confirmation"
            for plan in authoring["plans"]
        )
        return (
            f"《{project.title}》\n"
            f"项目: {self._project_id}\n"
            f"章节计划: {len(plans)}\n"
            f"待作者确认: {pending}\n"
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
        return (
            f"第{chapter}章《{plan.title}》\n"
            f"字数: {draft.char_count} | 状态: {draft.status}\n\n"
            f"{draft.text[:2000]}\n\n...（共 {draft.char_count} 字）"
        )
