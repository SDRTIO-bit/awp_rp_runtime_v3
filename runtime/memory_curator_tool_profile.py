"""Memory Curator Tool Profile — read-only tools for memory curation.

The Memory Curator can ONLY query existing data. It cannot write to any store.
Tool whitelist: accepted_turn_lookup, active_memory_lookup, rag_memory_lookup,
entity_alias_lookup, timeline_lookup, relationship_context_lookup.
"""

from __future__ import annotations

from ..contracts.agent_task_envelope import TaskBudget
from .agent_runtime_registry import AgentRoleSpec
from .tool_registry import ToolRegistry, ToolRegistration, V1_ALLOWED_TOOLS


# Tools the Memory Curator may use (all read-only, side-effect-free)
MEMORY_CURATOR_TOOLS = {
    "accepted_turn_lookup": ToolRegistration(
        tool_id="accepted_turn_lookup",
        description="Look up accepted turn records",
        allowed_roles=["memory-curator", "history-recall", "opportunity", "emotion-relationship", "continuity"],
        side_effect_free=True,
        can_write_state=False,
        can_write_memory=False,
        can_delegate=False,
    ),
    "active_memory_lookup": ToolRegistration(
        tool_id="active_memory_lookup",
        description="Look up active memory records",
        allowed_roles=["memory-curator", "history-recall", "opportunity", "emotion-relationship", "continuity"],
        side_effect_free=True,
        can_write_state=False,
        can_write_memory=False,
        can_delegate=False,
    ),
    "rag_memory_lookup": ToolRegistration(
        tool_id="rag_memory_lookup",
        description="Search RAG memory records",
        allowed_roles=["memory-curator", "history-recall", "opportunity", "emotion-relationship", "continuity"],
        side_effect_free=True,
        can_write_state=False,
        can_write_memory=False,
        can_delegate=False,
    ),
    "entity_alias_lookup": ToolRegistration(
        tool_id="entity_alias_lookup",
        description="Look up entity aliases",
        allowed_roles=["memory-curator", "history-recall", "opportunity", "emotion-relationship", "continuity"],
        side_effect_free=True,
        can_write_state=False,
        can_write_memory=False,
        can_delegate=False,
    ),
    "timeline_lookup": ToolRegistration(
        tool_id="timeline_lookup",
        description="Look up timeline events",
        allowed_roles=["memory-curator", "history-recall", "opportunity", "emotion-relationship", "continuity"],
        side_effect_free=True,
        can_write_state=False,
        can_write_memory=False,
        can_delegate=False,
    ),
    "relationship_context_lookup": ToolRegistration(
        tool_id="relationship_context_lookup",
        description="Look up relationship context",
        allowed_roles=["memory-curator", "history-recall", "opportunity", "emotion-relationship", "continuity"],
        side_effect_free=True,
        can_write_state=False,
        can_write_memory=False,
        can_delegate=False,
    ),
}


MEMORY_CURATOR_ROLE_SPEC = AgentRoleSpec(
    role_id="memory-curator",
    description="Memory Curator Agent — post-accept memory governance",
    allowed_suggestion_kinds=[],
    default_budget_tokens=1000,
    max_budget_tokens=2000,
    allowed_tools=[
        "accepted_turn_lookup", "active_memory_lookup", "rag_memory_lookup",
        "entity_alias_lookup", "timeline_lookup", "relationship_context_lookup",
    ],
    can_delegate=False,
    can_write_state=False,
    can_write_memory=False,
    can_generate_final_text=False,
)


def create_memory_curator_tool_registry() -> ToolRegistry:
    """Create a tool registry with only Memory Curator tools."""
    registry = ToolRegistry()
    for tool_id, reg in MEMORY_CURATOR_TOOLS.items():
        registry.register(reg)
    return registry
