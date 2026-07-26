from __future__ import annotations

from awp_rp_runtime_v3.contracts.novel_tool_approval import (
    ToolApprovalDecision,
    ToolApprovalRequest,
)
from awp_rp_runtime_v3.runtime.novel_project_sandbox import NovelProjectSandbox


def test_risk_policy_is_fail_closed(tmp_path):
    (tmp_path / "outline.md").write_text("第一章", encoding="utf-8")
    sandbox = NovelProjectSandbox(tmp_path)

    assert sandbox.classify("read", {"path": "outline.md"}).risk == "read"
    assert (
        sandbox.classify(
            "write", {"path": "notes/idea.md", "content": "x"}
        ).risk
        == "write"
    )
    assert (
        sandbox.classify(
            "write", {"path": "output/chapter_02.md", "content": "x"}
        ).risk
        == "important"
    )
    denied = sandbox.classify(
        "bash", {"command": "curl https://example.com"}
    )
    assert denied.risk == "hard_deny"
    assert "network" in denied.reason


def test_protected_write_is_a_hard_deny_instead_of_an_exception(tmp_path):
    request = NovelProjectSandbox(tmp_path).classify(
        "write", {"path": ".awp/authoring/plans/x.json", "content": "{}"}
    )

    assert request.risk == "hard_deny"
    assert request.targets == [".awp/authoring/plans/x.json"]


def test_approval_contracts_are_strict_and_have_stable_signature():
    request = ToolApprovalRequest.create(
        tool="write",
        risk="important",
        summary="覆盖章节正文",
        targets=["output/chapter_02.md"],
        reason="chapter output requires author approval",
        arguments={"path": "output/chapter_02.md", "content": "正文"},
    )
    decision = ToolApprovalDecision(
        approval_id=request.approval_id,
        decision="allow",
        remember=False,
    )

    assert len(request.signature) == 64
    assert decision.decision == "allow"
    assert request.model_dump()["risk"] == "important"
