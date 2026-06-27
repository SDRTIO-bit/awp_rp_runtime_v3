"""WorldLifeToolProfile — tool registrations for World-Life Agent.

All tools are read-only, side-effect-free, scoped to cardId + sessionId.
Default allowedTools = [] — only TaskEnvelope-authorized tools are available.
"""
from __future__ import annotations

from .tool_registry import ToolRegistration
from .agent_runtime_registry import AgentRoleSpec
from ..contracts.agent_suggestion import SuggestionKind


# World-Life specific tool registrations
WORLD_LIFE_TOOLS: dict[str, ToolRegistration] = {
    "worldbook_lookup": ToolRegistration(
        tool_id="worldbook_lookup",
        description="Look up worldbook entries (world-life)",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"entries": {"type": "array"}}},
        allowed_roles=["world-life", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "timeline_lookup": ToolRegistration(
        tool_id="timeline_lookup",
        description="Look up timeline events (world-life)",
        input_schema={"type": "object", "properties": {"range": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"events": {"type": "array"}}},
        allowed_roles=["world-life", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "relationship_context_lookup": ToolRegistration(
        tool_id="relationship_context_lookup",
        description="Look up relationship context (world-life)",
        input_schema={"type": "object", "properties": {"entities": {"type": "array"}}},
        output_schema={"type": "object", "properties": {"relationships": {"type": "array"}}},
        allowed_roles=["world-life", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "accepted_turn_lookup": ToolRegistration(
        tool_id="accepted_turn_lookup",
        description="Look up accepted turn records (world-life)",
        input_schema={"type": "object", "properties": {
            "entity": {"type": "string"}, "query": {"type": "string"},
        }},
        output_schema={"type": "object", "properties": {"turns": {"type": "array"}}},
        allowed_roles=["world-life", "opportunity", "history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "active_memory_lookup": ToolRegistration(
        tool_id="active_memory_lookup",
        description="Look up active memory records (world-life)",
        input_schema={"type": "object", "properties": {"entity": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"memories": {"type": "array"}}},
        allowed_roles=["world-life", "opportunity", "history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "rag_memory_lookup": ToolRegistration(
        tool_id="rag_memory_lookup",
        description="Search RAG memory for relevant entries (world-life)",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"hits": {"type": "array"}}},
        allowed_roles=["world-life", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "entity_alias_lookup": ToolRegistration(
        tool_id="entity_alias_lookup",
        description="Look up entity aliases and references (world-life)",
        input_schema={"type": "object", "properties": {"entity": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"aliases": {"type": "array"}}},
        allowed_roles=["world-life", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "event_stage_lookup": ToolRegistration(
        tool_id="event_stage_lookup",
        description="Look up event stages and progress (world-life)",
        input_schema={"type": "object", "properties": {"event_id": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"stages": {"type": "array"}}},
        allowed_roles=["world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "scene_context_lookup": ToolRegistration(
        tool_id="scene_context_lookup",
        description="Look up scene context and atmosphere (world-life)",
        input_schema={"type": "object", "properties": {"location": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"context": {"type": "object"}}},
        allowed_roles=["world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "npc_context_lookup": ToolRegistration(
        tool_id="npc_context_lookup",
        description="Look up NPC context and current state (world-life)",
        input_schema={"type": "object", "properties": {"npc_id": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"context": {"type": "object"}}},
        allowed_roles=["world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
}


# World-Life role spec (matches what's in BUILTIN_ROLES)
WORLD_LIFE_ROLE_SPEC = AgentRoleSpec(
    role_id="world-life",
    description="World-Life Agent — identifies world activity beyond protagonist's view",
    allowed_suggestion_kinds=[
        SuggestionKind.ENVIRONMENTAL_PRESSURE,
        SuggestionKind.WEATHER_OR_TIME_ATMOSPHERE,
        SuggestionKind.NPC_SIDE_TENSION,
        SuggestionKind.EVENT_STAGE_ECHO,
        SuggestionKind.LOCATION_LIFE_DETAIL,
        SuggestionKind.SOCIAL_BACKGROUND_SIGNAL,
        SuggestionKind.WORLDBOOK_RESONANCE,
        SuggestionKind.OFFSCREEN_CONSEQUENCE_HINT,
        SuggestionKind.AMBIENT_RUMOR_SIGNAL,
        SuggestionKind.WORLD_LIFE_WARNING,
    ],
    default_budget_tokens=1000,
    max_budget_tokens=2000,
    allowed_tools=list(WORLD_LIFE_TOOLS.keys()),
    can_delegate=False,
    can_write_state=False,
    can_write_memory=False,
    can_generate_final_text=False,
)


def create_world_life_tool_registry() -> ToolRegistry:
    """Create a ToolRegistry with world-life tools registered."""
    from .tool_registry import ToolRegistry, V1_ALLOWED_TOOLS
    tools = dict(V1_ALLOWED_TOOLS)
    tools.update(WORLD_LIFE_TOOLS)
    return ToolRegistry(tools)
