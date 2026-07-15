from __future__ import annotations

from types import SimpleNamespace

import pytest

from awp_rp_runtime_v3.scripts import novel_cli


def test_cli_banner_reports_pi_role_runtime(monkeypatch, capsys):
    monkeypatch.delenv("NOVEL_AGENT_RUNTIME", raising=False)
    monkeypatch.setattr(
        novel_cli,
        "get_novel_role_runtime",
        lambda: SimpleNamespace(runtime_name="PiRoles"),
        raising=False,
    )
    monkeypatch.setattr(
        novel_cli,
        "_writer_role_connection",
        lambda: SimpleNamespace(provider="opencode", model="kimi-k2.6"),
        raising=False,
    )

    novel_cli._print_agent_runtime_banner()

    output = capsys.readouterr().out
    assert "Agent Runtime: Pi role agents" in output
    assert "opencode / kimi-k2.6" in output


def test_cli_pi_missing_dependencies_does_not_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("NOVEL_AGENT_RUNTIME", raising=False)
    harness = tmp_path / "agent_harness" / "src"
    harness.mkdir(parents=True)
    (harness / "novel_role_host.mjs").write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match="npm ci"):
        novel_cli.assert_pi_role_runtime_ready(tmp_path)


def test_cli_legacy_mode_does_not_require_pi_dependencies(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVEL_AGENT_RUNTIME", "legacy")

    novel_cli.assert_pi_role_runtime_ready(tmp_path)
