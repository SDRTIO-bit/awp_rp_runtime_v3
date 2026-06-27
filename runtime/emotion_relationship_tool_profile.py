"""EmotionRelationshipToolProfile — tool registrations for Emotion/Relationship Agent.

All tools are read-only, side-effect-free, scoped to cardId + sessionId.
Default allowedTools = [] — only TaskEnvelope-authorized tools are available.
"""

from __future__ import annotations

from .tool_registry import ToolRegistration
from .agent_runtime_registry import AgentRoleSpec
from ..contracts.agent_suggestion import SuggestionKind


# Emotion/Relationship specific tool registrations (same 7 tools as opportunity)
EMOTION_RELATIONSHIP_TOOLS: dict[str, ToolRegistration] = {
    "rag_memory_lookup": ToolRegistration(
        tool_id="rag_memory_lookup",
        description="Search RAG memory for relevant entries (emotion-relationship)",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"hits": {"type": "array"}}},
        allowed_roles=["emotion-relationship", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "entity_alias_lookup": ToolRegistration(
        tool_id="entity_alias_lookup",
        description="Look up entity aliases and references (emotion-relationship)",
        input_schema={"type": "object", "properties": {"entity": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"aliases": {"type": "array"}}},
        allowed_roles=["emotion-relationship", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "timeline_lookup": ToolRegistration(
        tool_id="timeline_lookup",
        description="Look up timeline events (emotion-relationship)",
        input_schema={"type": "object", "properties": {"range": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"events": {"type": "array"}}},
        allowed_roles=["emotion-relationship", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "relationship_context_lookup": ToolRegistration(
        tool_id="relationship_context_lookup",
        description="Look up relationship context (emotion-relationship)",
        input_schema={"type": "object", "properties": {"entities": {"type": "array"}}},
        output_schema={"type": "object", "properties": {"relationships": {"type": "array"}}},
        allowed_roles=["emotion-relationship", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "worldbook_lookup": ToolRegistration(
        tool_id="worldbook_lookup",
        description="Look up worldbook entries (emotion-relationship)",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"entries": {"type": "array"}}},
        allowed_roles=["emotion-relationship", "opportunity", "history-recall", "director"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "accepted_turn_lookup": ToolRegistration(
        tool_id="accepted_turn_lookup",
        description="Look up accepted turn records (emotion-relationship)",
        input_schema={"type": "object", "properties": {
            "entity": {"type": "string"}, "query": {"type": "string"},
        }},
        output_schema={"type": "object", "properties": {"turns": {"type": "array"}}},
        allowed_roles=["emotion-relationship", "opportunity", "history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "active_memory_lookup": ToolRegistration(
        tool_id="active_memory_lookup",
        description="Look up active memory records (emotion-relationship)",
        input_schema={"type": "object", "properties": {"entity": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"memories": {"type": "array"}}},
        allowed_roles=["emotion-relationship", "opportunity", "history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
}


# Emotion/Relationship role spec
EMOTION_RELATIONSHIP_ROLE_SPEC = AgentRoleSpec(
    role_id="emotion-relationship",
    description="Emotion/Relationship Agent — identifies relational dynamics and emotional undercurrents",
    allowed_suggestion_kinds=[
        SuggestionKind.ER_TRUST_TENSION,
        SuggestionKind.ER_GUARDEDNESS,
        SuggestionKind.ER_EMOTIONAL_RESIDUE,
        SuggestionKind.ER_UNRESOLVED_HURT,
        SuggestionKind.ER_PROMISE_PRESSURE,
        SuggestionKind.ER_MISUNDERSTANDING_SIGNAL,
        SuggestionKind.ER_JEALOUSY_RISK,
        SuggestionKind.ER_AFFECTION_RESTRAINT,
        SuggestionKind.ER_CONFLICT_DEESCALATION,
        SuggestionKind.ER_RELATIONSHIP_BOUNDARY,
        SuggestionKind.ER_SUBTEXT_OPPORTUNITY,
        SuggestionKind.ER_WARNING,
    ],
    default_budget_tokens=1000,
    max_budget_tokens=2000,
    allowed_tools=list(EMOTION_RELATIONSHIP_TOOLS.keys()),
    can_delegate=False,
    can_write_state=False,
    can_write_memory=False,
    can_generate_final_text=False,
)


def create_emotion_relationship_tool_registry() -> ToolRegistry:
    """Create a ToolRegistry with emotion/relationship tools registered."""
    from .tool_registry import ToolRegistry, V1_ALLOWED_TOOLS
    tools = dict(V1_ALLOWED_TOOLS)
    tools.update(EMOTION_RELATIONSHIP_TOOLS)
    return ToolRegistry(tools)
