from types import SimpleNamespace

from awp_rp_runtime_v2.contracts.round_snapshot import RoundSnapshot
from awp_rp_runtime_v2.runtime.sub_agent_llm_runner import _build_prompt


def test_sub_agent_prompt_includes_card_profile_context():
    snapshot = RoundSnapshot(
        player_input="continue",
        card_profile_context={
            "name": "SUBAGENT_PROFILE_NAME",
            "description": "SUBAGENT_PROFILE_DESCRIPTION",
            "personality": "SUBAGENT_PROFILE_PERSONALITY",
        },
    )

    prompt = _build_prompt("continuity", snapshot)

    assert "character_profile_lookup:" in prompt
    assert "SUBAGENT_PROFILE_NAME" in prompt
    assert "SUBAGENT_PROFILE_DESCRIPTION" in prompt
    assert "SUBAGENT_PROFILE_PERSONALITY" in prompt


def test_sub_agent_prompt_renders_recent_history_chronologically():
    snapshot = RoundSnapshot(
        player_input="continue",
        recent_turn_records=[
            SimpleNamespace(turn_index=4, player_input="p4", writer_output="w4"),
            SimpleNamespace(turn_index=3, player_input="p3", writer_output="w3"),
            SimpleNamespace(turn_index=2, player_input="p2", writer_output="w2"),
        ],
    )

    prompt = _build_prompt("history_recall", snapshot)
    tool_results = prompt.split("=== READ-ONLY TOOL RESULTS (volatile) ===", 1)[1]
    history = tool_results.split("accepted_turn_lookup:", 1)[1].split("active_memory_lookup:", 1)[0]

    assert history.index("Turn 2 Player") < history.index("Turn 3 Player")
    assert history.index("Turn 3 Player") < history.index("Turn 4 Player")
