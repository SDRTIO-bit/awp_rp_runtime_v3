"""HistoryRecallQueryPlanner — generates structured tool queries from focus entities.

Converts focus entities + recall kinds into a list of tool queries.
Each query maps to a specific tool in the whitelist.
"""

from __future__ import annotations

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.recall_focus import RecallKind


# Mapping from RecallKind to tool
_RECALL_KIND_TO_TOOL: dict[RecallKind, str] = {
    RecallKind.EVENT_HISTORY: "timeline_lookup",
    RecallKind.TIMELINE_HISTORY: "timeline_lookup",
    RecallKind.UNRESOLVED_THREAD: "timeline_lookup",
    RecallKind.RELATIONSHIP_HISTORY: "relationship_context_lookup",
    RecallKind.IDENTITY_HISTORY: "entity_alias_lookup",
    RecallKind.PROMISE_HISTORY: "accepted_turn_lookup",
    RecallKind.SECRET_HISTORY: "rag_memory_lookup",
    RecallKind.CONFLICT_HISTORY: "rag_memory_lookup",
    RecallKind.LOCATION_HISTORY: "worldbook_lookup",
}


class HistoryRecallQueryPlanner:
    """Plans tool queries based on focus entities and recall kinds.

    Each query is a dict with tool_id, input, and metadata.
    Queries are bounded by max_tool_calls.
    """

    def plan_queries(
        self,
        snapshot: RoundSnapshot,
        focus_entities: list[str],
        recall_kinds: list[RecallKind],
        max_tool_calls: int = 7,
    ) -> list[dict]:
        """Generate a list of tool queries.

        Returns list of dicts: {tool_id, input, card_id, session_id, recall_kind}
        """
        queries: list[dict] = []
        card_id = snapshot.card_id
        session_id = snapshot.session_id

        # For each entity × recall kind, generate a query
        for entity in focus_entities:
            for kind in recall_kinds:
                if len(queries) >= max_tool_calls:
                    break

                tool_id = _RECALL_KIND_TO_TOOL.get(kind)
                if not tool_id:
                    continue

                query_input = self._build_query_input(tool_id, entity, snapshot)
                queries.append({
                    "tool_id": tool_id,
                    "input": query_input,
                    "card_id": card_id,
                    "session_id": session_id,
                    "recall_kind": kind.value,
                    "entity": entity,
                })

            if len(queries) >= max_tool_calls:
                break

        # If no entity-specific queries, generate general queries
        if not queries and recall_kinds:
            for kind in recall_kinds:
                if len(queries) >= max_tool_calls:
                    break
                tool_id = _RECALL_KIND_TO_TOOL.get(kind)
                if not tool_id:
                    continue
                queries.append({
                    "tool_id": tool_id,
                    "input": {"query": snapshot.player_input[:100]},
                    "card_id": card_id,
                    "session_id": session_id,
                    "recall_kind": kind.value,
                    "entity": "",
                })

        return queries[:max_tool_calls]

    def _build_query_input(
        self, tool_id: str, entity: str, snapshot: RoundSnapshot
    ) -> dict:
        """Build tool-specific input from entity and context."""
        if tool_id == "timeline_lookup":
            return {"entity": entity, "range": "all"}
        elif tool_id == "relationship_context_lookup":
            return {"entities": [entity, "player"]}
        elif tool_id == "entity_alias_lookup":
            return {"entity": entity}
        elif tool_id == "rag_memory_lookup":
            return {"query": entity, "entity_refs": [entity]}
        elif tool_id == "worldbook_lookup":
            return {"query": entity}
        elif tool_id == "accepted_turn_lookup":
            return {"entity": entity, "query": snapshot.player_input[:100]}
        elif tool_id == "active_memory_lookup":
            return {"entity": entity}
        else:
            return {"query": entity}
