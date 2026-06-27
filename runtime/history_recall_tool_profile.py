"""HistoryRecallToolProfile — tool registrations for History/Recall Agent.

All tools are read-only, side-effect-free, scoped to cardId + sessionId.
Default allowedTools = [] — only TaskEnvelope-authorized tools are available.
"""

from __future__ import annotations

from .tool_registry import ToolRegistration
from .agent_runtime_registry import AgentRoleSpec
from ..contracts.agent_suggestion import SuggestionKind


# History-recall-specific tool registrations
HISTORY_RECALL_TOOLS: dict[str, ToolRegistration] = {
    "rag_memory_lookup": ToolRegistration(
        tool_id="rag_memory_lookup",
        description="Search RAG memory for relevant entries (history recall)",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"hits": {"type": "array"}}},
        allowed_roles=["history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "entity_alias_lookup": ToolRegistration(
        tool_id="entity_alias_lookup",
        description="Look up entity aliases and references (history recall)",
        input_schema={"type": "object", "properties": {"entity": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"aliases": {"type": "array"}}},
        allowed_roles=["history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "timeline_lookup": ToolRegistration(
        tool_id="timeline_lookup",
        description="Look up timeline events (history recall)",
        input_schema={"type": "object", "properties": {"range": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"events": {"type": "array"}}},
        allowed_roles=["history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "relationship_context_lookup": ToolRegistration(
        tool_id="relationship_context_lookup",
        description="Look up relationship context (history recall)",
        input_schema={"type": "object", "properties": {"entities": {"type": "array"}}},
        output_schema={"type": "object", "properties": {"relationships": {"type": "array"}}},
        allowed_roles=["history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "worldbook_lookup": ToolRegistration(
        tool_id="worldbook_lookup",
        description="Look up worldbook entries (history recall)",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"entries": {"type": "array"}}},
        allowed_roles=["history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "accepted_turn_lookup": ToolRegistration(
        tool_id="accepted_turn_lookup",
        description="Look up accepted turn records by entity or query",
        input_schema={"type": "object", "properties": {
            "entity": {"type": "string"}, "query": {"type": "string"},
        }},
        output_schema={"type": "object", "properties": {"turns": {"type": "array"}}},
        allowed_roles=["history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "active_memory_lookup": ToolRegistration(
        tool_id="active_memory_lookup",
        description="Look up active memory records by entity",
        input_schema={"type": "object", "properties": {"entity": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"memories": {"type": "array"}}},
        allowed_roles=["history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
}


# History-recall role spec (matches what's in BUILTIN_ROLES)
HISTORY_RECALL_ROLE_SPEC = AgentRoleSpec(
    role_id="history-recall",
    description="History/Recall sub-agent for historical evidence and continuity",
    allowed_suggestion_kinds=[
        SuggestionKind.CONTINUITY_ISSUE,
        SuggestionKind.CHARACTER_CONSISTENCY,
        SuggestionKind.HISTORICAL_CONFLICT,
        SuggestionKind.IDENTITY_CLARIFICATION,
        SuggestionKind.TIMELINE_WARNING,
        SuggestionKind.WRITER_CONSTRAINT,
        SuggestionKind.DIRECTOR_FOLLOWUP,
    ],
    default_budget_tokens=1000,
    max_budget_tokens=2000,
    allowed_tools=list(HISTORY_RECALL_TOOLS.keys()),
    can_delegate=False,
    can_write_state=False,
    can_write_memory=False,
    can_generate_final_text=False,
)


def create_history_recall_tool_registry() -> ToolRegistry:
    """Create a ToolRegistry with history-recall tools registered."""
    from .tool_registry import ToolRegistry, V1_ALLOWED_TOOLS
    tools = dict(V1_ALLOWED_TOOLS)
    tools.update(HISTORY_RECALL_TOOLS)
    return ToolRegistry(tools)
