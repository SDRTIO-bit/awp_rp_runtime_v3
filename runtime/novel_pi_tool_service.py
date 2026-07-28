"""Project-bound tools exposed to the dedicated Pi writing editor."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..contracts.novel_authoring import AuthorChapterPlan
from ..contracts.novel_conversation import EditorWorkPlan
from ..contracts.novel_revision import (
    ChapterRevisionPlan,
    RevisionBatchStatus,
    RevisionPatch,
)
from ..contracts.novel_project_skill import (
    ProjectSkillProposal,
    ProjectSkillVersion,
)
from .novel_author_plan_compiler import AuthorPlanCompiler
from .novel_authoring_service import NovelAuthoringService
from .novel_chapter_revision_service import NovelChapterRevisionService
from .novel_project_skill_service import NovelProjectSkillService
from .novel_engine import NovelEngine
from .novel_project_sandbox import NovelProjectSandbox
from .novel_trace import NovelStreamCallbacks


class NovelPiToolService:
    """Execute the editor allowlist without exposing paths, stores, or shell."""

    ALLOWED_TOOLS = frozenset(
        {
            "read",
            "ls",
            "find",
            "grep",
            "write",
            "edit",
            "bash",
            "project_status",
            "read_chapter",
            "save_revision_plan",
            "approve_revision_plan",
            "apply_revision_plan",
            "propose_project_skill",
            "audit_chapter",
            "read_authoring_context",
            "capture_author_material",
            "save_author_plan",
            "approve_author_plan",
            "execute_author_plan",
            "update_work_plan",
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
        prompt_snapshot_id: str = "",
    ):
        self._registry = registry
        self._project_id = project_id
        self._callbacks = callbacks
        self._authoring = NovelAuthoringService(project_dir, project_id)
        self._project_sandbox = NovelProjectSandbox(project_dir)
        self._project_dir = Path(project_dir)
        self._current_turn = current_turn
        self._current_message_id = current_message_id
        self._current_author_message = current_author_message
        self._prompt_snapshot_id = prompt_snapshot_id

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, object]:
        if name not in self.ALLOWED_TOOLS:
            raise ValueError(f"Pi tool is not allowed: {name}")
        if name in {"read", "ls", "find", "grep", "write", "edit", "bash"}:
            return self._execute_project_tool(name, args)
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
        if name == "save_revision_plan":
            self._require_turn_context()
            return self._save_revision_plan(args)
        if name == "approve_revision_plan":
            self._require_turn_context()
            return self._approve_revision_plan(args)
        if name == "apply_revision_plan":
            self._require_turn_context()
            return self._apply_revision_plan(args)
        if name == "propose_project_skill":
            self._require_turn_context()
            return self._propose_project_skill(args)
        if name == "update_work_plan":
            return self._handle_work_plan(args)
        chapter = self._chapter_argument(args)
        if name == "read_chapter":
            chapter_read = NovelChapterRevisionService(
                self._registry, project_id=self._project_id
            ).read_chapter(chapter)
            return {
                "ok": True,
                "content": json.dumps(
                    chapter_read.model_dump(mode="json"), ensure_ascii=False
                ),
            }
        report = self._engine().audit_chapter(
            project_id=self._project_id,
            chapter_index=chapter,
        )
        return {"ok": True, "content": json.dumps(report, ensure_ascii=False)}

    def _revision_service(self) -> NovelChapterRevisionService:
        return NovelChapterRevisionService(self._registry, project_id=self._project_id)

    def _skill_service(self) -> NovelProjectSkillService:
        return NovelProjectSkillService(
            self._registry, project_id=self._project_id, project_root=self._project_dir
        )

    def _propose_project_skill(self, args: dict[str, Any]) -> dict[str, object]:
        skill_id = str(args.get("skill_id", ""))
        proposal = ProjectSkillProposal(
            proposal_id=str(
                args.get("proposal_id") or f"skill-proposal-{uuid.uuid4().hex[:12]}"
            ),
            project_id=self._project_id,
            purpose=str(args.get("purpose", "")),
            behavior_impact=str(args.get("behavior_impact", "")),
            proposal_turn=self._current_turn,
            skill=ProjectSkillVersion(
                skill_id=skill_id,
                version=1,
                content=str(args.get("content", "")),
                source="editor",
            ),
        )
        saved = self._skill_service().save_editor_proposal(proposal)
        return {
            "ok": True,
            "content": (
                f"技能提议已保存并等待作者确认：{saved.proposal_id}。"
                "编辑不能启用该技能；作者确认并显式启用后才会在下一轮生效。"
            ),
        }

    def _save_revision_plan(self, args: dict[str, Any]) -> dict[str, object]:
        chapter_index = self._chapter_argument({"chapter": args.get("chapter_index")})
        base_revision = int(args.get("base_revision", 0))
        patches = tuple(
            RevisionPatch.model_validate({
                **patch,
                "chapter_index": chapter_index,
                "base_revision": base_revision,
            })
            for patch in args.get("patches", [])
        )
        plan = ChapterRevisionPlan(
            plan_id=str(args.get("plan_id") or f"revision-{uuid.uuid4().hex[:12]}"),
            project_id=self._project_id,
            chapter_index=chapter_index,
            base_revision=base_revision,
            status=RevisionBatchStatus.PENDING_CONFIRMATION,
            patches=patches,
            proposal_turn=self._current_turn,
            reason=str(args.get("reason", "")),
        )
        saved = self._revision_service().save_plan(plan)
        return {
            "ok": True,
            "content": f"正文修订计划已保存并等待确认：{saved.plan_id}（基于 r{saved.base_revision}）",
        }

    def _approve_revision_plan(self, args: dict[str, Any]) -> dict[str, object]:
        quote = str(args.get("confirmation_quote", "")).strip()
        self._require_current_quote(quote)
        approved = self._revision_service().approve_plan(
            str(args.get("plan_id", "")), turn=self._current_turn
        )
        return {
            "ok": True,
            "content": f"正文修订计划已批准：{approved.plan_id}。请在后续作者轮次确认应用。",
        }

    def _apply_revision_plan(self, args: dict[str, Any]) -> dict[str, object]:
        quote = str(args.get("confirmation_quote", "")).strip()
        self._require_current_quote(quote)
        draft = self._revision_service().apply_plan(
            str(args.get("plan_id", "")),
            expected_revision=int(args.get("expected_revision", 0)),
            turn=self._current_turn,
        )
        return {
            "ok": True,
            "content": f"正文修订已应用：{draft.draft_id}（r{draft.revision}）。",
        }

    def _require_current_quote(self, quote: str) -> None:
        if not quote or quote not in self._current_author_message:
            raise ValueError("confirmation_quote must occur in the current author message")

    def _handle_work_plan(self, args: dict[str, Any]) -> dict[str, object]:
        items = args.get("items", [])
        plan = EditorWorkPlan(
            explanation=str(args.get("explanation", "")),
            items=items,
        )
        self._notify_tool({
            "type": "editor_work_plan_updated",
            "status": "completed",
            "plan": plan.model_dump(mode="json"),
        })
        return {"ok": True, "content": "工作计划已更新。"}

    def _execute_project_tool(
        self, name: str, args: dict[str, Any]
    ) -> dict[str, object]:
        request = self._project_sandbox.classify(name, args)
        self._notify_tool(
            {
                "status": "checking",
                **request.model_dump(mode="json"),
            }
        )
        if request.risk == "hard_deny":
            self._notify_tool(
                {
                    "status": "denied",
                    **request.model_dump(mode="json"),
                }
            )
            raise ValueError(request.reason)
        if request.risk == "important":
            approval = getattr(
                self._callbacks, "request_tool_approval", None
            )
            decision = (
                approval(request.model_dump(mode="json"))
                if callable(approval)
                else "deny"
            )
            if decision != "allow":
                self._notify_tool(
                    {
                        "status": "denied",
                        **request.model_dump(mode="json"),
                    }
                )
                raise ValueError("tool call denied by author approval policy")
        self._notify_tool(
            {
                "status": "running",
                **request.model_dump(mode="json"),
            }
        )
        if name in {"read", "ls", "find", "grep"}:
            content = self._project_sandbox.execute_read(name, args)
        else:
            content = self._project_sandbox.execute_write(name, args)
        self._notify_tool(
            {
                "status": "completed",
                **request.model_dump(mode="json"),
            }
        )
        return {"ok": True, "content": content}

    def _notify_tool(self, payload: dict[str, Any]) -> None:
        callback = getattr(self._callbacks, "on_tool_event", None)
        if callable(callback):
            callback(payload)

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
        phase_callback = getattr(self._callbacks, "on_phase", None)
        if phase_callback:
            phase_callback(
                "start",
                "author_plan_compile",
                {"chapter_index": plan.chapter_index},
            )
        self._bind_project_root()
        chapter = AuthorPlanCompiler().compile_and_save(plan, self._registry)
        if phase_callback:
            phase_callback(
                "end",
                "author_plan_compile",
                {"chapter_index": plan.chapter_index},
            )
        draft = self._engine().write_chapter_stream(
            project_id=self._project_id,
            chapter_index=chapter.chapter_index,
            write_guidance="",
        )
        if draft.status != "accepted":
            raise ValueError(
                "Writer output was not accepted; author plan remains approved"
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

    def _bind_project_root(self) -> None:
        """Bind Writer provenance lookup to this already project-scoped service."""

        project = self._registry.novel_project_store.load(self._project_id)
        if project is None:
            raise ValueError(f"Project not found: {self._project_id}")
        config = dict(getattr(project, "config", {}) or {})
        expected = self._authoring.project_root
        configured = str(config.get("novel_dir", "") or "")
        if configured and Path(configured).resolve() != expected:
            raise ValueError("project root does not match the authoring workspace")
        if not configured:
            config["novel_dir"] = str(expected)
            self._registry.novel_project_store.update(
                replace(project, config=config)
            )

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
            prompt_snapshot_id=self._prompt_snapshot_id,
            callbacks=NovelStreamCallbacks(
                on_phase=getattr(callbacks, "on_phase", None),
                on_beat=getattr(callbacks, "on_beat", None),
                on_chunk=getattr(callbacks, "on_chunk", None),
                on_error=getattr(callbacks, "on_error", None),
                on_draft_saved=getattr(callbacks, "on_draft_saved", None),
                should_cancel=(
                    getattr(callbacks, "should_cancel", None)
                    or (lambda: False)
                ),
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
            bool(self._registry.novel_chapter_draft_store.load_latest_accepted(plan.chapter_id))
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
        draft = self._registry.novel_chapter_draft_store.load_latest_accepted(plan.chapter_id)
        if not draft or not draft.text:
            return f"第{chapter}章尚未生成。"
        return (
            f"第{chapter}章《{plan.title}》\n"
            f"字数: {draft.char_count} | 状态: {draft.status}\n\n"
            f"{draft.text[:2000]}\n\n...（共 {draft.char_count} 字）"
        )
