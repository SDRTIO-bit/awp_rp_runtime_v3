"""ContinuityToolProfile — tool registrations for Continuity Agent.

All tools are read-only, side-effect-free, scoped to cardId + sessionId.
Default allowedTools = [] — only TaskEnvelope-authorized tools are available.
"""
from __future__ import annotations

from .tool_registry import ToolRegistration
from .agent_runtime_registry import AgentRoleSpec
from ..contracts.agent_suggestion import SuggestionKind


# Continuity specific tool registrations
CONTINUITY_TOOLS: dict[str, ToolRegistration] = {
    "accepted_turn_lookup": ToolRegistration(
        tool_id="accepted_turn_lookup",
        description="Look up accepted turn records (continuity)",
        input_schema={"type": "object", "properties": {
            "entity": {"type": "string"}, "query": {"type": "string"},
        }},
        output_schema={"type": "object", "properties": {"turns": {"type": "array"}}},
        allowed_roles=["continuity", "history-recall", "world-life", "opportunity"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "active_memory_lookup": ToolRegistration(
        tool_id="active_memory_lookup",
        description="Look up active memory records (continuity)",
        input_schema={"type": "object", "properties": {"entity": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"memories": {"type": "array"}}},
        allowed_roles=["continuity", "history-recall", "world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "rag_memory_lookup": ToolRegistration(
        tool_id="rag_memory_lookup",
        description="Search RAG memory for relevant entries (continuity)",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"hits": {"type": "array"}}},
        allowed_roles=["continuity", "world-life", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "timeline_lookup": ToolRegistration(
        tool_id="timeline_lookup",
        description="Look up timeline events (continuity)",
        input_schema={"type": "object", "properties": {"range": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"events": {"type": "array"}}},
        allowed_roles=["continuity", "world-life", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "relationship_context_lookup": ToolRegistration(
        tool_id="relationship_context_lookup",
        description="Look up relationship context (continuity)",
        input_schema={"type": "object", "properties": {"entities": {"type": "array"}}},
        output_schema={"type": "object", "properties": {"relationships": {"type": "array"}}},
        allowed_roles=["continuity", "world-life", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "worldbook_lookup": ToolRegistration(
        tool_id="worldbook_lookup",
        description="Look up worldbook entries (continuity)",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"entries": {"type": "array"}}},
        allowed_roles=["continuity", "world-life", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "entity_alias_lookup": ToolRegistration(
        tool_id="entity_alias_lookup",
        description="Look up entity aliases and references (continuity)",
        input_schema={"type": "object", "properties": {"entity": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"aliases": {"type": "array"}}},
        allowed_roles=["continuity", "world-life", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "event_stage_lookup": ToolRegistration(
        tool_id="event_stage_lookup",
        description="Look up event stages and progress (continuity)",
        input_schema={"type": "object", "properties": {"event_id": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"stages": {"type": "array"}}},
        allowed_roles=["continuity", "world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "scene_context_lookup": ToolRegistration(
        tool_id="scene_context_lookup",
        description="Look up scene context (continuity)",
        input_schema={"type": "object", "properties": {"location": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"context": {"type": "object"}}},
        allowed_roles=["continuity", "world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "npc_context_lookup": ToolRegistration(
        tool_id="npc_context_lookup",
        description="Look up NPC context (continuity)",
        input_schema={"type": "object", "properties": {"npc_id": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"context": {"type": "object"}}},
        allowed_roles=["continuity", "world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
}


# Continuity role spec
CONTINUITY_ROLE_SPEC = AgentRoleSpec(
    role_id="continuity",
    description="Continuity Agent — checks that confirmed facts do not conflict",
    allowed_suggestion_kinds=[
        SuggestionKind.CONTINUITY_FACT_CONSTRAINT,
        SuggestionKind.CONTINUITY_BLOCKING_RISK,
        SuggestionKind.CONTINUITY_TIMELINE_WARNING,
        SuggestionKind.CONTINUITY_IDENTITY_WARNING,
        SuggestionKind.CONTINUITY_LOCATION_WARNING,
        SuggestionKind.CONTINUITY_KNOWLEDGE_BOUNDARY_WARNING,
        SuggestionKind.CONTINUITY_SUGGESTION_CONFLICT,
        SuggestionKind.CONTINUITY_WRITER_CONSTRAINT,
        SuggestionKind.CONTINUITY_DIRECTOR_FOLLOWUP,
    ],
    default_budget_tokens=1000,
    max_budget_tokens=2000,
    allowed_tools=list(CONTINUITY_TOOLS.keys()),
    can_delegate=False,
    can_write_state=False,
    can_write_memory=False,
    can_generate_final_text=False,
)


def create_continuity_tool_registry():
    """Create a ToolRegistry with continuity tools registered."""
    from .tool_registry import ToolRegistry, V1_ALLOWED_TOOLS
    tools = dict(V1_ALLOWED_TOOLS)
    tools.update(CONTINUITY_TOOLS)
    return ToolRegistry(tools)
