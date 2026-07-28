import json

import pytest

from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_draft import ChapterDraft
from awp_rp_runtime_v3.contracts.novel_authoring import AuthorChapterPlan
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_authoring_service import NovelAuthoringService
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_pi_tool_service import NovelPiToolService
from awp_rp_runtime_v3.storage.sqlite.database import Database
from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry


@pytest.fixture
def reg(tmp_path):
    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    registry.novel_project_store.create(NovelProject(project_id="p1", title="测试小说"))
    registry.novel_chapter_plan_store.save(
        ChapterPlan(chapter_id="ch1", project_id="p1", chapter_index=1, target_chars=100)
    )
    return registry


def test_default_tool_service_cannot_bypass_author_plan(reg, tmp_path):
    service = NovelPiToolService(reg, project_id="p1", project_dir=tmp_path)

    assert "plan_chapter" not in service.ALLOWED_TOOLS
    assert "write_chapter" not in service.ALLOWED_TOOLS


def test_execute_author_plan_uses_compiler_then_streaming_engine(monkeypatch, reg, tmp_path):
    calls = []
    authoring = NovelAuthoringService(tmp_path, "p1")
    pending = authoring.save_plan(
        AuthorChapterPlan.model_validate(
            {
                "plan_id": "author-ch1",
                "project_id": "p1",
                "chapter_index": 1,
                "purpose": "让人物作出选择",
                "confirmed_events": ["人物回到教室"],
                "scenes": [
                    {
                        "scene_id": "s1",
                        "summary": "人物回到教室",
                        "change": "人物决定留下",
                    }
                ],
                "proposal_turn": 1,
                "status": "pending_confirmation",
            }
        )
    )
    authoring.approve_plan(
        pending.plan_id, pending.revision, 2, "m2", "这个摘要准确，确认。", "确认"
    )
    monkeypatch.setattr(
        NovelEngine,
        "write_chapter_stream",
        lambda self, **kwargs: calls.append(kwargs)
        or type("Draft", (), {"char_count": 2, "status": "accepted"})(),
    )
    service = NovelPiToolService(
        reg,
        project_id="p1",
        project_dir=tmp_path,
        current_turn=3,
        current_message_id="m3",
        current_author_message="现在交给管线写第一章。",
    )
    result = service.execute(
        "execute_author_plan",
        {"plan_id": pending.plan_id, "revision": pending.revision, "confirmation_quote": "交给管线写"},
    )

    assert result["ok"] is True
    assert calls == [{"project_id": "p1", "chapter_index": 1, "write_guidance": ""}]
    assert reg.novel_chapter_plan_store.load_by_index("p1", 1) is not None


def test_audit_does_not_create_draft(monkeypatch, reg, tmp_path):
    monkeypatch.setattr(
        NovelEngine,
        "audit_chapter",
        lambda self, **kwargs: {"chapter": kwargs["chapter_index"], "verdict": "accept"},
    )

    result = NovelPiToolService(reg, project_id="p1", project_dir=tmp_path).execute(
        "audit_chapter", {"chapter": 1}
    )

    assert result["ok"] is True
    assert reg.novel_chapter_draft_store.load_latest("ch1") is None


def test_read_chapter_returns_accepted_revision_and_paragraph_anchors(reg, tmp_path):
    reg.novel_chapter_draft_store.save(ChapterDraft(
        draft_id="draft-ch1-r1", chapter_id="ch1", revision=1,
        status="accepted", text="第一段。\n\n第二段。", char_count=9,
    ))

    result = NovelPiToolService(reg, project_id="p1", project_dir=tmp_path).execute(
        "read_chapter", {"chapter": 1}
    )

    payload = json.loads(result["content"])
    assert payload["accepted_revision"] == 1
    assert payload["paragraphs"][0]["paragraph_id"] == "r1:p1"


def test_revision_tools_require_separate_author_turns(reg, tmp_path):
    reg.novel_chapter_draft_store.save(ChapterDraft(
        draft_id="draft-ch1-r1", chapter_id="ch1", revision=1,
        status="accepted", text="旧正文。", char_count=4,
    ))
    chapter = NovelPiToolService(reg, project_id="p1", project_dir=tmp_path).execute(
        "read_chapter", {"chapter": 1}
    )
    paragraph = json.loads(chapter["content"])["paragraphs"][0]
    plan_args = {
        "plan_id": "revision-pi-tool",
        "chapter_index": 1,
        "base_revision": 1,
        "patches": [{
            "patch_id": "patch-pi-tool",
            "paragraph_id": paragraph["paragraph_id"],
            "expected_paragraph_hash": paragraph["sha256"],
            "operation": "replace",
            "replacement_text": "新正文。",
            "reason": "减少解释。",
        }],
    }
    proposed = NovelPiToolService(
        reg, project_id="p1", project_dir=tmp_path,
        current_turn=1, current_message_id="m1", current_author_message="请提出修订。",
    ).execute("save_revision_plan", plan_args)
    assert proposed["ok"] is True

    approved = NovelPiToolService(
        reg, project_id="p1", project_dir=tmp_path,
        current_turn=2, current_message_id="m2", current_author_message="确认这组修订。",
    ).execute("approve_revision_plan", {
        "plan_id": "revision-pi-tool", "confirmation_quote": "确认这组修订",
    })
    assert approved["ok"] is True

    applied = NovelPiToolService(
        reg, project_id="p1", project_dir=tmp_path,
        current_turn=3, current_message_id="m3", current_author_message="现在应用这组修订。",
    ).execute("apply_revision_plan", {
        "plan_id": "revision-pi-tool", "expected_revision": 1,
        "confirmation_quote": "应用这组修订",
    })
    assert "r2" in applied["content"]


def test_editor_can_propose_but_cannot_activate_project_skill(reg, tmp_path):
    service = NovelPiToolService(
        reg, project_id="p1", project_dir=tmp_path,
        current_turn=1, current_message_id="m1", current_author_message="提议一个口吻检查技能。",
    )

    result = service.execute("propose_project_skill", {
        "proposal_id": "skill-proposal-voice-check", "skill_id": "voice-check",
        "purpose": "检查人物口吻", "behavior_impact": "只给出证据",
        "content": "---\nname: voice-check\ndescription: 检查角色口吻\n---\n只报告证据。",
    })

    assert "等待作者确认" in result["content"]
    with pytest.raises(ValueError, match="not allowed"):
        service.execute("activate_project_skill", {"skill_id": "voice-check"})


def test_service_refuses_unbound_or_unapproved_tool(reg, tmp_path):
    service = NovelPiToolService(reg, project_id="p1", project_dir=tmp_path)

    with pytest.raises(ValueError, match="not allowed"):
        service.execute("fetch_url", {"url": "https://example.invalid"})


def test_coding_tools_route_through_project_sandbox(reg, tmp_path):
    (tmp_path / "outline.md").write_text("第一章", encoding="utf-8")
    service = NovelPiToolService(reg, project_id="p1", project_dir=tmp_path)

    read = service.execute("read", {"path": "outline.md"})
    written = service.execute(
        "write", {"path": "notes/editor.md", "content": "需要核对时间线"}
    )

    assert read["ok"] is True
    assert "第一章" in read["content"]
    assert written["ok"] is True
    assert (tmp_path / "notes" / "editor.md").read_text(
        encoding="utf-8"
    ) == "需要核对时间线"


def test_important_project_write_requires_approval_callback(reg, tmp_path):
    requested = []
    callbacks = type(
        "Callbacks",
        (),
        {
            "request_tool_approval": lambda self, payload: (
                requested.append(payload) or "deny"
            )
        },
    )()
    service = NovelPiToolService(
        reg,
        project_id="p1",
        project_dir=tmp_path,
        callbacks=callbacks,
    )

    with pytest.raises(ValueError, match="denied"):
        service.execute(
            "write",
            {"path": "output/chapter_02.md", "content": "不应写入"},
        )

    assert requested[0]["tool"] == "write"
    assert not (tmp_path / "output" / "chapter_02.md").exists()
