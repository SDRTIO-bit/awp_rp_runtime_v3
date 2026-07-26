from __future__ import annotations

import json

import pytest

from awp_rp_runtime_v3.contracts.novel_authoring import (
    AuthorChapterPlan,
    AuthorPlanStatus,
)
from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_author_plan_compiler import AuthorPlanCompiler
from awp_rp_runtime_v3.runtime.novel_authoring_service import NovelAuthoringService
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_npc_agenda_adapter import NovelNpcAgendaAdapter
from awp_rp_runtime_v3.runtime.novel_pi_tool_service import NovelPiToolService
from awp_rp_runtime_v3.runtime.novel_write_packet_builder import NovelWritePacketBuilder
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


def test_author_led_pipeline_never_invokes_autonomous_npc_planner(
    monkeypatch, tmp_path, fake_novel_role_runtime
):
    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    registry.novel_project_store.create(
        NovelProject(
            project_id="p1",
            title="测试",
            config={"novel_dir": str(tmp_path)},
        )
    )
    registry.novel_character_store.save(
        NovelCharacter(
            character_id="c1",
            project_id="p1",
            name="林舟",
            first_appearance=1,
            core_motivation="找回钥匙",
        )
    )
    authoring = NovelAuthoringService(tmp_path, "p1")
    pending = authoring.save_plan(
        AuthorChapterPlan.model_validate(
            {
                "plan_id": "author-ch1",
                "project_id": "p1",
                "chapter_index": 1,
                "purpose": "让林舟拿回钥匙",
                "confirmed_events": ["林舟找回钥匙"],
                "scenes": [
                    {
                        "scene_id": "s1",
                        "summary": "林舟找回钥匙",
                        "change": "林舟决定暂时留下",
                        "characters": ["林舟"],
                    }
                ],
                "proposal_turn": 1,
                "status": "pending_confirmation",
            }
        )
    )
    approved = authoring.approve_plan(
        pending.plan_id,
        pending.revision,
        2,
        "m2",
        "这个计划准确，我确认。",
        "我确认",
    )
    AuthorPlanCompiler().compile_and_save(approved, registry)
    monkeypatch.setattr(
        NovelNpcAgendaAdapter,
        "propose",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("author-led pipeline must not invoke autonomous NPC planning")
        ),
    )
    monkeypatch.setattr(
        NovelEngine,
        "_call_director",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("author-led pipeline must not invoke Director")
        ),
    )

    draft = NovelEngine(registry).write_chapter_stream(
        project_id="p1",
        chapter_index=1,
    )

    assert draft.char_count > 0
    assert all(
        task.role != "director" for task in fake_novel_role_runtime.tasks
    )
    assert registry.novel_ledger_store.list_by_project("p1", "npc_agenda") == []


def test_author_plan_binding_survives_a_later_pending_revision(tmp_path):
    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    registry.novel_project_store.create(
        NovelProject(
            project_id="p1",
            title="测试",
            config={"novel_dir": str(tmp_path)},
        )
    )
    authoring = NovelAuthoringService(tmp_path, "p1")
    pending = authoring.save_plan(
        AuthorChapterPlan.model_validate(
            {
                "plan_id": "author-ch1",
                "project_id": "p1",
                "chapter_index": 1,
                "purpose": "保留第一版目的",
                "confirmed_events": ["她交出钥匙"],
                "scenes": [
                    {
                        "scene_id": "s1",
                        "summary": "她交出钥匙",
                        "change": "两人暂时合作",
                    }
                ],
                "proposal_turn": 1,
                "status": "pending_confirmation",
            }
        )
    )
    approved = authoring.approve_plan(
        pending.plan_id,
        pending.revision,
        2,
        "m2",
        "这个计划准确，我确认。",
        "我确认",
    )
    chapter = AuthorPlanCompiler().compile(approved)
    registry.novel_chapter_plan_store.save(chapter)
    authoring.save_plan(
        approved.model_copy(
            update={
                "purpose": "尚未批准的第二版目的",
                "status": AuthorPlanStatus.PENDING_CONFIRMATION,
            }
        )
    )

    builder = NovelWritePacketBuilder(registry)

    assert builder.has_approved_author_plan(chapter) is True
    contract = builder._approved_author_contract(chapter, str(tmp_path))
    assert "保留第一版目的" in contract
    assert "尚未批准的第二版目的" not in contract


def test_tampered_bound_author_plan_fails_closed(tmp_path):
    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    registry.novel_project_store.create(
        NovelProject(
            project_id="p1",
            title="测试",
            config={"novel_dir": str(tmp_path)},
        )
    )
    authoring = NovelAuthoringService(tmp_path, "p1")
    pending = authoring.save_plan(
        AuthorChapterPlan.model_validate(
            {
                "plan_id": "author-ch1",
                "project_id": "p1",
                "chapter_index": 1,
                "purpose": "原始批准目的",
                "confirmed_events": ["她交出钥匙"],
                "scenes": [
                    {
                        "scene_id": "s1",
                        "summary": "她交出钥匙",
                        "change": "两人暂时合作",
                    }
                ],
                "proposal_turn": 1,
                "status": "pending_confirmation",
            }
        )
    )
    approved = authoring.approve_plan(
        pending.plan_id,
        pending.revision,
        2,
        "m2",
        "这个计划准确，我确认。",
        "我确认",
    )
    chapter = AuthorPlanCompiler().compile(approved)
    plan_path = (
        tmp_path
        / ".awp"
        / "authoring"
        / "chapter-plans"
        / "author-ch1.v1.json"
    )
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["purpose"] = "未经作者批准的篡改"
    plan_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="provenance"):
        NovelWritePacketBuilder(registry).has_approved_author_plan(chapter)
