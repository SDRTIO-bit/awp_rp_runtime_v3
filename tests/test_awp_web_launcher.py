from __future__ import annotations

import json
import pytest
from awp_rp_runtime_v3.scripts.awp_web_launcher import LauncherError, WebLauncher


def _repository(tmp_path):
    project = tmp_path / "novels" / "daily_high_school"
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps({"project_id": "daily-high-school", "db_path": str(project / "novel.db")}),
        encoding="utf-8",
    )
    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    (tmp_path / "frontend" / "dist" / "index.html").write_text("ok")
    (tmp_path / "agent_harness" / "node_modules" / "@earendil-works" / "pi-coding-agent").mkdir(parents=True)
    return tmp_path


def test_launcher_reuses_healthy_server_and_opens_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _: "node")
    opened = []
    launcher = WebLauncher(repository_root=_repository(tmp_path), health_probe=lambda: True, browser_open=opened.append)
    result = launcher.start("daily_high_school")
    assert result.started_process is False
    assert opened == ["http://127.0.0.1:8188/awp/novels/daily-high-school/workspace/book"]


def test_launcher_reuses_healthy_server_and_opens_project_list(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _: "node")
    opened = []
    launcher = WebLauncher(repository_root=_repository(tmp_path), health_probe=lambda: True, browser_open=opened.append)

    result = launcher.start(open_project_list=True)

    assert result.started_process is False
    assert opened == ["http://127.0.0.1:8188/awp/novels"]


def test_launcher_reports_incomplete_pi_dependencies(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _: "node")
    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    (tmp_path / "frontend" / "dist" / "index.html").write_text("ok")
    with pytest.raises(LauncherError, match="agent_harness.*npm ci"):
        WebLauncher(repository_root=tmp_path).preflight()
