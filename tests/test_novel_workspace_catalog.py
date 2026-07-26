from __future__ import annotations

import json

import pytest

from awp_rp_runtime_v3.runtime.novel_workspace_catalog import NovelWorkspaceCatalog


def _write_state(project, *, project_id: str, db_path: str) -> None:
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps({"project_id": project_id, "db_path": db_path}),
        encoding="utf-8",
    )


def test_catalog_discovers_only_bound_novel_directories(tmp_path):
    project = tmp_path / "novels" / "book"
    db_path = project / "novel.db"
    _write_state(project, project_id="book-1", db_path=str(db_path))

    catalog = NovelWorkspaceCatalog(tmp_path)
    workspace = catalog.require("book-1")

    assert workspace.root == project.resolve()
    assert workspace.db_path == db_path.resolve()
    assert workspace.state["project_id"] == "book-1"


def test_catalog_rejects_db_path_outside_project(tmp_path):
    project = tmp_path / "novels" / "book"
    _write_state(
        project,
        project_id="book-1",
        db_path=str(tmp_path / "outside.db"),
    )

    with pytest.raises(ValueError, match="database escaped project root"):
        NovelWorkspaceCatalog(tmp_path).list()


def test_catalog_rejects_duplicate_project_ids(tmp_path):
    for name in ("one", "two"):
        project = tmp_path / "novels" / name
        _write_state(
            project,
            project_id="duplicate",
            db_path=str(project / "novel.db"),
        )

    with pytest.raises(ValueError, match="duplicate novel project id"):
        NovelWorkspaceCatalog(tmp_path).list()


def test_catalog_missing_project_does_not_accept_a_path(tmp_path):
    catalog = NovelWorkspaceCatalog(tmp_path)

    with pytest.raises(KeyError, match="workspace not found"):
        catalog.require("../../outside")
