"""ToolRegistry — explicit registration of allowed tools.

V1 only allows read-only, card-scoped, session-scoped tools.
No dynamic imports, no arbitrary code execution, no file/network access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolRegistration:
    """Registration entry for a single tool."""
    tool_id: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    allowed_roles: list[str] = field(default_factory=lambda: ["director"])
    allowed_scopes: list[str] = field(default_factory=lambda: ["card", "session"])
    default_timeout_ms: int = 30000
    max_timeout_ms: int = 60000
    default_token_budget: int = 1000
    max_token_budget: int = 5000
    side_effect_free: bool = True
    can_write_state: bool = False
    can_write_memory: bool = False
    can_delegate: bool = False


# V1 allowed tools — read-only, card/session scoped
V1_ALLOWED_TOOLS: dict[str, ToolRegistration] = {
    "worldbook_lookup": ToolRegistration(
        tool_id="worldbook_lookup",
        description="Look up worldbook entries for the current card/session",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"entries": {"type": "array"}}},
        allowed_roles=["director", "world-life", "opportunity", "history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "rag_memory_lookup": ToolRegistration(
        tool_id="rag_memory_lookup",
        description="Search RAG memory for relevant entries",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"hits": {"type": "array"}}},
        allowed_roles=["director", "world-life", "opportunity", "history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "entity_alias_lookup": ToolRegistration(
        tool_id="entity_alias_lookup",
        description="Look up entity aliases and references",
        input_schema={"type": "object", "properties": {"entity": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"aliases": {"type": "array"}}},
        allowed_roles=["director", "world-life", "opportunity", "history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "timeline_lookup": ToolRegistration(
        tool_id="timeline_lookup",
        description="Look up timeline events for the current card",
        input_schema={"type": "object", "properties": {"range": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"events": {"type": "array"}}},
        allowed_roles=["director", "world-life", "opportunity", "history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "relationship_context_lookup": ToolRegistration(
        tool_id="relationship_context_lookup",
        description="Look up relationship context between entities",
        input_schema={"type": "object", "properties": {"entities": {"type": "array"}}},
        output_schema={"type": "object", "properties": {"relationships": {"type": "array"}}},
        allowed_roles=["director", "world-life", "opportunity", "history-recall"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    # D1: History/Recall tools
    "accepted_turn_lookup": ToolRegistration(
        tool_id="accepted_turn_lookup",
        description="Look up accepted turn records by entity or query",
        input_schema={"type": "object", "properties": {
            "entity": {"type": "string"}, "query": {"type": "string"},
        }},
        output_schema={"type": "object", "properties": {"turns": {"type": "array"}}},
        allowed_roles=["history-recall", "world-life", "opportunity"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "active_memory_lookup": ToolRegistration(
        tool_id="active_memory_lookup",
        description="Look up active memory records by entity",
        input_schema={"type": "object", "properties": {"entity": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"memories": {"type": "array"}}},
        allowed_roles=["history-recall", "world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    # D3: World-Life tools
    "event_stage_lookup": ToolRegistration(
        tool_id="event_stage_lookup",
        description="Look up event stages and progress",
        input_schema={"type": "object", "properties": {"event_id": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"stages": {"type": "array"}}},
        allowed_roles=["world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "scene_context_lookup": ToolRegistration(
        tool_id="scene_context_lookup",
        description="Look up scene context and atmosphere",
        input_schema={"type": "object", "properties": {"location": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"context": {"type": "object"}}},
        allowed_roles=["world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
    "npc_context_lookup": ToolRegistration(
        tool_id="npc_context_lookup",
        description="Look up NPC context and current state",
        input_schema={"type": "object", "properties": {"npc_id": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"context": {"type": "object"}}},
        allowed_roles=["world-life"],
        allowed_scopes=["card", "session"],
        side_effect_free=True,
    ),
}


class ToolRegistry:
    """Explicit registry of allowed tools.

    Only registered tools can be executed.
    Unregistered tools are rejected.
    """

    def __init__(self, tools: dict[str, ToolRegistration] | None = None):
        self._tools: dict[str, ToolRegistration] = dict(tools or V1_ALLOWED_TOOLS)

    def is_registered(self, tool_id: str) -> bool:
        return tool_id in self._tools

    def get(self, tool_id: str) -> ToolRegistration | None:
        return self._tools.get(tool_id)

    def register(self, registration: ToolRegistration) -> None:
        """Register a new tool. Only for testing/extending."""
        self._tools[registration.tool_id] = registration

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def validate_tool_id(self, tool_id: str) -> tuple[bool, str]:
        if not self.is_registered(tool_id):
            return False, f"Tool '{tool_id}' is not registered. Allowed: {self.list_tools()}"
        return True, "Tool is registered"
