from __future__ import annotations

import json

import pytest

from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_draft import ChapterDraft
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_document_service import (
    DocumentConflictError,
    NovelDocumentService,
)
from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog


def _workspace(tmp_path):
    project = tmp_path / "novels" / "book"
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps(
            {"project_id": "p1", "db_path": str(project / "novel.db")}
        ),
        encoding="utf-8",
    )
    catalog = NovelWorkspaceCatalog(tmp_path)
    workspace = catalog.require("p1")
    registry = catalog.registry("p1")
    registry.novel_project_store.create(
        NovelProject(project_id="p1", title="测试")
    )
    return workspace, registry


def test_document_save_creates_versions_without_overwriting_history(tmp_path):
    workspace, registry = _workspace(tmp_path)
    service = NovelDocumentService(workspace, registry)

    first = service.save("world", "旧世界观", expected_revision=0)
    second = service.save("world", "新世界观", expected_revision=1)

    assert service.read_version("world", 1).content == "旧世界观"
    assert second.revision == 2
    assert workspace.root.joinpath("world.md").read_text(
        encoding="utf-8"
    ) == "新世界观"
    assert first.content_hash != second.content_hash


def test_stale_expected_revision_is_rejected(tmp_path):
    workspace, registry = _workspace(tmp_path)
    service = NovelDocumentService(workspace, registry)
    service.save("outline", "v1", expected_revision=0)

    with pytest.raises(DocumentConflictError) as error:
        service.save("outline", "冲突内容", expected_revision=0)

    assert error.value.current_revision == 1
    assert service.read("outline").content == "v1"


def test_character_save_updates_only_bound_structured_record(tmp_path):
    workspace, registry = _workspace(tmp_path)
    registry.novel_character_store.save(
        NovelCharacter(
            character_id="c1",
            project_id="p1",
            name="林舟",
            personality="谨慎",
        )
    )
    service = NovelDocumentService(workspace, registry)
    payload = registry.novel_character_store.load("c1").to_dict()
    payload["personality"] = "谨慎，但会在关键处冒险"

    saved = service.save(
        "characters",
        json.dumps(payload, ensure_ascii=False),
        expected_revision=0,
        resource_id="c1",
    )

    assert saved.revision == 1
    assert (
        registry.novel_character_store.load("c1").personality
        == "谨慎，但会在关键处冒险"
    )
    with pytest.raises(ValueError, match="does not belong"):
        service.save(
            "characters",
            json.dumps({**payload, "project_id": "other"}),
            expected_revision=1,
            resource_id="c1",
        )


def test_draft_edit_creates_new_store_and_document_revisions(tmp_path):
    workspace, registry = _workspace(tmp_path)
    registry.novel_chapter_plan_store.save(
        ChapterPlan(
            chapter_id="ch1",
            project_id="p1",
            chapter_index=1,
            title="第一章",
        )
    )
    registry.novel_chapter_draft_store.save(
        ChapterDraft(
            draft_id="draft-ch1-r1",
            chapter_id="ch1",
            revision=1,
            text="旧正文",
            char_count=3,
            status="accepted",
        )
    )
    service = NovelDocumentService(workspace, registry)

    saved = service.save(
        "draft",
        "作者修改后的正文",
        expected_revision=1,
        resource_id="1",
    )

    draft = registry.novel_chapter_draft_store.load_latest("ch1")
    assert saved.revision == 2
    assert draft.revision == 2
    assert draft.text == "作者修改后的正文"
    assert draft.source == "author_edit"
    assert service.read_version("draft", 2, resource_id="1").content == draft.text


@pytest.mark.parametrize(
    "kind,resource_id",
    [
        ("unknown", ""),
        ("draft", "../1"),
        ("characters", ""),
        ("world", "extra"),
    ],
)
def test_document_identifiers_never_become_paths(
    tmp_path, kind, resource_id
):
    workspace, registry = _workspace(tmp_path)
    service = NovelDocumentService(workspace, registry)

    with pytest.raises(ValueError):
        service.read(kind, resource_id=resource_id)

