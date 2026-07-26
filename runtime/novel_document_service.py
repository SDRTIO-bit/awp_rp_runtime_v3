"""Allowlisted, immutable versions for novel project documents."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..contracts.novel_character import NovelCharacter
from ..contracts.novel_document import (
    NovelDocumentKind,
    NovelDocumentVersion,
)
from ..contracts.novel_draft import ChapterDraft
from .novel_workspace_catalog import NovelWorkspace
from .session_runtime_registry import SessionRuntimeStoreRegistry

_KINDS = {"outline", "world", "characters", "draft"}
_RESOURCE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_CHAPTER_ID = re.compile(r"[1-9][0-9]*")
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocumentConflictError(RuntimeError):
    def __init__(self, current_revision: int):
        super().__init__(
            f"document revision conflict; current revision is {current_revision}"
        )
        self.current_revision = current_revision


class NovelDocumentService:
    """Maps browser document IDs to fixed project files and structured stores."""

    def __init__(
        self,
        workspace: NovelWorkspace,
        registry: SessionRuntimeStoreRegistry,
    ):
        self.workspace = workspace
        self.registry = registry
        self.root = workspace.root / ".awp" / "versions" / "documents"
        self.root.mkdir(parents=True, exist_ok=True)
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(
                str(workspace.root), threading.RLock()
            )

    def read(
        self,
        kind: NovelDocumentKind | str,
        resource_id: str = "",
    ) -> NovelDocumentVersion:
        parsed_kind, parsed_resource = self._validate_identity(
            kind, resource_id
        )
        with self._lock:
            versions = self.list_versions(parsed_kind, parsed_resource)
            if versions:
                return versions[0]
            content, revision, source = self._read_canonical(
                parsed_kind, parsed_resource
            )
            return self._version(
                parsed_kind,
                parsed_resource,
                revision,
                content,
                source,
            )

    def save(
        self,
        kind: NovelDocumentKind | str,
        content: str,
        expected_revision: int,
        resource_id: str = "",
        source: str = "author",
    ) -> NovelDocumentVersion:
        parsed_kind, parsed_resource = self._validate_identity(
            kind, resource_id
        )
        if not isinstance(content, str):
            raise TypeError("document content must be text")
        if len(content) > 2_000_000:
            raise ValueError("document content is too large")
        if expected_revision < 0:
            raise ValueError("expected revision cannot be negative")
        with self._lock:
            current = self.read(parsed_kind, parsed_resource)
            if current.revision != expected_revision:
                raise DocumentConflictError(current.revision)
            revision = current.revision + 1
            effective_source = (
                "author_edit" if parsed_kind == "draft" else source
            )
            version = self._version(
                parsed_kind,
                parsed_resource,
                revision,
                content,
                effective_source,
            )
            version_path = self._version_path(
                parsed_kind, parsed_resource, revision
            )
            if version_path.exists():
                raise ValueError("document version already exists")
            self._write_canonical(version)
            self._atomic_json(
                version_path,
                version.model_dump(mode="json"),
            )
            return version

    def list_versions(
        self,
        kind: NovelDocumentKind | str,
        resource_id: str = "",
    ) -> list[NovelDocumentVersion]:
        parsed_kind, parsed_resource = self._validate_identity(
            kind, resource_id
        )
        directory = self._resource_dir(parsed_kind, parsed_resource)
        versions: list[NovelDocumentVersion] = []
        if directory.is_dir():
            for path in directory.glob("v[0-9][0-9][0-9][0-9][0-9][0-9].json"):
                try:
                    version = NovelDocumentVersion.model_validate_json(
                        path.read_text(encoding="utf-8")
                    )
                except Exception as exc:
                    raise ValueError(
                        f"invalid document version: {path.name}"
                    ) from exc
                if (
                    version.kind != parsed_kind
                    or version.resource_id != parsed_resource
                ):
                    raise ValueError("document version identity mismatch")
                versions.append(version)
        return sorted(
            versions, key=lambda item: item.revision, reverse=True
        )

    def read_version(
        self,
        kind: NovelDocumentKind | str,
        revision: int,
        resource_id: str = "",
    ) -> NovelDocumentVersion:
        parsed_kind, parsed_resource = self._validate_identity(
            kind, resource_id
        )
        if revision < 1:
            raise ValueError("stored document revision must be positive")
        path = self._version_path(
            parsed_kind, parsed_resource, revision
        )
        if not path.is_file():
            raise FileNotFoundError("document version not found")
        version = NovelDocumentVersion.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if (
            version.kind != parsed_kind
            or version.resource_id != parsed_resource
            or version.revision != revision
        ):
            raise ValueError("document version identity mismatch")
        return version

    def _read_canonical(
        self, kind: str, resource_id: str
    ) -> tuple[str, int, str]:
        if kind in {"outline", "world"}:
            path = self.workspace.root / f"{kind}.md"
            content = (
                path.read_text(encoding="utf-8")
                if path.is_file()
                else ""
            )
            return content, 0, "project_file"
        if kind == "characters":
            character = self.registry.novel_character_store.load(resource_id)
            if (
                character is None
                or character.project_id != self.workspace.project_id
            ):
                raise FileNotFoundError("character document not found")
            return (
                json.dumps(
                    character.to_dict(), ensure_ascii=False, indent=2
                ),
                0,
                "structured_store",
            )
        plan = self.registry.novel_chapter_plan_store.load_by_index(
            self.workspace.project_id, int(resource_id)
        )
        if plan is None:
            raise FileNotFoundError("chapter plan not found")
        draft = self.registry.novel_chapter_draft_store.load_latest(
            plan.chapter_id
        )
        if draft is None:
            return "", 0, "writer"
        return draft.text, draft.revision, draft.source

    def _write_canonical(self, version: NovelDocumentVersion) -> None:
        if version.kind in {"outline", "world"}:
            self._atomic_text(
                self.workspace.root / f"{version.kind}.md",
                version.content,
            )
            return
        if version.kind == "characters":
            try:
                payload = json.loads(version.content)
            except json.JSONDecodeError as exc:
                raise ValueError("character content must be valid JSON") from exc
            if not isinstance(payload, dict):
                raise ValueError("character content must be a JSON object")
            character = NovelCharacter.from_dict(payload)
            if (
                character.character_id != version.resource_id
                or character.project_id != self.workspace.project_id
            ):
                raise ValueError("character document does not belong to project")
            self.registry.novel_character_store.save(character)
            return
        chapter_index = int(version.resource_id)
        plan = self.registry.novel_chapter_plan_store.load_by_index(
            self.workspace.project_id, chapter_index
        )
        if plan is None:
            raise FileNotFoundError("chapter plan not found")
        previous = self.registry.novel_chapter_draft_store.load_latest(
            plan.chapter_id
        )
        draft = ChapterDraft(
            draft_id=f"draft-{plan.chapter_id}-r{version.revision}",
            chapter_id=plan.chapter_id,
            revision=version.revision,
            source_plan_revision=(
                previous.source_plan_revision if previous else 1
            ),
            text=version.content,
            raw_text=version.content,
            char_count=len(version.content),
            status="accepted",
            source="author_edit",
            quality_decision_id=(
                previous.quality_decision_id if previous else ""
            ),
            quality_annotations=(
                previous.quality_annotations if previous else ()
            ),
            created_at=version.created_at,
        )
        self.registry.novel_chapter_draft_store.save(draft)

    def _validate_identity(
        self, kind: str, resource_id: str
    ) -> tuple[str, str]:
        if kind not in _KINDS:
            raise ValueError("unknown document kind")
        if kind in {"outline", "world"}:
            if resource_id:
                raise ValueError(f"{kind} does not accept a resource id")
            return kind, ""
        if not resource_id:
            raise ValueError(f"{kind} requires a resource id")
        pattern = _CHAPTER_ID if kind == "draft" else _RESOURCE_ID
        if pattern.fullmatch(resource_id) is None:
            raise ValueError("invalid document resource id")
        return kind, resource_id

    def _resource_dir(self, kind: str, resource_id: str) -> Path:
        selected = resource_id or "project"
        return self.root / kind / selected

    def _version_path(
        self, kind: str, resource_id: str, revision: int
    ) -> Path:
        return (
            self._resource_dir(kind, resource_id)
            / f"v{revision:06d}.json"
        )

    def _version(
        self,
        kind: str,
        resource_id: str,
        revision: int,
        content: str,
        source: str,
    ) -> NovelDocumentVersion:
        return NovelDocumentVersion(
            document_id=f"{kind}:{resource_id or 'project'}",
            kind=kind,
            resource_id=resource_id,
            revision=revision,
            content=content,
            content_hash=hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest(),
            source=source,
            created_at=_now(),
        )

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

    @staticmethod
    def _atomic_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)


__all__ = [
    "DocumentConflictError",
    "NovelDocumentService",
]
