"""Test the project context service: bounded file discovery and reference materialization."""

from __future__ import annotations

import pytest

from awp_rp_runtime_v3.runtime.novel_project_context_service import (
    NovelProjectContextService,
)


def test_materialize_references_is_bounded_and_project_local(tmp_path):
    (tmp_path / "outline.md").write_text("第三章", encoding="utf-8")
    service = NovelProjectContextService(tmp_path)
    materialized = service.materialize([{"path": "outline.md"}])
    assert materialized.references[0].path == "outline.md"
    assert materialized.references[0].sha256
    assert "第三章" in materialized.prompt_context
    with pytest.raises(ValueError, match="invalid reference|escaped|relative"):
        service.materialize([{"path": "../outside.md"}])


def test_materialize_rejects_too_many_references(tmp_path):
    (tmp_path / "f.md").write_text("x", encoding="utf-8")
    service = NovelProjectContextService(tmp_path)
    refs = [{"path": "f.md"}] * 13  # max is 12
    with pytest.raises(ValueError, match="12"):
        service.materialize(refs)


def test_materialize_rejects_binary_files(tmp_path):
    (tmp_path / "img.png").write_bytes(b"\x89PNG\x0d\x0a")
    service = NovelProjectContextService(tmp_path)
    with pytest.raises(ValueError, match="binary|utf-8|img"):
        service.materialize([{"path": "img.png"}])


def test_materialize_rejects_missing_file(tmp_path):
    service = NovelProjectContextService(tmp_path)
    with pytest.raises(ValueError, match="not found"):
        service.materialize([{"path": "missing.md"}])


def test_materialize_rejects_protected_path(tmp_path):
    (tmp_path / ".awp").mkdir(exist_ok=True)
    (tmp_path / ".awp" / "authoring").mkdir(exist_ok=True)
    (tmp_path / ".awp" / "authoring" / "secret.md").write_text("secret", encoding="utf-8")
    service = NovelProjectContextService(tmp_path)
    with pytest.raises((ValueError, Exception), match=r"protected|relative|dot"):
        service.materialize([{"path": ".awp/authoring/secret.md"}])


def test_list_files_excludes_dot_awp(tmp_path):
    (tmp_path / ".awp").mkdir(exist_ok=True)
    (tmp_path / ".awp" / "internal.md").write_text("x", encoding="utf-8")
    (tmp_path / "visible.md").write_text("hello", encoding="utf-8")
    service = NovelProjectContextService(tmp_path)
    files = service.list_files()
    assert "visible.md" in files
    assert ".awp/internal.md" not in files


def test_list_files_returns_posix_relative_paths(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "notes.md").write_text("x", encoding="utf-8")
    service = NovelProjectContextService(tmp_path)
    files = service.list_files()
    for f in files:
        assert "\\" not in f
        assert not f.startswith("/")


def test_list_files_query_filter(tmp_path):
    (tmp_path / "outline.md").write_text("x", encoding="utf-8")
    (tmp_path / "characters.md").write_text("x", encoding="utf-8")
    service = NovelProjectContextService(tmp_path)
    files = service.list_files(query="out")
    assert "outline.md" in files
    assert "characters.md" not in files
