"""Project-root filesystem sandbox for the dedicated novel editor."""

from __future__ import annotations

import fnmatch
import hashlib
import re
from pathlib import Path, PurePath
from typing import Any, Iterator


class NovelProjectSandbox:
    """Read novel project text without allowing path or link escapes."""

    MAX_READ_BYTES = 2 * 1024 * 1024
    MAX_READ_LINES = 2_000
    MAX_RESULTS = 200
    _INTERNAL_SEARCH_DIRS = frozenset(
        {
            "file-history",
            "pi-sessions",
            "tool-audit",
            "tool-approvals",
            "trash",
        }
    )

    def __init__(self, project_root: str | Path):
        root = Path(project_root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("novel project root must be a directory")
        self.root = root

    def resolve_relative(self, raw: str, *, write: bool = False) -> Path:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("project path must be a non-empty relative path")
        normalized = raw.strip().replace("\\", "/")
        path = Path(normalized)
        if path.is_absolute() or path.drive or normalized.startswith("//"):
            raise ValueError("project path must be relative")
        parts = PurePath(normalized).parts
        if any(part == ".." for part in parts):
            raise ValueError("project path escaped project root")
        candidate = self.root.joinpath(*parts)
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("project path escaped project root") from exc
        if write:
            self._reject_protected(resolved)
        return resolved

    def content_hash(self, raw: str) -> str:
        path = self.resolve_relative(raw)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def execute_read(self, name: str, args: dict[str, Any]) -> str:
        if name == "read":
            return self._read(args)
        if name == "ls":
            return self._list(args)
        if name == "find":
            return self._find(args)
        if name == "grep":
            return self._grep(args)
        raise ValueError(f"unsupported project read tool: {name}")

    def _read(self, args: dict[str, Any]) -> str:
        raw = self._required_path(args)
        path = self.resolve_relative(raw)
        if not path.is_file():
            raise ValueError(f"project file not found: {raw}")
        data = self._read_text(path)
        lines = data.splitlines()
        offset = self._bounded_int(args.get("offset", 1), "offset", 1, 10_000_000)
        limit = self._bounded_int(
            args.get("limit", self.MAX_READ_LINES),
            "limit",
            1,
            self.MAX_READ_LINES,
        )
        selected = lines[offset - 1 : offset - 1 + limit]
        body = "\n".join(
            f"{line_number}: {line}"
            for line_number, line in enumerate(selected, start=offset)
        )
        relative = path.relative_to(self.root).as_posix()
        digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
        header = f"path: {relative}\nsha256: {digest}\n"
        if offset - 1 + len(selected) < len(lines):
            return f"{header}{body}\n... ({len(lines)} lines total)"
        return f"{header}{body}"

    def _list(self, args: dict[str, Any]) -> str:
        raw = str(args.get("path", ".") or ".")
        path = self.resolve_relative(raw)
        if not path.is_dir():
            raise ValueError(f"project directory not found: {raw}")
        limit = self._bounded_int(
            args.get("limit", self.MAX_RESULTS),
            "limit",
            1,
            self.MAX_RESULTS,
        )
        entries: list[str] = []
        for child in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
            if self._skip_search_path(child):
                continue
            resolved = self._safe_resolved(child)
            suffix = "/" if resolved.is_dir() else ""
            entries.append(
                f"{resolved.relative_to(self.root).as_posix()}{suffix}"
            )
            if len(entries) >= limit:
                break
        return "\n".join(entries) or "(empty directory)"

    def _find(self, args: dict[str, Any]) -> str:
        pattern = str(args.get("pattern", "") or "")
        if not pattern or len(pattern) > 500:
            raise ValueError("find pattern must contain 1-500 characters")
        raw = str(args.get("path", ".") or ".")
        base = self.resolve_relative(raw)
        if not base.is_dir():
            raise ValueError(f"project directory not found: {raw}")
        limit = self._bounded_int(
            args.get("limit", self.MAX_RESULTS),
            "limit",
            1,
            self.MAX_RESULTS,
        )
        matches: list[str] = []
        for path in self._walk(base):
            relative = path.relative_to(self.root).as_posix()
            if fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(
                path.name, pattern
            ):
                matches.append(relative)
                if len(matches) >= limit:
                    break
        return "\n".join(matches) or "(no matches)"

    def _grep(self, args: dict[str, Any]) -> str:
        pattern = str(args.get("pattern", "") or "")
        if not pattern or len(pattern) > 1_000:
            raise ValueError("grep pattern must contain 1-1000 characters")
        flags = re.IGNORECASE if bool(args.get("ignoreCase", False)) else 0
        expression = re.compile(
            re.escape(pattern) if bool(args.get("literal", False)) else pattern,
            flags,
        )
        raw = str(args.get("path", ".") or ".")
        target = self.resolve_relative(raw)
        glob = str(args.get("glob", "") or "")
        limit = self._bounded_int(
            args.get("limit", self.MAX_RESULTS),
            "limit",
            1,
            self.MAX_RESULTS,
        )
        matches: list[str] = []
        paths = [target] if target.is_file() else self._walk(target)
        for path in paths:
            if glob and not (
                fnmatch.fnmatch(path.name, glob)
                or fnmatch.fnmatch(path.relative_to(self.root).as_posix(), glob)
            ):
                continue
            try:
                text = self._read_text(path)
            except (UnicodeDecodeError, ValueError, OSError):
                continue
            relative = path.relative_to(self.root).as_posix()
            for line_number, line in enumerate(text.splitlines(), start=1):
                if expression.search(line):
                    matches.append(f"{relative}:{line_number}:{line[:500]}")
                    if len(matches) >= limit:
                        return "\n".join(matches)
        return "\n".join(matches) or "(no matches)"

    def _walk(self, base: Path) -> Iterator[Path]:
        if not base.is_dir():
            return
        for path in base.rglob("*"):
            if self._skip_search_path(path):
                continue
            try:
                resolved = self._safe_resolved(path)
            except ValueError:
                continue
            if resolved.is_file():
                yield resolved

    def _safe_resolved(self, path: Path) -> Path:
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("project path escaped project root") from exc
        return resolved

    def _skip_search_path(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            return True
        parts = relative.parts
        if path.name == ".novel_cli.json" or path.name.startswith("novel.db"):
            return True
        return (
            len(parts) >= 2
            and parts[0] == ".awp"
            and parts[1] in self._INTERNAL_SEARCH_DIRS
        )

    def _reject_protected(self, path: Path) -> None:
        relative = path.relative_to(self.root)
        parts = relative.parts
        if not parts:
            raise ValueError("project root is protected")
        if parts[0] == ".awp":
            raise ValueError("project runtime path is protected")
        if parts[0] == ".novel_cli.json" or parts[0].startswith("novel.db"):
            raise ValueError("project database or binding file is protected")

    def _read_text(self, path: Path) -> str:
        if not path.is_file():
            raise ValueError("target is not a project file")
        size = path.stat().st_size
        if size > self.MAX_READ_BYTES:
            raise ValueError(
                f"project file exceeds {self.MAX_READ_BYTES} byte read limit"
            )
        data = path.read_bytes()
        if b"\0" in data:
            raise ValueError("binary project file is not readable by this tool")
        return data.decode("utf-8")

    @staticmethod
    def _required_path(args: dict[str, Any]) -> str:
        raw = args.get("path")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("path is required")
        return raw

    @staticmethod
    def _bounded_int(value: Any, name: str, minimum: int, maximum: int) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be an integer")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be an integer") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
        return parsed


__all__ = ["NovelProjectSandbox"]
