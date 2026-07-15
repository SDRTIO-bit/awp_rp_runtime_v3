"""Runtime wiring tests for autonomous novel NPC planning."""

from __future__ import annotations

import pytest

from awp_rp_runtime_v3.contracts.novel_profile import default_autonomous_profile
from awp_rp_runtime_v3.runtime.novel_profile_compiler import NovelProfileCompiler


def test_profile_is_nonempty_and_role_layered() -> None:
    p = default_autonomous_profile()
    assert p.narrative["language"] == "zh-CN"
    assert p.agent_contracts["npc_planner"]["response_format"] == "npc_agenda_json"
    planner = NovelProfileCompiler().compile_for(
        "npc_planner",
        p,
        world_rules=["守恒"],
        history="已接受",
        scene="雨夜",
        character_context={},
    )
    writer = NovelProfileCompiler().compile_for(
        "writer",
        p,
        world_rules=["守恒"],
        history="已接受",
        scene="雨夜",
        character_context={},
    )
    assert planner["world_rules"] == ["守恒"]
    assert "world_rules" not in writer
