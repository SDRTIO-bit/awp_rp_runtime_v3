"""SubAgentLlmRunner — LLM-driven analysis for triggered D1-D5 sub-agents.

Each triggered sub-agent gets one cheap DeepSeek Flash call (thinking disabled)
to produce concrete, context-specific analysis text. This replaces the
generic rule-trigger summaries like "[D4-Emotion] active_memories>0" with
real insights the Writer can use.
"""

from __future__ import annotations

from typing import Any

from ..adapters.llm.deepseek_adapter import DeepSeekAdapter

# DeepSeek Flash model with thinking disabled
_FLASH_MODEL = "deepseek-v4-flash"
_EXTRA_DISABLE_THINKING = {"thinking": {"type": "disabled"}}


def _safe(text: Any, max_len: int = 200) -> str:
    return str(text or "")[:max_len]


def _build_prompt(role: str, snapshot: Any) -> str:
    """Build a focused analysis prompt for a given sub-agent role.

    Each prompt is tailored to the agent's purpose and includes
    relevant context (scene, recent turns, memories, worldbook).
    """
    # Extract scene context
    cs = getattr(snapshot, "card_state", None)
    scene = getattr(cs, "scene_state", None) if cs else None
    location = _safe(getattr(scene, "location", "") if scene else "")
    time_of_day = _safe(getattr(scene, "time_of_day", "") if scene else "")
    weather = _safe(getattr(scene, "weather", "") if scene else "")
    active_npcs = list(getattr(scene, "active_npcs", []) if scene else [])
    player_input = _safe(getattr(snapshot, "player_input", ""), 300)

    # Recent turns
    recent = getattr(snapshot, "recent_turn_records", []) or []
    turn_lines = []
    for t in recent[-3:]:
        idx = _safe(getattr(t, "turn_index", "?"))
        p = _safe(getattr(t, "player_input", ""), 150)
        w = _safe(getattr(t, "writer_output", ""), 150)
        turn_lines.append(f"Turn {idx} Player: {p}")
        turn_lines.append(f"Turn {idx} Writer: {w}")
    recent_block = "\n".join(turn_lines) if turn_lines else "(none)"

    # Active memories
    memories = getattr(snapshot, "active_memories", []) or []
    mem_lines = []
    for m in memories[:5]:
        if isinstance(m, dict):
            s = _safe(m.get("summary", "") or m.get("content", ""), 120)
            if s:
                mem_lines.append(f"- {s}")
    mem_block = "\n".join(mem_lines) if mem_lines else "(none)"

    # Active worldbook
    wb = getattr(snapshot, "active_worldbook_entries", []) or []
    wb_lines = []
    for e in wb[:3]:
        if isinstance(e, dict):
            title = _safe(e.get("title", "") or e.get("entry_id", ""), 50)
            content = _safe(e.get("content_excerpt", "") or "", 100)
            if title:
                wb_lines.append(f"- {title}: {content}")
    wb_block = "\n".join(wb_lines) if wb_lines else "(none)"

    npc_str = ", ".join(str(n) for n in active_npcs[:5]) if active_npcs else "(none)"

    # Shared context block
    context = (
        f"Scene: {location} | Time: {time_of_day} | Weather: {weather}\n"
        f"Active NPCs: {npc_str}\n"
        f"Player input: {player_input}\n\n"
        f"Recent turns:\n{recent_block}\n\n"
        f"Active memories:\n{mem_block}\n\n"
        f"Worldbook context:\n{wb_block}"
    )

    prompts = {
        "history_recall": (
            "You are a narrative consistency analyst. Based on the context below, "
            "identify any contradictions, unresolved threads, or character "
            "inconsistencies in the narrative so far.\n\n"
            f"{context}\n\n"
            "Respond with 2-3 sentences of specific analysis."
        ),
        "opportunity": (
            "You are a narrative opportunity scout. Based on the context below, "
            "identify dramatic moments, emotional beats, or plot hooks that "
            "could be developed in the next turn.\n\n"
            f"{context}\n\n"
            "Respond with 2-3 sentences of specific opportunities."
        ),
        "world_life": (
            "You are a world detail enhancer. Based on the context below, "
            "suggest sensory details, environmental changes, or world-building "
            "elements that could enrich the current scene.\n\n"
            f"{context}\n\n"
            "Respond with 2-3 sentences of specific suggestions."
        ),
        "emotion_relationship": (
            "You are an emotional dynamics analyst. Based on the context below, "
            "analyze the emotional state and relationship dynamics between "
            "the characters. What shifts or tensions are present?\n\n"
            f"{context}\n\n"
            "Respond with 2-3 sentences of specific analysis."
        ),
        "continuity": (
            "You are a factual continuity checker. Based on the context below, "
            "verify that names, relationships, locations, and events remain "
            "consistent. Flag any potential continuity issues.\n\n"
            f"{context}\n\n"
            "Respond with 2-3 sentences of specific analysis."
        ),
    }

    return prompts.get(role, f"Analyze the following RP context from a {role} perspective.\n\n{context}\n\nRespond with 2-3 sentences.")


def run_sub_agent_llm(
    role: str,
    snapshot: Any,
    adapter: DeepSeekAdapter,
    trace_id: str = "",
    turn_id: str = "",
    attempt_id: str = "",
) -> str:
    """Run one sub-agent LLM call.

    Args:
        role: Sub-agent role name (d1_history_recall, d2_opportunity, etc.)
        snapshot: RoundSnapshot with current RP state
        adapter: DeepSeekAdapter configured with flash model
        trace_id, turn_id, attempt_id: For provider receipts

    Returns:
        Analysis text (2-3 sentences), or empty string on failure.
    """
    prompt = _build_prompt(role, snapshot)

    text, receipt = adapter.generate_text(
        prompt,
        max_tokens=500,
        provider_role=f"sub_agent_{role}",
        model=_FLASH_MODEL,
        extra_body=_EXTRA_DISABLE_THINKING,
        trace_id=trace_id,
        turn_id=turn_id,
        attempt_id=attempt_id,
    )

    if not text.strip():
        return ""

    return text.strip()[:500]
