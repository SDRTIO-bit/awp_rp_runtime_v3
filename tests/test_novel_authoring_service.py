from __future__ import annotations

import inspect
import json
from datetime import datetime

import pytest

from awp_rp_runtime_v3.contracts.novel_authoring import (
    AuthorChapterPlan,
    AuthorPlanStatus,
)
from awp_rp_runtime_v3.runtime.novel_authoring_service import NovelAuthoringService


def _plan(proposal_turn: int = 2) -> AuthorChapterPlan:
    return AuthorChapterPlan.model_validate(
        {
            "plan_id": "author-ch3",
            "project_id": "novel-1",
            "chapter_index": 3,
            "purpose": "让她主动选择回来",
            "confirmed_events": ["她回到空教室", "她交出钥匙但不道歉"],
            "scenes": [
                {
                    "scene_id": "s1",
                    "summary": "她回到空教室交出钥匙",
                    "change": "两人从回避变成暂时合作",
                }
            ],
            "proposal_turn": proposal_turn,
            "status": "pending_confirmation",
        }
    )


def test_message_is_appended_before_any_agent_work(tmp_path):
    service = NovelAuthoringService(tmp_path, "novel-1")
    message_id = service.record_author_message("她其实不想赢。", "session-1", 1)
    journal = (
        tmp_path
        / ".awp"
        / "authoring"
        / "journal"
        / f"{datetime.now().astimezone():%Y-%m-%d}.jsonl"
    )
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]

    assert rows[0]["message_id"] == message_id
    assert rows[0]["text"] == "她其实不想赢。"


def test_plan_versions_never_overwrite(tmp_path):
    service = NovelAuthoringService(tmp_path, "novel-1")
    first = service.save_plan(_plan())
    second = service.save_plan(first.model_copy(update={"purpose": "新目的"}))

    assert second.revision == 2
    assert service.get_plan(first.plan_id, 1).purpose == "让她主动选择回来"
    assert service.get_plan(first.plan_id).purpose == "新目的"


def test_approval_and_execution_require_distinct_explicit_turns(tmp_path):
    service = NovelAuthoringService(tmp_path, "novel-1")
    saved = service.save_plan(_plan(proposal_turn=2))

    with pytest.raises(ValueError, match="later author turn"):
        service.approve_plan(
            saved.plan_id, saved.revision, 2, "m2", "确认", "确认"
        )

    approved = service.approve_plan(
        saved.plan_id, saved.revision, 3, "m3", "这个摘要准确，确认。", "确认"
    )
    with pytest.raises(ValueError, match="later author turn"):
        service.mark_executed(
            approved.plan_id,
            approved.revision,
            3,
            "m3",
            "现在写",
            "现在写",
        )

    executed = service.mark_executed(
        approved.plan_id,
        approved.revision,
        4,
        "m4",
        "现在交给管线写第三章。",
        "交给管线写",
    )
    assert executed.status.value == "executed"


def test_service_never_accepts_an_external_path(tmp_path):
    service = NovelAuthoringService(tmp_path, "novel-1")

    assert "path" not in inspect.signature(service.save_plan).parameters


@pytest.mark.parametrize(
    "message, quote",
    [
        ("我不同意，不要批准这个计划。", "批准"),
        ("先别确认，我还要修改。", "确认"),
        ("我拒绝，就不要按这个。", "按这个"),
        ("我还没确认这个计划。", "确认"),
        ("我没有批准这个计划。", "批准"),
        ("我不想批准这个计划。", "批准"),
        ("我确认这个计划，但是我不同意。", "确认"),
    ],
)
def test_negated_approval_is_never_consent(tmp_path, message, quote):
    service = NovelAuthoringService(tmp_path, "novel-1")
    saved = service.save_plan(_plan(proposal_turn=1))

    with pytest.raises(ValueError, match="not an explicit approval"):
        service.approve_plan(
            saved.plan_id,
            saved.revision,
            2,
            "m2",
            message,
            quote,
        )


@pytest.mark.parametrize(
    "message, quote",
    [
        ("不要开始写，我只是讨论。", "开始写"),
        ("先不要写，等我补完。", "不要写"),
        ("我说的“开始写”不是让你开始写。", "开始写"),
        ("我还没决定开始写。", "开始写"),
        ("我没有授权你开始写。", "开始写"),
        ("现在开始写，但是不要开始写。", "开始写"),
    ],
)
def test_negated_or_quoted_execution_is_never_consent(tmp_path, message, quote):
    service = NovelAuthoringService(tmp_path, "novel-1")
    saved = service.save_plan(_plan(proposal_turn=1))
    approved = service.approve_plan(
        saved.plan_id,
        saved.revision,
        2,
        "m2",
        "这个计划准确，我确认。",
        "我确认",
    )

    with pytest.raises(ValueError, match="not an explicit execution request"):
        service.mark_executed(
            approved.plan_id,
            approved.revision,
            3,
            "m3",
            message,
            quote,
        )


def test_negative_story_constraint_does_not_cancel_explicit_execution(tmp_path):
    service = NovelAuthoringService(tmp_path, "novel-1")
    saved = service.save_plan(_plan(proposal_turn=1))
    approved = service.approve_plan(
        saved.plan_id,
        saved.revision,
        2,
        "m2",
        "这个计划准确，我确认。",
        "我确认",
    )

    executed = service.mark_executed(
        approved.plan_id,
        approved.revision,
        3,
        "m3",
        "不要写她道歉，按这个写。",
        "按这个写",
    )

    assert executed.status is AuthorPlanStatus.EXECUTED


def test_approval_quote_must_belong_to_the_explicit_consent_clause(tmp_path):
    service = NovelAuthoringService(tmp_path, "novel-1")
    saved = service.save_plan(_plan(proposal_turn=1))

    with pytest.raises(ValueError, match="not an explicit approval"):
        service.approve_plan(
            saved.plan_id,
            saved.revision,
            2,
            "m2",
            "我没有批准旧版本；新版本我确认。",
            "批准",
        )
