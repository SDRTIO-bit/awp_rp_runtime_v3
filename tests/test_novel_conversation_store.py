from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from awp_rp_runtime_v3.contracts.novel_web_event import NovelRoomId, NovelWebEvent
from awp_rp_runtime_v3.runtime.novel_conversation_store import (
    NovelConversationStore,
    ROOT_BRANCH_ID,
)


def test_event_ids_are_durable_and_room_histories_are_isolated(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    first = store.append("book", "author_message_saved", {"text": "总纲想法"})
    second = store.append(
        "chapter:1", "author_message_saved", {"text": "第一章想法"}
    )

    restarted = NovelConversationStore(tmp_path, "p1")
    third = restarted.append(
        "chapter:1", "editor_message_completed", {"text": "追问"}
    )

    assert [first.event_id, second.event_id, third.event_id] == [1, 2, 3]
    assert [event.payload["text"] for event in restarted.replay("chapter:1")] == [
        "第一章想法",
        "追问",
    ]
    assert [event.payload["text"] for event in restarted.replay("book")] == [
        "总纲想法"
    ]


def test_replay_filters_by_event_id_and_enforces_limit(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    for index in range(4):
        store.append("chapter:2", "event", {"index": index})

    events = store.replay("chapter:2", after_event_id=1, limit=2)

    assert [event.event_id for event in events] == [2, 3]
    with pytest.raises(ValueError, match="limit"):
        store.replay("chapter:2", limit=0)
    with pytest.raises(ValueError, match="after_event_id"):
        store.replay("chapter:2", after_event_id=-1)


def test_partial_editor_deltas_are_not_replayed_as_completed_messages(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append(
        "chapter:1", "editor_delta", {"message_id": "m1", "text": "半句"}
    )

    events = store.replay("chapter:1")

    assert all(event.type != "editor_message_completed" for event in events)


def test_complete_editor_message_writes_an_explicit_completion_event(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")

    completed = store.complete_editor_message("chapter:1", "m1", "完整追问")

    assert completed.type == "editor_message_completed"
    assert completed.payload == {"message_id": "m1", "text": "完整追问"}


@pytest.mark.parametrize(
    "value",
    [
        "",
        "chapter",
        "chapter:",
        "chapter:0",
        "chapter:-1",
        "chapter:01",
        "chapter:1/../../outside",
        "book:1",
    ],
)
def test_room_ids_reject_noncanonical_or_unsafe_values(value):
    with pytest.raises(ValueError, match="invalid novel room"):
        NovelRoomId.parse(value)


def test_room_contract_is_frozen_and_consistent():
    room = NovelRoomId.parse("chapter:3")

    assert str(room) == "chapter:3"
    with pytest.raises(ValidationError):
        room.chapter_index = 4
    with pytest.raises(ValidationError):
        NovelRoomId(kind="book", chapter_index=1)


def test_replay_rejects_malformed_or_cross_room_rows(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "合法"})
    conversation = (
        tmp_path
        / ".awp"
        / "authoring"
        / "conversations"
        / "book.jsonl"
    )
    with conversation.open("a", encoding="utf-8") as handle:
        handle.write("{not-json}\n")

    with pytest.raises(ValueError, match="invalid conversation event"):
        store.replay("book")

    rows = conversation.read_text(encoding="utf-8").splitlines()
    rows[-1] = json.dumps(
        NovelWebEvent(
            event_id=2,
            project_id="p1",
            room="chapter:1",
            type="editor_message_completed",
            payload={},
            created_at="2026-07-26T00:00:00+00:00",
        ).model_dump(mode="json")
    )
    conversation.write_text("\n".join(rows) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not belong"):
        store.replay("book")


# ---------------------------------------------------------------------------
# Branch-aware append
# ---------------------------------------------------------------------------


def test_append_defaults_to_main_branch(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    event = store.append("book", "author_message_saved", {"text": "hello"})
    assert event.branch_id == ROOT_BRANCH_ID


def test_append_to_specific_branch(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    child = store.create_branch("book", title="child")
    event = store.append(
        "book",
        "author_message_saved",
        {"text": "child msg"},
        branch_id=child.branch_id,
    )
    assert event.branch_id == child.branch_id


def test_branch_aware_replay_filters_by_branch(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("book", "author_message_saved", {"text": "main msg"})
    child = store.create_branch("book", title="child")
    store.append(
        "book",
        "author_message_saved",
        {"text": "child msg"},
        branch_id=child.branch_id,
    )

    main_events = store.replay("book", "main")
    child_events = store.replay("book", child.branch_id)

    main_texts = [e.payload["text"] for e in main_events]
    child_texts = [e.payload["text"] for e in child_events]
    assert "main msg" in main_texts
    assert "child msg" not in main_texts
    assert "child msg" in child_texts
