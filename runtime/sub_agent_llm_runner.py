"""LLM-driven analysis for triggered D1-D5 sub-agents."""

from __future__ import annotations

from typing import Any

from ..adapters.llm.deepseek_adapter import DeepSeekAdapter


_FLASH_MODEL = "deepseek-v4-flash"
_EXTRA_DISABLE_THINKING = {"thinking": {"type": "disabled"}}

_STABLE_SUB_AGENT_CONTRACT = """You are a read-only analysis sub-agent for an interactive roleplay runtime.
Keep this fixed contract above volatile turn data so provider prefix caching can be reused across D1-D5 calls.

=== STABLE SUB-AGENT CONTRACT ===
You never write final player-visible prose. You produce concise analysis for the Writer.
Use only evidence from the supplied tool results and turn packet. Do not invent unseen facts.
Do not change CardState, memory, files, network, environment variables, or database records.
Do not delegate to other agents.
Return 2-3 concrete sentences. Mention uncertainty when evidence is thin.

=== AVAILABLE READ-ONLY TOOLS ===
accepted_turn_lookup: Reads recent accepted player/writer turns for continuity.
active_memory_lookup: Reads active high-priority memories for promises, relationships, and facts.
rag_memory_lookup: Reads recalled long-term memory snippets relevant to this turn.
worldbook_lookup: Reads active worldbook entries selected by the resolver.
scene_context_lookup: Reads current scene fields such as location, time, weather, and NPCs.
npc_context_lookup: Reads currently active NPC references when present.
relationship_context_lookup: Reads relationship and emotion cues from memories and recent turns.
timeline_lookup: Reads recent event order from accepted turns.
character_profile_lookup: Reads immutable character profile fields from the imported card.

=== ROLE CATALOG ===
history_recall: Find contradictions, unresolved threads, callbacks, and continuity-sensitive facts.
opportunity: Find dramatic moments, emotional beats, plot hooks, and useful next-turn openings.
world_life: Find sensory details, environmental reactions, NPC background actions, and world texture.
emotion_relationship: Analyze emotional state, relationship pressure, subtext, and interpersonal shifts.
continuity: Check names, relationships, locations, object ownership, event order, and constraints.

Use the selected role from the volatile turn packet below."""


def _safe(text: Any, max_len: int | None = None) -> str:
    value = str(text or "")
    if max_len is None:
        return value
    return value[:max_len]


def _build_tool_result_block(snapshot: Any) -> str:
    """Build deterministic read-only tool results for the sub-agent prompt."""
    profile = getattr(snapshot, "card_profile_context", {}) or {}
    profile_block = _format_card_profile(profile)

    cs = getattr(snapshot, "card_state", None)
    scene = getattr(cs, "scene_state", None) if cs else None
    location = _safe(getattr(scene, "location", "") if scene else "")
    time_of_day = _safe(getattr(scene, "time_of_day", "") if scene else "")
    weather = _safe(getattr(scene, "weather", "") if scene else "")
    active_npcs = list(getattr(scene, "active_npcs", []) if scene else [])
    npc_str = ", ".join(str(n) for n in active_npcs) if active_npcs else "(none)"

    recent = getattr(snapshot, "recent_turn_records", []) or []
    turn_lines: list[str] = []
    recent_limit = int(getattr(snapshot, "max_turn_history", 5) or 5)
    for turn in _chronological_turns(recent[:recent_limit]):
        idx = _safe(getattr(turn, "turn_index", "?"))
        player = _safe(getattr(turn, "player_input", ""))
        writer = _safe(getattr(turn, "writer_output", ""))
        turn_lines.append(f"Turn {idx} Player: {player}")
        turn_lines.append(f"Turn {idx} Writer: {writer}")
    recent_block = "\n".join(turn_lines) if turn_lines else "(none)"

    memories = getattr(snapshot, "active_memories", []) or []
    memory_lines: list[str] = []
    for memory in memories:
        if isinstance(memory, dict):
            summary = _safe(memory.get("summary", "") or memory.get("content", ""))
            if summary:
                memory_lines.append(f"- {summary}")
    memory_block = "\n".join(memory_lines) if memory_lines else "(none)"

    rag = getattr(snapshot, "rag_recall", []) or []
    rag_lines: list[str] = []
    for item in rag:
        if isinstance(item, dict):
            summary = _safe(item.get("summary", "") or item.get("content", ""))
            if summary:
                rag_lines.append(f"- {summary}")
    rag_block = "\n".join(rag_lines) if rag_lines else "(none)"

    worldbook = getattr(snapshot, "active_worldbook_entries", []) or []
    worldbook_lines: list[str] = []
    for entry in worldbook:
        if isinstance(entry, dict):
            title = _safe(entry.get("title", "") or entry.get("entry_id", ""))
            content = _safe(entry.get("content_excerpt", "") or entry.get("content", ""))
            if title:
                worldbook_lines.append(f"- {title}: {content}")
    worldbook_block = "\n".join(worldbook_lines) if worldbook_lines else "(none)"

    return (
        "character_profile_lookup:\n"
        f"{profile_block or '(none)'}\n\n"
        "scene_context_lookup:\n"
        f"Scene: {location} | Time: {time_of_day} | Weather: {weather}\n"
        f"Active NPCs: {npc_str}\n\n"
        "accepted_turn_lookup:\n"
        f"{recent_block}\n\n"
        "active_memory_lookup:\n"
        f"{memory_block}\n\n"
        "rag_memory_lookup:\n"
        f"{rag_block}\n\n"
        "worldbook_lookup:\n"
        f"{worldbook_block}"
    )


def _format_card_profile(profile: dict[str, Any]) -> str:
    if not isinstance(profile, dict) or not profile:
        return ""
    fields = (
        ("name", "Name"),
        ("description", "Description"),
        ("personality", "Personality"),
        ("scenario", "Scenario"),
        ("mes_example", "Example messages"),
        ("creator_notes", "Creator notes"),
    )
    lines: list[str] = []
    for key, label in fields:
        value = _safe(profile.get(key, ""))
        if value.strip():
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _chronological_turns(turns: list[Any]) -> list[Any]:
    def key(turn: Any) -> tuple[int, str]:
        raw_index = getattr(turn, "turn_index", 0)
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            index = 0
        return (index, str(getattr(turn, "turn_id", "") or ""))

    return sorted(turns, key=key)


def _role_instruction(role: str) -> str:
    instructions = {
        "history_recall": "Focus on contradictions, unresolved threads, callbacks, and character consistency.",
        "opportunity": "Focus on dramatic opportunities, emotional beats, and plot hooks for the next turn.",
        "world_life": "Focus on sensory details, environmental reactions, NPC background action, and world texture.",
        "emotion_relationship": "Focus on emotional state, relationship pressure, subtext, and interpersonal shifts.",
        "continuity": "Focus on names, relationships, locations, object ownership, event order, and hard constraints.",
    }
    return instructions.get(role, f"Analyze the turn from the {role} perspective.")


def _build_prompt(role: str, snapshot: Any) -> str:
    """Build a cache-friendly focused analysis prompt for one sub-agent role."""
    player_input = _safe(getattr(snapshot, "player_input", ""))
    return (
        f"{_STABLE_SUB_AGENT_CONTRACT}\n\n"
        "=== TURN PACKET (volatile; changes every turn) ===\n"
        f"Selected role: {role}\n"
        f"Role instruction: {_role_instruction(role)}\n"
        f"Player input: {player_input}\n\n"
        "=== READ-ONLY TOOL RESULTS (volatile) ===\n"
        f"{_build_tool_result_block(snapshot)}\n\n"
        "Now produce 2-3 sentences of specific analysis for the selected role."
    )


def run_sub_agent_llm(
    role: str,
    snapshot: Any,
    adapter: DeepSeekAdapter,
    trace_id: str = "",
    turn_id: str = "",
    attempt_id: str = "",
) -> str:
    """Run one sub-agent LLM call."""
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

    return text.strip()
