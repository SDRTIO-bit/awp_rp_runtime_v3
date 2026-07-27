"""Test the append-only branch graph, inherited replay, effect detection,
and context rendering."""

from __future__ import annotations

import pytest

from awp_rp_runtime_v3.contracts.novel_web_event import NovelWebEvent
from awp_rp_runtime_v3.runtime.novel_conversation_store import (
    NovelConversationStore,
    ROOT_BRANCH_ID,
)


# ---------------------------------------------------------------------------
# Legacy row adaptation (no rewrite)
# ---------------------------------------------------------------------------


def test_legacy_rows_are_replayed_as_main_without_rewrite(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    legacy_path = store.root / "book.jsonl"
    legacy_path.write_text(
        NovelWebEvent(
            event_id=1,
            project_id="p1",
            room="book",
            type="author_message_saved",
            payload={"text": "旧消息"},
            created_at="2026-07-27T00:00:00+00:00",
        ).model_dump_json(exclude={"branch_id", "turn_id"})
        + "\n",
        encoding="utf-8",
    )
    before = legacy_path.read_bytes()
    assert store.list_branches("book")[0].branch_id == "main"
    assert store.replay("book", "main")[0].branch_id == "main"
    assert legacy_path.read_bytes() == before


# ---------------------------------------------------------------------------
# Branch creation and child replay
# ---------------------------------------------------------------------------


def test_child_replay_stops_parent_at_fork_event(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    first = store.append("book", "author_message_saved", {"text": "A"})
    store.append("book", "editor_message_completed", {"text": "旧回答"})
    child = store.create_branch(
        "book",
        parent_branch_id="main",
        fork_event_id=first.event_id,
        title="新回答",
    )
    store.append(
        "book",
        "editor_message_completed",
        {"text": "新回答"},
        branch_id=child.branch_id,
    )
    texts = [
        e.payload["text"] for e in store.replay("book", child.branch_id)
    ]
    assert texts == ["A", "新回答"]


def test_new_root_has_no_inherited_events(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "主分支消息"})
    root2 = store.create_branch("book", title="新对话")
    events = store.replay("book", root2.branch_id)
    assert len(events) == 0


def test_unknown_parent_is_rejected(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    with pytest.raises(ValueError, match="parent"):
        store.create_branch(
            "book",
            parent_branch_id="nonexistent",
            fork_event_id=1,
            title="坏分支",
        )


def test_unknown_fork_event_is_rejected(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "A"})
    with pytest.raises(ValueError, match="fork"):
        store.create_branch(
            "book",
            parent_branch_id="main",
            fork_event_id=999,
            title="坏分支",
        )


def test_fork_event_must_belong_to_parent_history(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "A"})
    child = store.create_branch(
        "book",
        parent_branch_id="main",
        fork_event_id=1,
        title="子分支",
    )
    store.append(
        "book",
        "editor_message_completed",
        {"text": "子回答"},
        branch_id=child.branch_id,
    )
    # Try to fork from main at the child's event (event_id=2) — it's not in main's history
    with pytest.raises(ValueError, match="fork"):
        store.create_branch(
            "book",
            parent_branch_id="main",
            fork_event_id=2,
            title="坏分支",
        )


def test_cycles_cannot_be_created(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "A"})
    child = store.create_branch(
        "book",
        parent_branch_id="main",
        fork_event_id=1,
        title="child",
    )
    with pytest.raises(ValueError, match="not in parent|cycle|ancestor"):
        store.create_branch(
            "book",
            parent_branch_id=child.branch_id,
            fork_event_id=1,
            title="循环",
        )


# ---------------------------------------------------------------------------
# Rename and archive
# ---------------------------------------------------------------------------


def test_rename_and_archive_append_metadata_not_rewrite(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "A"})
    metadata_path = store._branch_path(store._parse_room("book"))
    before_lines = (
        len(metadata_path.read_text(encoding="utf-8").splitlines())
        if metadata_path.is_file()
        else 0
    )

    store.update_branch("book", "main", title="新标题")

    branches = store.list_branches("book")
    assert branches[0].title == "新标题"

    store.update_branch("book", "main", archived=True)

    branches_after = store.list_branches("book")
    assert len(branches_after) == 0  # archived, hidden by default
    all_branches = store.list_branches("book", include_archived=True)
    assert all_branches[0].status == "archived"
    assert all_branches[0].title == "新标题"

    # Metadata rows should have increased
    after_lines = len(
        metadata_path.read_text(encoding="utf-8").splitlines()
    )
    assert after_lines > before_lines


def test_archived_branches_hidden_by_default(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "A"})
    child = store.create_branch("book", title="新版")
    store.update_branch("book", child.branch_id, archived=True)

    active = store.list_branches("book")
    assert all(b.status == "active" for b in active)
    assert child.branch_id not in [b.branch_id for b in active]

    all_branches = store.list_branches("book", include_archived=True)
    archived_ids = {b.branch_id for b in all_branches}
    assert child.branch_id in archived_ids


# ---------------------------------------------------------------------------
# Effect detection
# ---------------------------------------------------------------------------


def test_fork_after_effect_raises_conflict(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "A"})
    store.append(
        "book",
        "project_file_changed",
        {"path": "outline.md"},
    )
    store.append("book", "editor_message_completed", {"text": "改完了"})

    with pytest.raises(ValueError, match="side.effect|confirm"):
        store.create_branch(
            "book",
            parent_branch_id="main",
            fork_event_id=2,  # after the file change
            title="撤销改动",
        )


def test_fork_after_effect_with_confirm_succeeds(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "A"})
    store.append(
        "book",
        "project_file_changed",
        {"path": "outline.md"},
    )

    branch = store.create_branch(
        "book",
        parent_branch_id="main",
        fork_event_id=2,
        title="继续",
        confirm_effects=True,
    )
    assert branch.branch_id != "main"


def test_pipeline_phase_start_is_an_effect(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "A"})
    store.append(
        "book",
        "pipeline_phase",
        {"phase": "writer", "event": "start"},
    )

    effects = store.effects_after("book", "main", after_event_id=1)
    assert len(effects) == 1
    assert effects[0].type == "pipeline_phase"


def test_pipeline_phase_non_start_is_not_an_effect(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "A"})
    store.append(
        "book",
        "pipeline_phase",
        {"phase": "writer", "event": "progress"},
    )

    effects = store.effects_after("book", "main", after_event_id=1)
    assert len(effects) == 0


# ---------------------------------------------------------------------------
# Context rendering
# ---------------------------------------------------------------------------


def test_render_context_excludes_deltas_and_failed(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "完整消息"})
    store.append(
        "book",
        "editor_delta",
        {"message_id": "m1", "text": "部分"},
    )
    store.append(
        "book",
        "editor_message_completed",
        {"text": "最终回答"},
    )
    store.append("book", "turn_failed", {"error": "boom"})

    context = store.render_context("book", "main")
    assert "完整消息" in context
    assert "最终回答" in context
    assert "部分" not in context  # deltas excluded
    assert "boom" not in context  # failed turn excluded


def test_render_context_stops_at_fork_point(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    first = store.append("book", "author_message_saved", {"text": "A"})
    store.append("book", "editor_message_completed", {"text": "旧回答"})
    child = store.create_branch(
        "book",
        parent_branch_id="main",
        fork_event_id=first.event_id,
        title="新回答",
    )
    store.append(
        "book",
        "editor_message_completed",
        {"text": "新回答"},
        branch_id=child.branch_id,
    )

    context = store.render_context("book", child.branch_id)
    assert "A" in context
    assert "旧回答" not in context  # after fork point
    assert "新回答" not in context  # own events not in context


# ---------------------------------------------------------------------------
# Interrupted turn recovery
# ---------------------------------------------------------------------------


def test_unmatched_turn_started_gets_one_turn_interrupted(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append(
        "book",
        "turn_started",
        {"status": "queued"},
        turn_id="turn-1",
    )
    store.append(
        "book",
        "author_message_saved",
        {"text": "未完成的对话"},
        turn_id="turn-1",
    )

    # Should insert turn_interrupted
    events = store.interrupt_incomplete_turn("book", "main")
    assert any(e.type == "turn_interrupted" for e in events)


def test_already_terminal_turn_not_interrupted_again(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append(
        "book",
        "turn_started",
        {"status": "queued"},
        turn_id="turn-1",
    )
    store.append(
        "book",
        "author_message_saved",
        {"text": "已完成"},
        turn_id="turn-1",
    )
    store.append(
        "book",
        "turn_completed",
        {"status": "completed"},
        turn_id="turn-1",
    )

    events = store.interrupt_incomplete_turn("book", "main")
    # Should be empty — nothing to interrupt
    assert len(events) == 0
