"""Tests for novel-mode memory pipeline integration."""

from __future__ import annotations

from awp_rp_runtime_v3.contracts.active_memory import ActiveMemoryRecord
from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan, ContentSummary
from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_director_guidance import DirectorGuidance
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.contracts.novel_write_packet import NovelWritePacket
from awp_rp_runtime_v3.contracts.rag_memory import RagMemoryRecord
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_writer_adapter import NovelWriterAdapter


def _registry(tmp_path):
    from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry
    from awp_rp_runtime_v3.storage.sqlite.database import Database

    db = Database(str(tmp_path / "novel_memory.db"))
    db.initialize()
    return SessionRuntimeStoreRegistry(db)


class CapturingNovelEngine(NovelEngine):
    def __init__(self, registry, chapter_text: str):
        super().__init__(registry)
        self.chapter_text = chapter_text
        self.captured_packet: NovelWritePacket | None = None

    def _call_director(self, *args, **kwargs):
        from awp_rp_runtime_v3.contracts.novel_director_guidance import BeatGuidance
        return DirectorGuidance(
            guidance_id="guid-test",
            character_anchor="主角: 30岁男, 测试角色",
            timeline_anchor="第1章, 搬入第1天",
            beat_details=(
                BeatGuidance(
                    beat_id="b1",
                    content_outline="推进本章计划",
                    emotion_shift="压抑到警觉",
                    info_type="对话",
                ),
            ),
        )

    def _call_writer(self, packet: NovelWritePacket, **_kwargs) -> str:
        self.captured_packet = packet
        return self.chapter_text


def test_write_chapter_commits_novel_active_rag_ledger_and_character_state(
    tmp_path, fake_novel_role_runtime
):
    reg = _registry(tmp_path)
    reg.novel_project_store.create(NovelProject(project_id="p1", title="空房间"))
    reg.novel_character_store.save(
        NovelCharacter(
            character_id="char-lin",
            project_id="p1",
            name="林舟",
            first_appearance=1,
            current_state={"location": "403室"},
        )
    )
    reg.novel_chapter_plan_store.save(
        ChapterPlan(
            chapter_id="ch1",
            project_id="p1",
            chapter_index=1,
            title="银钥匙",
            target_chars=40,
            content_summary=ContentSummary(
                cause="林舟发现银钥匙",
                development="门后规则改变",
                ending="留下未解决的伏笔",
            ),
        )
    )
    text = (
        "林舟在403室找到银钥匙，门后规则改变。"
        "她承诺明晚回来验证钥匙。这个秘密成为新的伏笔。"
    )

    engine = CapturingNovelEngine(reg, text)
    draft = engine.write_chapter(project_id="p1", chapter_index=1)

    assert "银钥匙" in draft.text
    active = reg.active_memory_store.get_all("p1", "novel:p1")
    rag = reg.rag_memory_store.search("p1", "novel:p1", "银钥匙", limit=5)
    ledger = reg.novel_ledger_store.list_by_project("p1")
    character = reg.novel_character_store.load("char-lin")

    assert any("承诺" in m.summary or "伏笔" in m.summary for m in active)
    assert any("银钥匙" in m.content or "银钥匙" in m.summary for m in rag)
    assert any(i.section in {"foreshadowing", "world_rules", "open_threads"} for i in ledger)
    assert character is not None
    assert character.current_state["last_chapter_index"] == 1
    assert "银钥匙" in character.current_state["recent_summary"]


def test_write_chapter_recalls_memory_into_writer_packet_and_prompt(
    tmp_path, fake_novel_role_runtime
):
    reg = _registry(tmp_path)
    reg.novel_project_store.create(NovelProject(project_id="p1", title="空房间"))
    reg.novel_chapter_plan_store.save(
        ChapterPlan(
            chapter_id="ch2",
            project_id="p1",
            chapter_index=2,
            title="钥匙背面",
            target_chars=40,
            content_summary=ContentSummary(
                cause="林舟研究银钥匙",
                development="钥匙背面刻着403",
            ),
        )
    )
    reg.active_memory_store.upsert(
        "p1",
        "novel:p1",
        ActiveMemoryRecord(
            memory_id="am-seed",
            card_id="p1",
            session_id="novel:p1",
            summary="林舟承诺明晚回到403室验证银钥匙的真正用途",
            kind="promise",
            entity_refs=["林舟"],
            source_turn_ids=["novel:p1:ch1"],
            source_card_state_revision=1,
            importance=0.9,
            confidence=0.9,
        ),
    )
    reg.rag_memory_store.save(
        "p1",
        "novel:p1",
        RagMemoryRecord(
            memory_id="rag-seed",
            card_id="p1",
            session_id="novel:p1",
            content="第一章里林舟在403室找到银钥匙，门后的规则随之改变。",
            summary="林舟找到银钥匙，403室规则改变",
            entity_refs=["林舟"],
            source_turn_ids=["novel:p1:ch1"],
            source_card_state_revision=1,
            importance=0.8,
            confidence=0.9,
        ),
    )

    engine = CapturingNovelEngine(reg, "林舟翻过银钥匙，看见背面的403。")
    engine.write_chapter(project_id="p1", chapter_index=2)

    assert engine.captured_packet is not None
    packet = engine.captured_packet
    assert any("银钥匙" in m["content"] for m in packet.memory_recall)
    assert any("承诺" in m["content"] for m in packet.active_memory_context)

    # Raw memory stays available to deterministic runtimes but is not dumped
    # into the context-light Writer prompt without a tested selection policy.
    _, prompt = NovelWriterAdapter(reg)._build_prompt(packet)
    assert "=== MEMORY RECALL ===" not in prompt
    assert "=== ACTIVE MEMORY ===" not in prompt
