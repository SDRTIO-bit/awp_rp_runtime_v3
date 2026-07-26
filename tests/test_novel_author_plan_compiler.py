from __future__ import annotations

from awp_rp_runtime_v3.contracts.novel_authoring import (
    AuthorApproval,
    AuthorChapterPlan,
)
from awp_rp_runtime_v3.runtime.novel_author_plan_compiler import AuthorPlanCompiler


def _approved_plan() -> AuthorChapterPlan:
    return AuthorChapterPlan.model_validate(
        {
            "plan_id": "author-ch3",
            "project_id": "novel-1",
            "chapter_index": 3,
            "status": "approved",
            "purpose": "让她以行动承认自己害怕被留下",
            "target_reader_effect": "读者先误以为她来道歉，随后发现她拒绝道歉",
            "confirmed_events": ["她返回空教室", "她把钥匙交出去"],
            "causal_chain": ["因为她不愿失去合作机会，所以她返回"],
            "scenes": [
                {
                    "scene_id": "s1",
                    "summary": "她返回空教室",
                    "change": "她决定交出钥匙",
                    "characters": ["林夏"],
                },
                {
                    "scene_id": "s2",
                    "summary": "他拒绝追问",
                    "change": "两人暂时合作",
                    "characters": ["周明"],
                },
            ],
            "must_not": ["不要让她道歉"],
            "writer_freedom": ["可以自由设计钥匙交接时的动作"],
            "approval": {
                "message_id": "m3",
                "confirmation_quote": "确认",
                "turn": 3,
                "approved_at": "2026-07-26T00:00:00+00:00",
                "content_hash": "abc",
            },
        }
    )


def test_compiler_preserves_scene_order_and_language():
    chapter = AuthorPlanCompiler().compile(_approved_plan())

    assert [beat.description for beat in chapter.scene_beats] == [
        "她返回空教室；变化：她决定交出钥匙",
        "他拒绝追问；变化：两人暂时合作",
    ]


def test_writer_contract_contains_author_red_lines_verbatim():
    contract = AuthorPlanCompiler().render_writer_contract(_approved_plan())

    assert "不要让她道歉" in contract
    assert "可以自由设计钥匙交接时的动作" in contract
    assert "读者先误以为她来道歉" in contract
