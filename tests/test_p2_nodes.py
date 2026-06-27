"""P2 Tests: ComfyUI nodes and workflow validation."""

import pytest
import json
from pathlib import Path


class TestP2NodeRegistration:
    """Test P2 nodes registered."""

    def test_p2_nodes_present(self):
        from awp_rp_runtime_v2.nodes import NODE_CLASS_MAPPINGS
        p2 = {"AWPV2Director", "AWPV2DelegationPlan", "AWPV2DynamicSubAgentPool",
              "AWPV2SuggestionMerge", "AWPV2WriterInputBundle", "AWPV2AgentTrace"}
        for name in p2:
            assert name in NODE_CLASS_MAPPINGS, f"Missing: {name}"

    def test_all_nodes_p1_plus_p2(self):
        from awp_rp_runtime_v2.nodes import NODE_CLASS_MAPPINGS
        # 8 P1 + 6 P2 + 8 M1 memory nodes
        assert len(NODE_CLASS_MAPPINGS) == 22

    def test_display_names_chinese(self):
        from awp_rp_runtime_v2.nodes import NODE_DISPLAY_NAME_MAPPINGS
        assert "AWP V2 叙事总控" in NODE_DISPLAY_NAME_MAPPINGS.values()
        assert "AWP V2 委派计划" in NODE_DISPLAY_NAME_MAPPINGS.values()


class TestP2WorkflowValidation:
    """Test 22: official workflow JSON structure."""

    def test_workflow_valid(self):
        wf_path = Path(__file__).parent.parent / "workflows" / "official_director_delegation_v2.json"
        assert wf_path.exists()
        with open(wf_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "nodes" in data
        node_types = {n["type"] for n in data["nodes"]}
        required = {"AWPV2CardStateInit", "AWPV2RoundSnapshot", "AWPV2Director",
                    "AWPV2DelegationPlan", "AWPV2DynamicSubAgentPool",
                    "AWPV2SuggestionMerge", "AWPV2WriterInputBundle", "AWPV2AgentTrace"}
        assert required.issubset(node_types)

    def test_workflow_links_valid(self):
        wf_path = Path(__file__).parent.parent / "workflows" / "official_director_delegation_v2.json"
        with open(wf_path, encoding="utf-8") as f:
            data = json.load(f)
        node_ids = {n["id"] for n in data["nodes"]}
        for link in data["links"]:
            assert link[1] in node_ids
            assert link[3] in node_ids
