"""Project file mutation previews, receipts, history, and approved restore.

All mutations go through difflib.unified_diff for preview, then
execute under the authoring lock, recording immutable receipts.
Old backup JSON manifests are read without modification.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.novel_conversation import ProjectMutationPreview, ProjectMutationReceipt
from .novel_project_sandbox import NovelProjectSandbox

_MAX_DIFF_CHARS = 60_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NovelProjectHistoryService:
    """Compute unified diffs, record receipts, list/restore versions."""

    def __init__(self, project_root: str | Path):
        self._sandbox = NovelProjectSandbox(project_root)
        self.root = Path(project_root).resolve()

    def preview(self, name: str, args: dict[str, Any]) -> ProjectMutationPreview:
        """Compute proposed change without writing or auditing."""
        raw = str(args.get("path", "") or "")
        path = self._sandbox.resolve_relative(raw, write=True)
        before = path.read_text(encoding="utf-8") if path.is_file() else ""
        before_hash = hashlib.sha256(before.encode("utf-8")).hexdigest()

        if name == "write":
            content = args.get("content", "")
            if not isinstance(content, str):
                raise ValueError("content must be text")
            after = content
        elif name == "edit":
            edits = args.get("edits", [])
            if not isinstance(edits, list):
                raise ValueError("edits must be a list")
            after = before
            for edit in edits:
                if not isinstance(edit, dict):
                    raise ValueError("each edit must be an object")
                old = edit.get("oldText", "")
                new = edit.get("newText", "")
                if before.count(old) != 1:
                    raise ValueError("oldText must occur exactly once")
                after = after.replace(old, new, 1)
        else:
            raise ValueError(f"unsupported preview tool: {name}")

        after_hash = hashlib.sha256(after.encode("utf-8")).hexdigest()
        diff = self._compute_diff(raw, before, after)
        return ProjectMutationPreview(
            path=raw,
            operation=name,
            before_hash=before_hash,
            after_hash=after_hash,
            diff=diff,
        )

    def execute(
        self,
        name: str,
        args: dict[str, Any],
        *,
        branch_id: str,
        turn_id: str,
    ) -> ProjectMutationReceipt:
        """Execute mutation and return a durable receipt."""
        preview = self.preview(name, args)
        raw = str(args.get("path", "") or "")
        path = self._sandbox.resolve_relative(raw, write=True)

        self._sandbox.execute_write(name, args)

        receipt = ProjectMutationReceipt(
            change_id=f"chg-{uuid.uuid4().hex}",
            turn_id=turn_id,
            branch_id=branch_id,
            path=raw,
            operation=preview.operation,
            before_hash=preview.before_hash,
            after_hash=preview.after_hash,
            diff=preview.diff,
            history_version_id=f"hist-{uuid.uuid4().hex}",
            created_at=_now(),
        )
        self._save_receipt(receipt)
        return receipt

    def list_versions(self, path_str: str) -> list[dict[str, Any]]:
        """Return version metadata for a project-relative path."""
        self._sandbox.resolve_relative(path_str)
        safe_name = path_str.replace("/", "__").replace("\\", "__")
        history_dir = self.root / ".awp" / "file-history" / safe_name
        if not history_dir.is_dir():
            return []

        versions: list[dict[str, Any]] = []
        for entry in sorted(history_dir.iterdir(), reverse=True):
            if not entry.name.endswith(".json"):
                continue
            try:
                data = json.loads(entry.read_text(encoding="utf-8"))
                versions.append({
                    "version_id": entry.stem,
                    "sha256": data.get("sha256", ""),
                    "created_at": data.get("created_at", ""),
                    "size_bytes": len(data.get("content", "")),
                })
            except (json.JSONDecodeError, OSError):
                continue
            if len(versions) >= 100:
                break
        return versions

    def restore(
        self,
        path_str: str,
        version_id: str,
        expected_hash: str,
        *,
        branch_id: str,
        turn_id: str,
    ) -> ProjectMutationReceipt:
        """Restore a file to a historical version, producing a new receipt."""
        self._sandbox.resolve_relative(path_str)
        safe_name = path_str.replace("/", "__").replace("\\", "__")
        history_dir = self.root / ".awp" / "file-history" / safe_name
        if not history_dir.is_dir():
            raise ValueError("no history for this file")

        # Find the version
        entry_path = history_dir / f"{version_id}.json"
        if not entry_path.is_file():
            raise ValueError(f"version not found: {version_id}")
        data = json.loads(entry_path.read_text(encoding="utf-8"))
        old_content = data.get("content", "")

        # Verify expected hash
        path = self._sandbox.resolve_relative(path_str, write=True)
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        current_hash = hashlib.sha256(current.encode("utf-8")).hexdigest()
        if expected_hash and current_hash != expected_hash:
            raise ValueError("file changed since version was listed")

        before_hash = current_hash
        after_hash = hashlib.sha256(old_content.encode("utf-8")).hexdigest()
        diff = self._compute_diff(path_str, current, old_content)

        # Do the restore
        self._sandbox._atomic_write(path, old_content)

        receipt = ProjectMutationReceipt(
            change_id=f"chg-{uuid.uuid4().hex}",
            turn_id=turn_id,
            branch_id=branch_id,
            path=path_str,
            operation="restore",
            before_hash=before_hash,
            after_hash=after_hash,
            diff=diff,
            history_version_id=version_id,
            created_at=_now(),
        )
        self._save_receipt(receipt)
        return receipt

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_diff(self, path_str: str, before: str, after: str) -> str:
        label_a = f"a/{path_str}"
        label_b = f"b/{path_str}"
        if not before:
            label_a = "/dev/null"
        diff_lines = list(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )
        )
        diff = "".join(diff_lines)
        if len(diff) > _MAX_DIFF_CHARS:
            diff = diff[:_MAX_DIFF_CHARS] + "\n... (diff truncated)"
        return diff

    def _save_receipt(self, receipt: ProjectMutationReceipt) -> None:
        rec_dir = self.root / ".awp" / "mutation-receipts"
        rec_dir.mkdir(parents=True, exist_ok=True)
        rec_path = rec_dir / f"{receipt.change_id}.json"
        data = receipt.model_dump(mode="json")
        data_str = json.dumps(data, ensure_ascii=False, indent=2)
        self._sandbox._atomic_write(rec_path, data_str + "\n")


__all__ = ["NovelProjectHistoryService"]
