"""Project-root filesystem sandbox for the dedicated novel editor."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Any, Iterator

from ..contracts.novel_tool_approval import ToolApprovalRequest


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

    def classify(
        self, name: str, args: dict[str, Any]
    ) -> ToolApprovalRequest:
        targets: list[str] = []
        risk = "hard_deny"
        summary = f"拒绝未知工具 {name}"
        reason = "unknown project tool"
        if name in {"read", "ls", "find", "grep"}:
            raw = str(args.get("path", ".") or ".")
            targets = [raw]
            try:
                self.resolve_relative(raw)
            except ValueError as exc:
                reason = str(exc)
            else:
                risk = "read"
                summary = f"{name} {raw}"
                reason = "project-local read"
        elif name in {"write", "edit"}:
            raw = str(args.get("path", "") or "")
            targets = [raw]
            try:
                path = self.resolve_relative(raw, write=True)
            except ValueError as exc:
                reason = str(exc)
                summary = f"拒绝修改 {raw or '(missing path)'}"
            else:
                relative = path.relative_to(self.root).as_posix()
                content_size = len(
                    str(args.get("content", "")).encode("utf-8")
                )
                important = (
                    relative.startswith("output/chapter_")
                    and relative.endswith(".md")
                ) or content_size > 100_000
                risk = "important" if important else "write"
                summary = f"{'修改' if name == 'edit' else '写入'} {relative}"
                reason = (
                    "chapter output or large replacement requires author approval"
                    if important
                    else "ordinary project text mutation"
                )
                targets = [relative]
        elif name == "bash":
            command = str(args.get("command", "") or "").strip()
            if command in {"pwd", "Get-Location"}:
                risk = "read"
                summary = "显示小说项目工作目录"
                reason = "fixed project-local command"
            elif re.search(
                r"(?i)\b(curl|wget|invoke-webrequest|iwr|ssh|scp|npm|pip|"
                r"winget|choco)\b|https?://",
                command,
            ):
                summary = "拒绝网络或包管理命令"
                reason = "network and package commands are outside the novel sandbox"
            else:
                summary = "拒绝无法静态证明安全的终端命令"
                reason = "ambiguous shell command cannot be proven project-local"
        return ToolApprovalRequest.create(
            tool=name,
            risk=risk,
            summary=summary,
            targets=targets,
            reason=reason,
            arguments=args,
        )

    def execute_write(self, name: str, args: dict[str, Any]) -> str:
        if name == "write":
            return self._write(args)
        if name == "edit":
            return self._edit(args)
        if name == "bash":
            command = str(args.get("command", "") or "").strip()
            if command not in {"pwd", "Get-Location"}:
                raise ValueError(
                    "shell command is not permitted by the novel sandbox"
                )
            return "."
        raise ValueError(f"unsupported project write tool: {name}")

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

    def _write(self, args: dict[str, Any]) -> str:
        raw = self._required_path(args)
        content = args.get("content")
        if not isinstance(content, str):
            raise ValueError("content must be text")
        if len(content.encode("utf-8")) > self.MAX_READ_BYTES:
            raise ValueError("project write exceeds text size limit")
        path = self.resolve_relative(raw, write=True)
        self._check_expected_hash(path, args.get("expected_hash"))
        if path.exists():
            self._backup(path)
        self._atomic_write(path, content)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        relative = path.relative_to(self.root).as_posix()
        self._audit("write", relative, digest)
        return f"wrote: {relative}\nsha256: {digest}"

    def _edit(self, args: dict[str, Any]) -> str:
        raw = self._required_path(args)
        path = self.resolve_relative(raw, write=True)
        if not path.is_file():
            raise ValueError(f"project file not found: {raw}")
        self._check_expected_hash(path, args.get("expected_hash"))
        edits = args.get("edits")
        if not isinstance(edits, list) or not edits or len(edits) > 100:
            raise ValueError("edits must contain 1-100 exact replacements")
        original = self._read_text(path)
        updated = original
        for edit in edits:
            if not isinstance(edit, dict):
                raise ValueError("each edit must be an object")
            old = edit.get("oldText")
            new = edit.get("newText")
            if not isinstance(old, str) or not old:
                raise ValueError("oldText must be non-empty text")
            if not isinstance(new, str):
                raise ValueError("newText must be text")
            if original.count(old) != 1:
                raise ValueError("oldText must occur exactly once")
            updated = updated.replace(old, new, 1)
        if updated == original:
            raise ValueError("edit did not change the project file")
        if len(updated.encode("utf-8")) > self.MAX_READ_BYTES:
            raise ValueError("edited project file exceeds text size limit")
        self._backup(path)
        self._atomic_write(path, updated)
        digest = hashlib.sha256(updated.encode("utf-8")).hexdigest()
        relative = path.relative_to(self.root).as_posix()
        self._audit("edit", relative, digest)
        return f"edited: {relative}\nsha256: {digest}"

    def _check_expected_hash(self, path: Path, expected: Any) -> None:
        if expected in (None, ""):
            return
        if not isinstance(expected, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected
        ):
            raise ValueError("expected_hash must be a sha256 hex digest")
        if not path.is_file():
            raise ValueError("project file changed since it was read")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("project file changed since it was read")

    def _backup(self, path: Path) -> None:
        relative = path.relative_to(self.root).as_posix()
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        safe_name = relative.replace("/", "__").replace("\\", "__")
        directory = self.root / ".awp" / "file-history" / safe_name
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "path": relative,
            "sha256": digest,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "content": data.decode("utf-8"),
        }
        self._atomic_write(
            directory / f"{timestamp}-{digest[:12]}.json",
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    def _audit(self, tool: str, relative: str, digest: str) -> None:
        directory = self.root / ".awp" / "tool-audit"
        directory.mkdir(parents=True, exist_ok=True)
        event = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "target": relative,
            "sha256": digest,
        }
        path = directory / "events.jsonl"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(
                descriptor, "w", encoding="utf-8", newline="\n"
            ) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

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
        if len(parts) >= 2 and parts[0] == "agent" and parts[1] == "skills":
            raise ValueError("project skill path is protected")
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
