from __future__ import annotations

import json

import pytest

from awp_rp_runtime_v3.contracts.novel_chapter import BeatDetail, ChapterPlan
from awp_rp_runtime_v3.contracts.novel_pi_role_protocol import NovelPiRoleResult
from awp_rp_runtime_v3.contracts.novel_director_guidance import DirectorGuidance
from awp_rp_runtime_v3.runtime.novel_architect_adapter import NovelArchitectAdapter
from awp_rp_runtime_v3.runtime.novel_director_adapter import NovelDirectorAdapter
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_role_context import (
    get_novel_role_context,
    novel_role_scope,
)


@pytest.fixture
def reg(tmp_path):
    from awp_rp_runtime_v3.runtime.session_runtime_registry import (
        SessionRuntimeStoreRegistry,
    )
    from awp_rp_runtime_v3.storage.sqlite.database import Database

    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    return SessionRuntimeStoreRegistry(db)


class RecordingRoleRuntime:
    def __init__(self, text: str):
        self.text = text
        self.tasks = []
        self.contexts = []

    def run(self, task, *, context, on_chunk=None):
        del on_chunk
        self.tasks.append(task)
        self.contexts.append(context)
        return NovelPiRoleResult(
            request_id=f"req-{len(self.tasks)}",
            role=task.role,
            session_key=task.session_key,
            text=self.text,
            model="kimi-k2.6",
        )


def _plan() -> ChapterPlan:
    return ChapterPlan(
        chapter_id="ch-p1-1",
        project_id="p1",
        chapter_index=1,
        title="告白事故",
        target_chars=3000,
        scene_beats=(
            BeatDetail(
                beat_id="b1",
                description="舞台字幕失控，唐梨把陈默拽上台",
                function_tag="开篇爆点",
                budget_chars=900,
            ),
        ),
    )


def test_architect_uses_pi_role_runtime(monkeypatch, reg):
    runtime = RecordingRoleRuntime(json.dumps(_plan().to_dict(), ensure_ascii=False))
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_architect_adapter.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )

    with novel_role_scope(registry=reg, project_id="p1", chapter_index=1):
        plan = NovelArchitectAdapter(reg).plan_chapter(
            "p1", 1, None, [], [], {},
        )

    assert runtime.tasks[0].role == "architect"
    assert runtime.tasks[0].session_key.startswith("task:")
    assert runtime.tasks[0].input_payload["response_format"] == "chapter_plan_json"
    assert plan.target_chars == 2000
    assert plan.scene_beats


def test_director_uses_task_scoped_pi_session(monkeypatch, reg):
    director_json = json.dumps({
        "beat_details": [{
            "beat_id": "b1",
            "content_outline": "字幕展开后两人先互相甩锅，再发现真正告白对象走了",
            "gap": "救场变成公开处刑",
        }],
        "risk_flags": [],
        "opportunities": ["让唐梨当场改口制造第二个笑点"],
    }, ensure_ascii=False)
    runtime = RecordingRoleRuntime(director_json)
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_director_adapter.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )

    with novel_role_scope(registry=reg, project_id="p1", chapter_index=1):
        guidance = NovelDirectorAdapter(reg).generate_guidance(
            "p1", _plan(), "", [], {}, [], [], "",
        )

    assert runtime.tasks[0].role == "director"
    assert runtime.tasks[0].session_key.startswith("task:")
    assert runtime.tasks[0].input_payload["response_format"] == "director_guidance_json"
    assert guidance.beat_details[0].beat_id == "b1"


def test_engine_binds_role_context_around_architect(monkeypatch, reg):
    from awp_rp_runtime_v3.contracts.novel_project import NovelProject

    reg.novel_project_store.create(NovelProject(project_id="p1", title="测试"))

    def planned(self, project_id, chapter_index, *args, **kwargs):
        del self, args, kwargs
        context = get_novel_role_context()
        assert context.project_id == project_id
        assert context.chapter_index == chapter_index
        return _plan()

    monkeypatch.setattr(NovelArchitectAdapter, "plan_chapter", planned)

    result = NovelEngine(reg).plan_chapter(project_id="p1", chapter_index=1)

    assert result.project_id == "p1"


def test_engine_binds_revision_context_around_director(monkeypatch, reg):
    def directed(self, project_id, chapter_plan, *args, **kwargs):
        del self, args, kwargs
        context = get_novel_role_context()
        assert context.project_id == project_id
        assert context.chapter_index == chapter_plan.chapter_index
        assert context.revision == 2
        return DirectorGuidance(guidance_id="g1")

    monkeypatch.setattr(NovelDirectorAdapter, "generate_guidance", directed)

    guidance = NovelEngine(reg)._call_director(
        "p1", _plan(), [], {}, "", revision=2,
    )

    assert guidance.guidance_id == "g1"
