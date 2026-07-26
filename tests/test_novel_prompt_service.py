from __future__ import annotations

import json

import pytest

from awp_rp_runtime_v3.runtime.novel_document_service import DocumentConflictError
from awp_rp_runtime_v3.runtime.novel_prompt_service import NovelPromptService
from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog


def _workspace(tmp_path):
    project = tmp_path / "novels" / "book"
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps({"project_id": "p1", "db_path": str(project / "novel.db")}),
        encoding="utf-8",
    )
    return NovelWorkspaceCatalog(tmp_path).require("p1")


def test_project_override_does_not_modify_system_prompt(tmp_path):
    service = NovelPromptService(_workspace(tmp_path))
    system = service.resolve("writer")
    content = system.content + "\n\n项目 Writer：服从作者批准的场景。"

    override = service.save_override("writer", content, expected_revision=0)

    assert service.resolve("writer").content == content
    assert service._system_path("writer").read_text(encoding="utf-8") == system.content
    assert override.revision == 1
    with pytest.raises(DocumentConflictError):
        service.save_override("writer", content + "x", expected_revision=0)


def test_running_snapshot_does_not_change_after_prompt_edit(tmp_path):
    service = NovelPromptService(_workspace(tmp_path))
    snapshot = service.snapshot({"editor", "writer", "style_cleaner"})
    writer = service.resolve("writer")
    service.save_override(
        "writer",
        writer.content + "\n作者批准内容高于通用套路。",
        expected_revision=0,
    )

    loaded = service.load_snapshot(snapshot.snapshot_id)

    assert loaded.hashes == snapshot.hashes
    assert loaded.contents == snapshot.contents
    assert loaded.hashes["writer"] != service.resolve("writer").content_hash


def test_writer_override_cannot_remove_author_contract(tmp_path):
    service = NovelPromptService(_workspace(tmp_path))

    with pytest.raises(ValueError, match="author-approved contract"):
        service.save_override("writer", "只管自由发挥。", expected_revision=0)


def test_restore_creates_a_new_revision(tmp_path):
    service = NovelPromptService(_workspace(tmp_path))
    editor = service.resolve("editor")
    first = service.save_override("editor", "项目编辑 v1", 0)
    service.save_override("editor", "项目编辑 v2", 1)

    restored = service.restore("editor", first.revision, 2)

    assert restored.revision == 3
    assert restored.content == "项目编辑 v1"
    assert service.diff("editor", 0)
    assert editor.source == "system"
