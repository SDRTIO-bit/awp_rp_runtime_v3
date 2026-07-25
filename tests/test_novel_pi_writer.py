from __future__ import annotations

from types import SimpleNamespace

import pytest

from awp_rp_runtime_v3.contracts.novel_chapter import BeatDetail, ChapterPlan
from awp_rp_runtime_v3.contracts.novel_pi_role_protocol import NovelPiRoleResult
from awp_rp_runtime_v3.contracts.novel_write_packet import NovelWritePacket
from awp_rp_runtime_v3.runtime.novel_role_context import novel_role_scope
from awp_rp_runtime_v3.runtime.novel_writer_adapter import NovelWriterAdapter
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_role_context import get_novel_role_context
from awp_rp_runtime_v3.runtime.prompt_loader import load_prompt


class RecordingWriterRuntime:
    def __init__(self, results):
        self.results = list(results)
        self.tasks = []

    def run(self, task, *, context, on_chunk=None):
        self.tasks.append(task)
        text = self.results.pop(0)
        if on_chunk:
            midpoint = max(1, len(text) // 2)
            on_chunk(text[:midpoint])
            on_chunk(text[midpoint:])
        return NovelPiRoleResult(
            request_id=f"r{len(self.tasks)}",
            role="writer",
            session_key=task.session_key,
            text=text,
            model="kimi-k2.6",
        )


def _packet() -> NovelWritePacket:
    plan = ChapterPlan(
        chapter_id="ch2",
        project_id="p1",
        chapter_index=2,
        title="第二章",
        target_chars=2000,
        scene_beats=(
            BeatDetail(beat_id="b1", description="字幕事故后对质", budget_chars=800),
            BeatDetail(beat_id="b2", description="两人被迫共同善后", budget_chars=900),
        ),
    )
    return NovelWritePacket(
        packet_id="packet-2",
        project_id="p1",
        chapter_id="ch2",
        chapter_plan=plan,
        current_scene_beat=plan.scene_beats[0],
        chapter_contract="用对话推进，完成事故善后",
    )


def test_writer_beats_share_chapter_revision_pi_session(monkeypatch):
    runtime = RecordingWriterRuntime(["第一段", "第二段"])
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_writer_adapter.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )
    packet = _packet()
    writer = NovelWriterAdapter(SimpleNamespace())

    with novel_role_scope(
        registry=SimpleNamespace(),
        project_id="p1",
        chapter_index=2,
        revision=3,
        artifacts={"write_packet": packet},
    ):
        writer.generate_beat(packet)
        packet.current_scene_beat = packet.chapter_plan.scene_beats[1]
        writer.generate_beat(packet)

    assert runtime.tasks[0].session_key == runtime.tasks[1].session_key
    assert runtime.tasks[0].session_key == "p1:2:3:writer"
    assert runtime.tasks[0].phase == "beat:b1"
    assert runtime.tasks[1].phase == "beat:b2"


def test_streamed_chunks_equal_final_writer_result(monkeypatch):
    runtime = RecordingWriterRuntime(["这是一段完整正文。"])
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_writer_adapter.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )
    packet = _packet()
    chunks: list[str] = []

    with novel_role_scope(
        registry=SimpleNamespace(),
        project_id="p1",
        chapter_index=2,
        revision=1,
        artifacts={"write_packet": packet},
    ):
        text = NovelWriterAdapter(SimpleNamespace()).generate_chapter_stream(
            packet, chunks.append,
        )

    assert text == "".join(chunks)
    assert runtime.tasks[0].stream is True
    assert runtime.tasks[0].phase == "chapter"


def test_writer_empty_pi_result_is_rejected(monkeypatch):
    runtime = RecordingWriterRuntime(["   "])
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_writer_adapter.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )
    packet = _packet()

    with novel_role_scope(
        registry=SimpleNamespace(), project_id="p1", chapter_index=2,
        artifacts={"write_packet": packet},
    ):
        with pytest.raises(RuntimeError, match="empty output"):
            NovelWriterAdapter(SimpleNamespace()).generate_chapter(packet)


def test_default_writer_prompt_is_genre_neutral():
    prompt = load_prompt("writer")

    assert "校园恋爱感" not in prompt
    assert "粉笔灰" not in prompt
    assert "六比四配比（恋爱喜剧）" not in prompt


def test_engine_closes_writer_session_after_chapter_scope(monkeypatch):
    closed = []
    runtime = SimpleNamespace(
        close_session=lambda session_key, **kwargs: closed.append(
            (session_key, kwargs["context"].revision)
        )
    )
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_engine.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )
    packet = _packet()

    with NovelEngine(SimpleNamespace())._writer_session(packet, revision=4):
        context = get_novel_role_context()
        assert context.artifacts["write_packet"] is packet
        assert context.revision == 4

    assert closed == [("p1:2:4:writer", 4)]
