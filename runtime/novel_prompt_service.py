"""Project prompt overrides, immutable versions, diffs, and run snapshots."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ..contracts.novel_prompt_version import (
    NovelPromptSnapshot,
    NovelPromptVersion,
    ResolvedPrompt,
)
from .novel_document_service import DocumentConflictError
from .novel_workspace_catalog import NovelWorkspace

PROMPT_ROLES = (
    "editor",
    "architect",
    "director",
    "writer",
    "npc_planner",
    "continuity_checker",
    "style_cleaner",
    "ledger_curator",
)
_LOCKS: dict[str, threading.RLock] = {}
_LOCK_GUARD = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NovelPromptService:
    def __init__(
        self,
        workspace: NovelWorkspace,
        *,
        resources_root: Path | None = None,
    ):
        self.workspace = workspace
        self.resources_root = (
            Path(resources_root).resolve()
            if resources_root is not None
            else (
                Path(__file__).resolve().parent.parent
                / "agent_harness"
                / "resources"
            ).resolve()
        )
        self.current_root = workspace.root / ".awp" / "prompts"
        self.version_root = (
            workspace.root / ".awp" / "versions" / "prompts"
        )
        self.snapshot_root = (
            workspace.root / ".awp" / "prompt-snapshots"
        )
        for path in (
            self.current_root,
            self.version_root,
            self.snapshot_root,
        ):
            path.mkdir(parents=True, exist_ok=True)
        with _LOCK_GUARD:
            self._lock = _LOCKS.setdefault(
                str(workspace.root), threading.RLock()
            )

    def list_roles(self) -> list[ResolvedPrompt]:
        return [self.resolve(role) for role in PROMPT_ROLES]

    def resolve(self, role: str) -> ResolvedPrompt:
        self._validate_role(role)
        versions = self.list_versions(role)
        if versions:
            latest = versions[0]
            return ResolvedPrompt(**latest.model_dump(exclude={"created_at"}))
        content = self._system_path(role).read_text(encoding="utf-8")
        return ResolvedPrompt(
            role=role,
            content=content,
            source="system",
            revision=0,
            content_hash=self._hash(content),
        )

    def save_override(
        self, role: str, content: str, expected_revision: int
    ) -> NovelPromptVersion:
        self._validate_content(role, content)
        with self._lock:
            current = self.resolve(role)
            if current.revision != expected_revision:
                raise DocumentConflictError(current.revision)
            revision = current.revision + 1
            version = NovelPromptVersion(
                role=role,
                content=content,
                source="project",
                revision=revision,
                content_hash=self._hash(content),
                created_at=_now(),
            )
            version_path = self._version_path(role, revision)
            if version_path.exists():
                raise ValueError("prompt version already exists")
            self._atomic_text(self.current_root / f"{role}.md", content)
            self._atomic_json(
                version_path, version.model_dump(mode="json")
            )
            return version

    def list_versions(self, role: str) -> list[NovelPromptVersion]:
        self._validate_role(role)
        directory = self.version_root / role
        versions = []
        if directory.is_dir():
            for path in directory.glob("v[0-9][0-9][0-9][0-9][0-9][0-9].json"):
                versions.append(
                    NovelPromptVersion.model_validate_json(
                        path.read_text(encoding="utf-8")
                    )
                )
        return sorted(
            versions, key=lambda item: item.revision, reverse=True
        )

    def read_version(self, role: str, revision: int) -> NovelPromptVersion:
        self._validate_role(role)
        path = self._version_path(role, revision)
        if not path.is_file():
            raise FileNotFoundError("prompt version not found")
        return NovelPromptVersion.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def restore(
        self, role: str, revision: int, expected_revision: int
    ) -> NovelPromptVersion:
        content = (
            self._system_path(role).read_text(encoding="utf-8")
            if revision == 0
            else self.read_version(role, revision).content
        )
        return self.save_override(role, content, expected_revision)

    def diff(self, role: str, revision: int | None = None) -> str:
        current = self.resolve(role)
        base = (
            self._system_path(role).read_text(encoding="utf-8")
            if revision is None or revision == 0
            else self.read_version(role, revision).content
        )
        return "".join(
            difflib.unified_diff(
                base.splitlines(keepends=True),
                current.content.splitlines(keepends=True),
                fromfile=f"{role}:base",
                tofile=f"{role}:current",
            )
        )

    def snapshot(self, roles: Iterable[str]) -> NovelPromptSnapshot:
        selected = sorted(set(roles))
        if not selected:
            raise ValueError("prompt snapshot requires at least one role")
        resolved = {role: self.resolve(role) for role in selected}
        snapshot = NovelPromptSnapshot(
            snapshot_id=f"prompt-{uuid.uuid4().hex}",
            versions={
                role: f"{prompt.source}:v{prompt.revision}"
                for role, prompt in resolved.items()
            },
            hashes={
                role: prompt.content_hash
                for role, prompt in resolved.items()
            },
            contents={
                role: prompt.content for role, prompt in resolved.items()
            },
            created_at=_now(),
        )
        self._atomic_json(
            self.snapshot_root / f"{snapshot.snapshot_id}.json",
            snapshot.model_dump(mode="json"),
        )
        return snapshot

    def load_snapshot(self, snapshot_id: str) -> NovelPromptSnapshot:
        if (
            not snapshot_id.startswith("prompt-")
            or len(snapshot_id) > 80
            or not snapshot_id[7:].isalnum()
        ):
            raise ValueError("invalid prompt snapshot id")
        path = self.snapshot_root / f"{snapshot_id}.json"
        if not path.is_file():
            raise FileNotFoundError("prompt snapshot not found")
        return NovelPromptSnapshot.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def _system_path(self, role: str) -> Path:
        path = (
            self.resources_root / "system-prompt.md"
            if role == "editor"
            else self.resources_root / "roles" / role / "system-prompt.md"
        )
        if not path.is_file():
            raise FileNotFoundError(f"system prompt not found for role: {role}")
        return path

    @staticmethod
    def _validate_role(role: str) -> None:
        if role not in PROMPT_ROLES:
            raise ValueError("unknown prompt role")

    def _validate_content(self, role: str, content: str) -> None:
        self._validate_role(role)
        if not content.strip():
            raise ValueError("prompt content cannot be empty")
        if len(content) > 100_000:
            raise ValueError("prompt content exceeds 100000 characters")
        if role == "writer" and not any(
            marker in content
            for marker in (
                "writer contract",
                "AUTHOR-APPROVED",
                "作者批准",
                "作者确认",
            )
        ):
            raise ValueError(
                "Writer prompt must preserve the author-approved contract"
            )

    def _version_path(self, role: str, revision: int) -> Path:
        return self.version_root / role / f"v{revision:06d}.json"

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _atomic_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)

    @staticmethod
    def _atomic_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)


__all__ = ["NovelPromptService", "PROMPT_ROLES"]
