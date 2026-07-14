from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_llm_factory import NovelLLMFactory
from awp_rp_runtime_v3.runtime.novel_pi_role_bridge import NovelPiRoleBridge
from awp_rp_runtime_v3.runtime.novel_role_runtime import (
    PiNovelRoleRuntime,
    novel_role_runtime_override,
)
from awp_rp_runtime_v3.runtime.session_runtime_registry import (
    SessionRuntimeStoreRegistry,
)
from awp_rp_runtime_v3.scripts import novel_cli
from awp_rp_runtime_v3.storage.sqlite.database import Database


pytestmark = pytest.mark.skipif(
    os.environ.get("NOVEL_PI_ROLE_E2E") != "1",
    reason="set NOVEL_PI_ROLE_E2E=1 to run the external-model Pi acceptance",
)


class RecordingRealPiBridge(NovelPiRoleBridge):
    def __init__(self, *args, **kwargs):
        self.roles: list[str] = []
        super().__init__(*args, **kwargs)

    def run(self, task, *, context, on_chunk=None):
        self.roles.append(task.role)
        return super().run(task, context=context, on_chunk=on_chunk)


def test_real_kimi_plan_write_audit_export_uses_pi_sessions(tmp_path):
    connection = NovelLLMFactory().get_pi_role_connection("writer")
    if "kimi" not in connection.model.lower():
        pytest.skip("configure NOVEL_LLM_MODEL=kimi-k2.6 for this acceptance")
    if not os.environ.get(connection.api_key_env):
        pytest.skip(f"missing external model key: {connection.api_key_env}")

    db_path = tmp_path / "novel.db"
    db = Database(str(db_path))
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    registry.novel_project_store.create(NovelProject(
        project_id="pi-e2e",
        title="告白事故测试",
        genre="校园恋爱喜剧",
        one_sentence_pitch="告白字幕失控后，两个互相甩锅的人被全校误认成情侣。",
        config={"novel_dir": str(tmp_path)},
    ))

    bridge = RecordingRealPiBridge(
        registry,
        project_dir=tmp_path,
        project_id="pi-e2e",
    )
    runtime = PiNovelRoleRuntime(bridge=bridge)
    engine = NovelEngine(registry)
    try:
        with novel_role_runtime_override(runtime):
            plan = engine.plan_chapter(
                project_id="pi-e2e",
                chapter_index=1,
                task_description=(
                    "首行就是礼堂告白字幕失控。唐梨为了掩盖真正的告白对象，"
                    "把普通学生陈默拽上台顶锅；以对话争夺和误判推动。"
                ),
            )
            draft = engine.write_chapter(project_id="pi-e2e", chapter_index=1)
            report = engine.audit_chapter(project_id="pi-e2e", chapter_index=1)
    finally:
        runtime.close()

    (tmp_path / ".novel_cli.json").write_text(json.dumps({
        "db_path": str(db_path), "project_id": "pi-e2e", "novel_dir": str(tmp_path),
    }, ensure_ascii=False), encoding="utf-8")
    novel_cli.cmd_export(SimpleNamespace(dir=str(tmp_path)))

    assert plan.scene_beats
    assert plan.target_chars == 2000
    assert draft.text.strip()
    assert len(draft.text) >= 1800
    assert report["chapter"] == 1
    assert {"architect", "director", "writer", "continuity_checker", "ledger_curator"}.issubset(
        set(bridge.roles)
    )
    assert (tmp_path / "export" / "chapter_01.txt").exists()
