import os

import pytest

from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_brain import BrainCallbacks
from awp_rp_runtime_v3.runtime.novel_pi_bridge import NovelPiBridge
from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from awp_rp_runtime_v3.storage.sqlite.database import Database


@pytest.mark.skipif(
    os.environ.get("NOVEL_PI_E2E") != "1",
    reason="requires configured Pi model provider",
)
def test_pi_status_turn_is_read_only(tmp_path):
    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    registry.novel_project_store.create(NovelProject(project_id="p1", title="测试小说"))
    bridge = NovelPiBridge(
        registry,
        BrainCallbacks(),
        project_dir=tmp_path,
        project_id="p1",
    )
    try:
        assert bridge.handle_message("查看当前项目状态")
    finally:
        bridge.close()

    assert registry.novel_chapter_draft_store.load_latest("ch-p1-1") is None
