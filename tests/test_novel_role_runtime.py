from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from awp_rp_runtime_v3.contracts.novel_pi_role_protocol import (
    NovelPiRoleResult,
    NovelPiRoleTask,
)
from awp_rp_runtime_v3.runtime.novel_role_context import NovelRoleContext
from awp_rp_runtime_v3.runtime.novel_role_runtime import create_novel_role_runtime


def _task() -> NovelPiRoleTask:
    return NovelPiRoleTask(
        role="writer",
        project_id="p1",
        chapter_index=1,
        session_key="p1:1:1:writer",
        task_contract="write",
        input_payload={"prompt": "hello"},
    )


def _context() -> NovelRoleContext:
    return NovelRoleContext(
        registry=SimpleNamespace(), project_id="p1", chapter_index=1
    )


def test_pi_roles_are_default_and_do_not_create_direct_adapter(monkeypatch):
    monkeypatch.delenv("NOVEL_AGENT_RUNTIME", raising=False)
    factory = Mock()
    factory.get_adapter.side_effect = AssertionError("direct adapter used")
    expected = NovelPiRoleResult(
        request_id="r1",
        role="writer",
        session_key="p1:1:1:writer",
        text="正文",
    )
    bridge = Mock()
    bridge.run.return_value = expected

    runtime = create_novel_role_runtime(llm_factory=factory, bridge=bridge)
    result = runtime.run(_task(), context=_context())

    assert runtime.runtime_name == "PiRoles"
    assert result is expected
    factory.get_adapter.assert_not_called()


def test_legacy_roles_require_explicit_environment_choice(monkeypatch):
    monkeypatch.setenv("NOVEL_AGENT_RUNTIME", "legacy")

    runtime = create_novel_role_runtime(llm_factory=Mock())

    assert runtime.runtime_name == "LegacyRoles"


def test_unknown_role_runtime_is_rejected(monkeypatch):
    monkeypatch.setenv("NOVEL_AGENT_RUNTIME", "automatic-fallback")

    with pytest.raises(ValueError, match="Unsupported NOVEL_AGENT_RUNTIME"):
        create_novel_role_runtime()
