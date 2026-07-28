"""Controlled reads and mutations for accepted novel chapter revisions."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..contracts.novel_draft import ChapterDraft
from ..contracts.novel_revision import (
    ChapterParagraph,
    ChapterRead,
    ChapterRevisionPlan,
    RevisionBatchStatus,
    RevisionPatchOperation,
)


class RevisionConflictError(RuntimeError):
    """Raised when a patch no longer targets the current accepted revision."""

    def __init__(self, current_revision: int):
        super().__init__(f"chapter revision conflict; current accepted revision is {current_revision}")
        self.current_revision = current_revision


class NovelChapterRevisionService:
    """Project-scoped service for revisions; canonical prose is always accepted."""

    def __init__(self, registry, *, project_id: str):
        self._registry = registry
        self._project_id = project_id

    def read_chapter(self, chapter_index: int) -> ChapterRead:
        if chapter_index < 1:
            raise ValueError("chapter_index must be positive")
        plan = self._registry.novel_chapter_plan_store.load_by_index(
            self._project_id, chapter_index
        )
        if plan is None:
            raise ValueError(f"Chapter plan not found: {self._project_id} ch{chapter_index}")
        draft = self._registry.novel_chapter_draft_store.load_latest_accepted(
            plan.chapter_id
        )
        if draft is None or not draft.text:
            raise ValueError(f"Accepted chapter draft not found: {self._project_id} ch{chapter_index}")
        paragraphs = tuple(
            ChapterParagraph(
                paragraph_id=f"r{draft.revision}:p{ordinal}",
                ordinal=ordinal,
                text=text,
                sha256=self._hash(text),
            )
            for ordinal, text in enumerate(self._paragraphs(draft.text), start=1)
        )
        return ChapterRead(
            chapter_index=chapter_index,
            title=plan.title,
            draft_id=draft.draft_id,
            accepted_revision=draft.revision,
            text_sha256=self._hash(draft.text),
            paragraphs=paragraphs,
        )

    def save_plan(self, plan: ChapterRevisionPlan) -> ChapterRevisionPlan:
        if plan.project_id != self._project_id:
            raise ValueError("revision plan does not belong to this project")
        conn = self._registry.db.connect()
        conn.execute(
            """INSERT OR REPLACE INTO novel_chapter_revision_plans
               (plan_id, project_id, chapter_index, base_revision, status, plan_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                plan.plan_id,
                plan.project_id,
                plan.chapter_index,
                plan.base_revision,
                plan.status.value,
                json.dumps(plan.model_dump(mode="json"), ensure_ascii=False),
            ),
        )
        conn.commit()
        return plan

    def get_plan(self, plan_id: str) -> ChapterRevisionPlan:
        row = self._registry.db.connect().execute(
            "SELECT plan_json FROM novel_chapter_revision_plans "
            "WHERE plan_id = ? AND project_id = ?",
            (plan_id, self._project_id),
        ).fetchone()
        if row is None:
            raise ValueError("revision plan not found")
        return ChapterRevisionPlan.model_validate(json.loads(row["plan_json"]))

    def approve_plan(self, plan_id: str, *, turn: int) -> ChapterRevisionPlan:
        plan = self.get_plan(plan_id)
        if plan.status != RevisionBatchStatus.PENDING_CONFIRMATION:
            raise ValueError("revision plan is not pending confirmation")
        if turn <= plan.proposal_turn:
            raise ValueError("revision plan approval requires a later author turn")
        approved = plan.model_copy(update={
            "status": RevisionBatchStatus.APPROVED,
            "approval_turn": turn,
        })
        self.save_plan(approved)
        return approved

    def export_current(self, project_root: str | Path) -> dict[str, object]:
        root = Path(project_root).resolve()
        output = root / "output"
        output.mkdir(parents=True, exist_ok=True)
        chapters: list[dict[str, object]] = []
        for plan in self._registry.novel_chapter_plan_store.list_by_project(self._project_id):
            draft = self._registry.novel_chapter_draft_store.load_latest_accepted(
                plan.chapter_id
            )
            if draft is None or not draft.text:
                continue
            filename = f"chapter_{plan.chapter_index:02d}.md"
            self._atomic_text(output / filename, draft.text)
            chapters.append({
                "chapter_index": plan.chapter_index,
                "filename": filename,
                "revision": draft.revision,
                "draft_id": draft.draft_id,
                "sha256": self._hash(draft.text),
            })
        manifest = {
            "project_id": self._project_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "chapters": chapters,
            "legacy_snapshots": sorted(
                path.name for path in root.glob("output_pre_*") if path.is_dir()
            ),
        }
        self._atomic_text(
            output / "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        return manifest

    def replace_chapter_text(
        self,
        chapter_index: int,
        text: str,
        *,
        expected_revision: int,
        source: str = "author_edit",
        created_at: str = "",
    ) -> ChapterDraft:
        """Apply an explicit author full-text replacement without a raw draft write.

        This is deliberately separate from editor patch plans: the browser author
        has already supplied the complete replacement as their direct action.  It
        nevertheless receives the same accepted-version compare-and-swap guard.
        """
        if chapter_index < 1 or expected_revision < 1:
            raise ValueError("chapter_index and expected_revision must be positive")
        if not isinstance(text, str) or not text:
            raise ValueError("replacement chapter text is required")
        conn = self._registry.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            chapter = self._registry.novel_chapter_plan_store.load_by_index(
                self._project_id, chapter_index
            )
            if chapter is None:
                raise ValueError("chapter plan not found")
            row = conn.execute(
                """SELECT draft_json FROM novel_chapter_drafts
                   WHERE chapter_id = ? AND status = 'accepted'
                   ORDER BY revision DESC LIMIT 1""",
                (chapter.chapter_id,),
            ).fetchone()
            if row is None:
                raise ValueError("accepted chapter draft not found")
            current = ChapterDraft.from_dict(json.loads(row["draft_json"]))
            if current.revision != expected_revision:
                raise RevisionConflictError(current.revision)
            replacement = ChapterDraft(
                draft_id=f"draft-{chapter.chapter_id}-r{current.revision + 1}",
                chapter_id=chapter.chapter_id,
                revision=current.revision + 1,
                source_plan_revision=current.source_plan_revision,
                text=text,
                raw_text=text,
                char_count=len(text),
                status="accepted",
                source=source,
                created_at=created_at or datetime.now(timezone.utc).isoformat(),
            )
            conn.execute(
                """INSERT INTO novel_chapter_drafts
                   (draft_id, chapter_id, revision, status, draft_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    replacement.draft_id,
                    replacement.chapter_id,
                    replacement.revision,
                    replacement.status,
                    json.dumps(replacement.to_dict(), ensure_ascii=False),
                ),
            )
            conn.commit()
            return replacement
        except Exception:
            conn.rollback()
            raise

    def apply_plan(
        self, plan_id: str, *, expected_revision: int, turn: int | None = None
    ) -> ChapterDraft:
        conn = self._registry.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT plan_json FROM novel_chapter_revision_plans WHERE plan_id = ? AND project_id = ?",
                (plan_id, self._project_id),
            ).fetchone()
            if row is None:
                raise ValueError("revision plan not found")
            plan = ChapterRevisionPlan.model_validate(json.loads(row["plan_json"]))
            if plan.status != RevisionBatchStatus.APPROVED:
                raise ValueError("revision plan is not approved")
            if turn is not None and turn <= plan.approval_turn:
                raise ValueError("revision plan application requires a later author turn")
            chapter = self._registry.novel_chapter_plan_store.load_by_index(
                self._project_id, plan.chapter_index
            )
            if chapter is None:
                raise ValueError("chapter plan not found")
            draft_row = conn.execute(
                """SELECT draft_json FROM novel_chapter_drafts
                   WHERE chapter_id = ? AND status = 'accepted'
                   ORDER BY revision DESC LIMIT 1""",
                (chapter.chapter_id,),
            ).fetchone()
            if draft_row is None:
                raise ValueError("accepted chapter draft not found")
            current = ChapterDraft.from_dict(json.loads(draft_row["draft_json"]))
            if current.revision != expected_revision or current.revision != plan.base_revision:
                raise RevisionConflictError(current.revision)
            text = self._apply_patches(current.text, plan)
            revision = current.revision + 1
            applied = ChapterDraft(
                draft_id=f"draft-{chapter.chapter_id}-r{revision}",
                chapter_id=chapter.chapter_id,
                revision=revision,
                source_plan_revision=current.source_plan_revision,
                text=text,
                raw_text=text,
                char_count=len(text),
                status="accepted",
                source="editor_patch",
            )
            conn.execute(
                """INSERT INTO novel_chapter_drafts
                   (draft_id, chapter_id, revision, status, draft_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    applied.draft_id,
                    applied.chapter_id,
                    applied.revision,
                    applied.status,
                    json.dumps(applied.to_dict(), ensure_ascii=False),
                ),
            )
            applied_plan = plan.model_copy(update={"status": RevisionBatchStatus.APPLIED})
            conn.execute(
                """UPDATE novel_chapter_revision_plans
                   SET status = ?, plan_json = ?, updated_at = datetime('now') WHERE plan_id = ?""",
                (
                    applied_plan.status.value,
                    json.dumps(applied_plan.model_dump(mode="json"), ensure_ascii=False),
                    plan_id,
                ),
            )
            conn.commit()
            return applied
        except Exception:
            conn.rollback()
            raise

    def _apply_patches(self, text: str, plan: ChapterRevisionPlan) -> str:
        paragraphs = list(self._paragraphs(text))
        for patch in plan.patches:
            if patch.chapter_index != plan.chapter_index or patch.base_revision != plan.base_revision:
                raise ValueError("patch does not match its revision plan")
            expected_id = f"r{plan.base_revision}:p"
            if not patch.paragraph_id.startswith(expected_id):
                raise ValueError("patch paragraph does not match base revision")
            ordinal = int(patch.paragraph_id.rsplit("p", 1)[1])
            if ordinal > len(paragraphs):
                raise RevisionConflictError(plan.base_revision)
            index = ordinal - 1
            if self._hash(paragraphs[index]) != patch.expected_paragraph_hash:
                raise RevisionConflictError(plan.base_revision)
            operation = patch.operation
            if operation == RevisionPatchOperation.REPLACE:
                paragraphs[index] = patch.replacement_text
            elif operation == RevisionPatchOperation.DELETE:
                del paragraphs[index]
            elif operation == RevisionPatchOperation.INSERT_BEFORE:
                paragraphs.insert(index, patch.replacement_text)
            elif operation == RevisionPatchOperation.INSERT_AFTER:
                paragraphs.insert(index + 1, patch.replacement_text)
        return "\n\n".join(paragraphs)

    @staticmethod
    def _paragraphs(text: str) -> tuple[str, ...]:
        return tuple(part for part in re.split(r"\r?\n\s*\r?\n", text) if part)

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _atomic_text(path: Path, content: str) -> None:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()


__all__ = ["NovelChapterRevisionService", "RevisionConflictError"]
