from __future__ import annotations

from awp_rp_runtime_v3.contracts.novel_authoring import AuthorChapterPlan
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_authoring_service import NovelAuthoringService
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_pi_tool_service import NovelPiToolService
from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from awp_rp_runtime_v3.storage.sqlite.database import Database


def test_author_led_flow_records_then_confirms_then_writes(monkeypatch, tmp_path):
    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    registry.novel_project_store.create(NovelProject(project_id="p1", title="测试"))
    authoring = NovelAuthoringService(tmp_path, "p1")

    first_message = authoring.record_author_message(
        "第三章我想让她回来，但不要道歉。", "session-1", 1
    )
    pending = authoring.save_plan(
        AuthorChapterPlan.model_validate(
            {
                "plan_id": "author-ch3",
                "project_id": "p1",
                "chapter_index": 3,
                "purpose": "让她用回来代替道歉",
                "confirmed_events": ["她回到教室", "她交出钥匙但不道歉"],
                "scenes": [
                    {
                        "scene_id": "s1",
                        "summary": "她回到教室交出钥匙",
                        "change": "两人从回避变为暂时合作",
                    }
                ],
                "must_not": ["不要让她道歉"],
                "source_material_ids": [first_message],
                "proposal_turn": 1,
                "status": "pending_confirmation",
            }
        )
    )
    authoring.record_author_message("这个摘要准确，确认。", "session-1", 2)
    approved = authoring.approve_plan(
        pending.plan_id,
        pending.revision,
        2,
        "m2",
        "这个摘要准确，确认。",
        "确认",
    )

    write_calls: list[int] = []
    monkeypatch.setattr(
        NovelEngine,
        "plan_chapter",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Architect must not run in author-led flow")
        ),
    )
    monkeypatch.setattr(
        NovelEngine,
        "write_chapter_stream",
        lambda _self, **kwargs: (
            write_calls.append(kwargs["chapter_index"])
            or type("Draft", (), {"char_count": 100, "status": "accepted"})()
        ),
    )
    result = NovelPiToolService(
        registry,
        project_id="p1",
        project_dir=tmp_path,
        current_turn=3,
        current_message_id="m3",
        current_author_message="现在交给管线写第三章。",
    ).execute(
        "execute_author_plan",
        {
            "plan_id": approved.plan_id,
            "revision": approved.revision,
            "confirmation_quote": "交给管线写",
        },
    )

    assert result["ok"] is True
    assert write_calls == [3]
    journal = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / ".awp" / "authoring" / "journal").glob("*.jsonl")
    )
    assert "不要道歉" in journal
