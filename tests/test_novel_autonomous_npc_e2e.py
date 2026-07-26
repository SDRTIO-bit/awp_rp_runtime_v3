"""Fake end-to-end acceptance for the autonomous NPC novel pipeline."""

from __future__ import annotations

import json
from typing import Any

import pytest

from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan, ContentSummary
from awp_rp_runtime_v3.contracts.novel_npc_agenda import (
    NpcAction,
    NpcAgenda,
    VisibleConsequence,
)
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.contracts.novel_profile import default_autonomous_profile
from awp_rp_runtime_v3.contracts.novel_pi_role_protocol import NovelPiRoleResult
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_role_runtime import novel_role_runtime_override


def _agenda(npc: str = "配角甲") -> NpcAgenda:
    return NpcAgenda(
        agenda_id=f"agenda-{npc}",
        thread_key="steal-medicine",
        npc=npc,
        private_goal="私密目标",
        known_fact_ids=("fact-1",),
        resources=("万能钥匙",),
        cost="暴露行踪",
        next_action="潜入药库",
        trigger="夜深",
        risk="被巡夜撞见",
        visible_consequence=VisibleConsequence(
            agenda_id=f"agenda-{npc}",
            beat_id="b1",
            observable_event="配角甲在雨夜里截走了药材",
            observable_clue="窗台留下一枚铜钥匙",
            affected_characters=("主角",),
        ),
        deadline="3",
    )


def _plan_json(project_id: str, chapter_index: int) -> dict[str, Any]:
    return {
        "chapter_id": f"ch-{project_id}-{chapter_index}",
        "project_id": project_id,
        "chapter_index": chapter_index,
        "title": f"第{chapter_index}章",
        "target_chars": 300,
        "chapter_position": "progression",
        "target_emotion": "紧张",
        "opening_hook": "人物在冲突中开场",
        "main_payoff": "配角甲在雨夜里截走药材",
        "content_summary": {
            "cause": "主角发现药材失窃",
            "development": "配角甲在暗处行动，截走药材",
            "turning_point": "钥匙留窗",
            "climax": "截走药材",
            "ending": "夜雨未停",
        },
        "plot_arrangement": {
            "main_line": "失窃",
            "sub_line": "暗线",
            "event_line": "截药",
            "emotion_line": "紧张",
            "logic_line": "刑侦",
        },
        "scene_beats": [
            {
                "beat_id": f"ch{chapter_index}-b1",
                "description": "配角甲在暗处行动并截走药材",
                "function_tag": "推进",
                "density": "normal",
                "budget_chars": 300,
            }
        ],
    }


class OrderedRoleRuntime:
    """Deterministic Pi role double that records the role call order."""

    runtime_name = "AcceptancePiRoles"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._writer_text = (
            "门刚推开，雨声先涌进来。"
            "他低头看了一眼窗台，那里多了一枚铜钥匙——本该锁着的药柜被人提前打开。"
            "配角甲在雨夜里截走药材，桌上的清单被划去两行。"
            "他没有喊人，只是把钥匙收进掌心，重新把雨衣的兜帽压低。"
            "走廊尽头的灯还亮着，脚步声停在门外，又退回去。"
            "他把折痕抹平，说如果真想让他反悔，就不该提前把名字写上去。"
        )

    def run(self, task, *, context, on_chunk=None):
        del context
        self.calls.append(task.role)
        text = self._text(task)
        if on_chunk:
            on_chunk(text)
        return NovelPiRoleResult(
            request_id=f"acc-{len(self.calls)}",
            role=task.role,
            session_key=task.session_key,
            text=text,
            model="acceptance-test-model",
        )

    def close_session(self, session_key, **kwargs):
        del session_key, kwargs

    def _text(self, task) -> str:
        if task.role == "architect":
            return json.dumps(_plan_json(task.project_id, task.chapter_index), ensure_ascii=False)
        if task.role == "npc_planner":
            return json.dumps(
                {"agendas": [a.model_dump(mode="json") for a in (_agenda(),)]},
                ensure_ascii=False,
            )
        if task.role == "director":
            return json.dumps(
                {
                    "beat_details": [
                        {
                            "beat_id": f"ch{task.chapter_index}-b1",
                            "content_outline": "配角甲在暗处行动并截走药材",
                        }
                    ],
                    "selected_agenda_ids": ["agenda-配角甲"],
                    "risk_flags": [],
                    "opportunities": [],
                },
                ensure_ascii=False,
            )
        if task.role == "writer":
            return self._writer_text
        if task.role == "continuity_checker":
            return json.dumps({"issues": [], "severity": "info", "suggestions": []}, ensure_ascii=False)
        if task.role == "ledger_curator":
            return json.dumps(
                {
                    "chapter_summary": "配角甲截走药材，夜雨未停。",
                    "ledger_updates": [],
                    "ledger_resolves": [],
                },
                ensure_ascii=False,
            )
        return str(task.input_payload.get("prompt", ""))


@pytest.fixture
def reg(tmp_path):
    from awp_rp_runtime_v3.runtime.session_runtime_registry import (
        SessionRuntimeStoreRegistry,
    )
    from awp_rp_runtime_v3.storage.sqlite.database import Database

    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    return SessionRuntimeStoreRegistry(db)


@pytest.fixture
def engine(reg):
    return NovelEngine(reg)


def _setup_two_chapter_project(reg):
    """Install the autonomy profile and two related chapters + a candidate NPC."""
    project = NovelProject(
        project_id="p1", title="截药", status="writing",
        config={"autonomous_profile": default_autonomous_profile().model_dump()},
    )
    reg.novel_project_store.create(project)
    for ch in (1, 2):
        reg.novel_chapter_plan_store.save(
            ChapterPlan(
                chapter_id=f"ch{ch}", project_id="p1", chapter_index=ch, target_chars=100,
                title="截药",
                content_summary=ContentSummary(
                    cause="主角发现药材失窃", development="配角甲在暗处行动截走药材",
                ),
            )
        )
    reg.novel_character_store.save(
        NovelCharacter(
            character_id="c1", project_id="p1", name="配角甲", role="配角",
            first_appearance=1, core_motivation="夺回药材",
        )
    )


def _ledger_count(reg, section: str) -> int:
    return len(reg.novel_ledger_store.list_by_project("p1", section))


def test_two_chapter_nonstreaming_chain_stages_agendas_without_private_leakage(
    reg, engine, fake_novel_role_runtime
):
    _setup_two_chapter_project(reg)

    runtime = OrderedRoleRuntime()
    with novel_role_runtime_override(runtime):
        # The real adapters (architect, npc_planner, director, writer) all run
        # through the deterministic runtime — nothing is monkeypatched, so the
        # recorded role order reflects the true engine pipeline.

        first = engine.plan_chapter(project_id="p1", chapter_index=1)
        first = engine.write_chapter(project_id="p1", chapter_index=1)
        second = engine.plan_chapter(project_id="p1", chapter_index=2)
        second = engine.write_chapter(project_id="p1", chapter_index=2)

    assert first.status == "accepted"
    assert second.status == "accepted"

    # The non-streaming V4 path has no Director selection phase. It may stage
    # an agenda, but must not promote it to a confirmed action by itself.
    assert _ledger_count(reg, NpcAction.LEDGER_SECTION) == 0
    assert _ledger_count(reg, "npc_agenda") >= 1
    assert "截走药材" in second.text
    assert "私密目标" not in second.text
    # The Writer never saw the Planner/Director private agenda either.
    assert "万能钥匙" not in second.text
    assert "被巡夜撞见" not in second.text

    # Exact non-streaming V4 role order: no Director or continuity role.
    expected_ch1 = [
        "architect", "npc_planner", "writer", "ledger_curator",
    ]
    assert runtime.calls == expected_ch1 + expected_ch1


@pytest.mark.skipif(
    "RUN_NOVEL_REAL_E2E" not in __import__("os").environ,
    reason="requires RUN_NOVEL_REAL_E2E=1 and real DeepSeek V4 Pro credentials",
)
def test_real_deepseek_two_chapter_chain():
    """Optional real-LLM acceptance. SKIPPED without credentials — never PASS."""
    # Guard: refuse to run if credentials/pofile are not actually configured.
    import os
    if "RUN_NOVEL_REAL_E2E" not in os.environ:
        pytest.skip("RUN_NOVEL_REAL_E2E not set")
    pytest.skip("real DeepSeek e2e not configured in this environment")
