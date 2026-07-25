import json
from pathlib import Path

from awp_rp_runtime_v3.adapters.llm.model_profile_registry import ModelProfileRegistry
from awp_rp_runtime_v3.runtime.default_model_profiles import profile_ids_from_env


def test_default_rp_profiles_use_deepseek_v4_pro(monkeypatch):
    monkeypatch.delenv("AWP_DIRECTOR_PROFILE_ID", raising=False)
    monkeypatch.delenv("AWP_WRITER_PROFILE_ID", raising=False)

    director_id, writer_id = profile_ids_from_env()

    assert ModelProfileRegistry.resolve(director_id).model == "deepseek-v4-pro"
    assert ModelProfileRegistry.resolve(writer_id).model == "deepseek-v4-pro"


def test_api_workflows_default_to_deepseek_v4_pro():
    workflow_dir = Path(__file__).resolve().parents[1] / "workflows" / "api"

    for path in workflow_dir.glob("*.api.json"):
        workflow = json.loads(path.read_text(encoding="utf-8"))
        profile_ids = [
            node["inputs"].get("director_profile_id")
            for node in workflow.values()
            if isinstance(node, dict) and isinstance(node.get("inputs"), dict)
        ]
        assert all(
            profile_id in (None, "deepseek-v4-pro-director")
            for profile_id in profile_ids
        ), path.name


def test_playable_workflows_default_to_deepseek_v4_pro():
    workflow_dir = Path(__file__).resolve().parents[1] / "workflows" / "awp_v2_playable_workflows"

    for path in workflow_dir.glob("*.json"):
        assert "deepseek-v4-flash" not in path.read_text(encoding="utf-8"), path.name
