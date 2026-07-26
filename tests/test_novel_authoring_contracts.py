from __future__ import annotations

import pytest

from awp_rp_runtime_v3.contracts.novel_authoring import (
    AuthorChapterPlan,
    AuthorPlanStatus,
)


def _plan_data() -> dict:
    return {
        "plan_id": "author-ch3",
        "project_id": "novel-1",
        "chapter_index": 3,
        "purpose": "让她第一次承认自己其实害怕被留下",
        "confirmed_events": ["她主动返回空教室", "她没有道歉，只把钥匙交出去"],
        "scenes": [
            {
                "scene_id": "s1",
                "summary": "两人在空教室交接钥匙",
                "change": "关系从回避变成暂时合作",
            }
        ],
    }


def test_author_plan_defaults_to_draft_and_preserves_author_language():
    plan = AuthorChapterPlan.model_validate(_plan_data())

    assert plan.status == AuthorPlanStatus.DRAFT
    assert plan.confirmed_events[1] == "她没有道歉，只把钥匙交出去"


def test_approved_plan_rejects_blocking_unresolved_questions():
    data = _plan_data()
    data.update(
        status="approved",
        unresolved_questions=["她为什么回来？"],
    )

    with pytest.raises(ValueError, match="unresolved"):
        AuthorChapterPlan.model_validate(data)


def test_contracts_are_strict():
    data = _plan_data()
    data["invented_field"] = "模型自行发挥"

    with pytest.raises(ValueError, match="Extra inputs"):
        AuthorChapterPlan.model_validate(data)
