"""Repository-local discovery and binding for novel workspaces."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from ..storage.sqlite.database import Database
from .session_runtime_registry import SessionRuntimeStoreRegistry


@dataclass(frozen=True)
class NovelWorkspace:
    """One trusted project root and its bound SQLite database."""

    project_id: str
    root: Path
    db_path: Path
    state: Mapping[str, Any]


class NovelWorkspaceCatalog:
    """Discover projects only from ``novels/*/.novel_cli.json``."""

    def __init__(self, repository_root: str | Path):
        self.repository_root = Path(repository_root).resolve()
        self.novels_root = (self.repository_root / "novels").resolve()
        self._lock = threading.RLock()
        self._registries: dict[
            tuple[int, str], SessionRuntimeStoreRegistry
        ] = {}

    def list(self) -> list[NovelWorkspace]:
        if not self.novels_root.is_dir():
            return []
        workspaces = [
            self._load(path)
            for path in self.novels_root.glob("*/.novel_cli.json")
            if path.is_file()
        ]
        ids = [workspace.project_id for workspace in workspaces]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate novel project id")
        return sorted(workspaces, key=lambda item: item.project_id)

    def require(self, project_id: str) -> NovelWorkspace:
        for workspace in self.list():
            if workspace.project_id == project_id:
                return workspace
        raise KeyError(f"novel workspace not found: {project_id}")

    def registry(self, project_id: str) -> SessionRuntimeStoreRegistry:
        workspace = self.require(project_id)
        key = (threading.get_ident(), project_id)
        with self._lock:
            registry = self._registries.get(key)
            if registry is None:
                database = Database(workspace.db_path)
                database.initialize()
                registry = SessionRuntimeStoreRegistry(database)
                self._registries[key] = registry
            return registry

    def close(self) -> None:
        with self._lock:
            for registry in self._registries.values():
                registry.db.close()
            self._registries.clear()

    def _load(self, state_path: Path) -> NovelWorkspace:
        project_root = state_path.parent.resolve()
        self._require_within(project_root, self.novels_root, "project escaped novels root")
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid novel workspace state: {state_path.name}") from exc
        if not isinstance(raw, dict):
            raise ValueError("invalid novel workspace state")
        project_id = raw.get("project_id")
        db_value = raw.get("db_path")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("novel workspace project_id is required")
        if not isinstance(db_value, str) or not db_value.strip():
            raise ValueError("novel workspace db_path is required")
        database = Path(db_value)
        if not database.is_absolute():
            database = project_root / database
        database = database.resolve()
        self._require_within(database, project_root, "database escaped project root")

        novel_dir = raw.get("novel_dir")
        if isinstance(novel_dir, str) and novel_dir.strip():
            configured_root = Path(novel_dir).resolve()
            if configured_root != project_root:
                raise ValueError("configured novel root does not match workspace")

        state = dict(raw)
        state["project_id"] = project_id
        state["db_path"] = str(database)
        state["novel_dir"] = str(project_root)
        return NovelWorkspace(
            project_id=project_id,
            root=project_root,
            db_path=database,
            state=MappingProxyType(state),
        )

    @staticmethod
    def _require_within(path: Path, root: Path, message: str) -> None:
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(message) from exc


__all__ = ["NovelWorkspace", "NovelWorkspaceCatalog"]
