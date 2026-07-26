"""Safe, project-bound persistence for author/editor collaboration."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.novel_authoring import (
    AuthorApproval,
    AuthorChapterPlan,
    AuthorMaterial,
    AuthorPlanStatus,
)

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _explicit_approval(text: str) -> bool:
    normalized = text.strip().lower()
    return any(
        phrase in normalized
        for phrase in ("确认", "批准", "同意", "就按这个", "摘要准确", "approve")
    )


def _explicit_execution(text: str) -> bool:
    normalized = text.strip().lower()
    return any(
        phrase in normalized
        for phrase in (
            "交给管线写",
            "开始写",
            "现在写",
            "执行写作",
            "按这个写",
            "execute",
        )
    )


class NovelAuthoringService:
    """Owns the fixed ``.awp/authoring`` layout for one novel project."""

    def __init__(self, project_root: str | Path, project_id: str):
        self.project_root = Path(project_root).resolve()
        self.project_id = project_id
        self.root = (self.project_root / ".awp" / "authoring").resolve()
        try:
            self.root.relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError("authoring root escaped project root") from exc
        self.plan_dir = self.root / "chapter-plans"
        self.journal_dir = self.root / "journal"
        self.inbox_path = self.root / "inbox.jsonl"
        self.index_path = self.root / "index.json"
        self.plan_dir.mkdir(parents=True, exist_ok=True)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(str(self.root), threading.RLock())

    def record_author_message(self, text: str, session_id: str, turn: int) -> str:
        if not text.strip():
            raise ValueError("author message cannot be empty")
        message_id = f"author-{uuid.uuid4().hex}"
        path = self.journal_dir / f"{datetime.now().astimezone():%Y-%m-%d}.jsonl"
        self._append_jsonl(
            path,
            {
                "message_id": message_id,
                "project_id": self.project_id,
                "session_id": session_id,
                "turn": turn,
                "text": text,
                "created_at": _now(),
            },
        )
        return message_id

    def capture_material(
        self,
        summary: str,
        category: str,
        source_message_ids: list[str],
    ) -> AuthorMaterial:
        material = AuthorMaterial(
            material_id=f"material-{uuid.uuid4().hex}",
            project_id=self.project_id,
            summary=summary,
            category=category or "idea",
            source_message_ids=source_message_ids,
            captured_at=_now(),
        )
        self._append_jsonl(self.inbox_path, material.model_dump(mode="json"))
        return material

    def save_plan(self, plan: AuthorChapterPlan) -> AuthorChapterPlan:
        if plan.project_id != self.project_id:
            raise ValueError("plan belongs to another project")
        with self._lock:
            index = self._read_index()
            entry = index["plans"].get(plan.plan_id)
            revision = 1 if entry is None else int(entry["latest_revision"]) + 1
            saved = plan.model_copy(
                update={
                    "revision": revision,
                    "approval": None,
                    "executed_at": "",
                    "execution_message_id": "",
                }
            )
            if saved.status in {AuthorPlanStatus.APPROVED, AuthorPlanStatus.EXECUTED}:
                saved = saved.model_copy(
                    update={"status": AuthorPlanStatus.PENDING_CONFIRMATION}
                )
            self._write_plan(saved)
            index["plans"][plan.plan_id] = {
                "latest_revision": revision,
                "chapter_index": saved.chapter_index,
                "status": saved.status.value,
            }
            self._atomic_json(self.index_path, index)
            return saved

    def get_plan(
        self, plan_id: str, revision: int | None = None
    ) -> AuthorChapterPlan:
        index = self._read_index()
        entry = index["plans"].get(plan_id)
        if entry is None:
            raise FileNotFoundError(f"author plan not found: {plan_id}")
        selected = revision or int(entry["latest_revision"])
        path = self._plan_path(plan_id, selected)
        if not path.is_file():
            raise FileNotFoundError(f"author plan revision not found: {plan_id} v{selected}")
        return AuthorChapterPlan.model_validate_json(path.read_text(encoding="utf-8"))

    def approve_plan(
        self,
        plan_id: str,
        revision: int,
        current_turn: int,
        current_message_id: str,
        current_author_message: str,
        confirmation_quote: str,
    ) -> AuthorChapterPlan:
        with self._lock:
            plan = self._latest_exact(plan_id, revision)
            if current_turn <= plan.proposal_turn:
                raise ValueError("approval requires a later author turn")
            if not confirmation_quote or confirmation_quote not in current_author_message:
                raise ValueError("confirmation quote must occur in the author message")
            if not _explicit_approval(current_author_message):
                raise ValueError("author message is not an explicit approval")
            if plan.unresolved_questions:
                raise ValueError("cannot approve a plan with unresolved questions")
            digest = hashlib.sha256(
                json.dumps(
                    plan.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            approved = plan.model_copy(
                update={
                    "status": AuthorPlanStatus.APPROVED,
                    "approval": AuthorApproval(
                        message_id=current_message_id,
                        confirmation_quote=confirmation_quote,
                        turn=current_turn,
                        approved_at=_now(),
                        content_hash=digest,
                    ),
                }
            )
            self._write_plan(approved)
            self._update_status(approved)
            return approved

    def mark_executed(
        self,
        plan_id: str,
        revision: int,
        current_turn: int,
        current_message_id: str,
        current_author_message: str,
        confirmation_quote: str,
    ) -> AuthorChapterPlan:
        with self._lock:
            plan = self.validate_execution_request(
                plan_id,
                revision,
                current_turn,
                current_author_message,
                confirmation_quote,
            )
            executed = plan.model_copy(
                update={
                    "status": AuthorPlanStatus.EXECUTED,
                    "executed_at": _now(),
                    "execution_message_id": current_message_id,
                }
            )
            self._write_plan(executed)
            self._update_status(executed)
            return executed

    def validate_execution_request(
        self,
        plan_id: str,
        revision: int,
        current_turn: int,
        current_author_message: str,
        confirmation_quote: str,
    ) -> AuthorChapterPlan:
        """Validate consent before any chapter compilation or Writer side effect."""

        plan = self._latest_exact(plan_id, revision)
        if plan.status != AuthorPlanStatus.APPROVED or plan.approval is None:
            raise ValueError("only an approved plan can execute")
        if current_turn <= plan.approval.turn:
            raise ValueError("execution requires a later author turn")
        if not confirmation_quote or confirmation_quote not in current_author_message:
            raise ValueError("execution quote must occur in the author message")
        if not _explicit_execution(current_author_message):
            raise ValueError("author message is not an explicit execution request")
        return plan

    def authoring_context(self, chapter_index: int | None = None) -> dict[str, Any]:
        index = self._read_index()
        plans: list[dict[str, Any]] = []
        for plan_id, entry in index["plans"].items():
            if chapter_index is not None and entry["chapter_index"] != chapter_index:
                continue
            plan = self.get_plan(plan_id)
            plans.append(plan.model_dump(mode="json"))
        materials = self._read_jsonl(self.inbox_path)
        return {
            "project_id": self.project_id,
            "plans": plans,
            "pending_materials": [
                item for item in materials if item.get("status") == "pending"
            ],
        }

    def _latest_exact(self, plan_id: str, revision: int) -> AuthorChapterPlan:
        index = self._read_index()
        entry = index["plans"].get(plan_id)
        if entry is None or int(entry["latest_revision"]) != revision:
            raise ValueError("plan revision is not the latest")
        return self.get_plan(plan_id, revision)

    def _update_status(self, plan: AuthorChapterPlan) -> None:
        index = self._read_index()
        index["plans"][plan.plan_id]["status"] = plan.status.value
        self._atomic_json(self.index_path, index)

    def _plan_path(self, plan_id: str, revision: int) -> Path:
        safe_id = "".join(
            char for char in plan_id if char.isalnum() or char in {"-", "_"}
        )
        if not safe_id or safe_id != plan_id:
            raise ValueError("invalid plan id")
        return self.plan_dir / f"{safe_id}.v{revision}.json"

    def _write_plan(self, plan: AuthorChapterPlan) -> None:
        self._atomic_json(
            self._plan_path(plan.plan_id, plan.revision),
            plan.model_dump(mode="json"),
        )

    def _read_index(self) -> dict[str, Any]:
        if not self.index_path.is_file():
            return {"schema_version": 1, "plans": {}}
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("plans"), dict):
            raise ValueError("invalid authoring index")
        return data

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

    def _atomic_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


__all__ = ["NovelAuthoringService"]
