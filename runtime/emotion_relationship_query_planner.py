"""EmotionRelationshipQueryPlanner — generates tool queries for emotion/relationship analysis.

Converts focus entities + emotion/relationship domains into a list of tool queries.
Each query maps to a specific tool in the whitelist.
"""

from __future__ import annotations

from ..contracts.round_snapshot import RoundSnapshot


# Mapping from emotion/relationship domain to tool
_DOMAIN_TO_TOOL: dict[str, str] = {
    "relationship_action": "relationship_context_lookup",
    "emotion_signal": "accepted_turn_lookup",
    "memory_relationship_shift": "active_memory_lookup",
    "memory_misunderstanding": "rag_memory_lookup",
    "memory_promise": "active_memory_lookup",
    "memory_secret": "rag_memory_lookup",
    "memory_emotional_trend": "active_memory_lookup",
    "relationship_tension": "relationship_context_lookup",
    "history_relationship": "timeline_lookup",
    "rag_relationship": "rag_memory_lookup",
}


class EmotionRelationshipQueryPlanner:
    """Plans tool queries based on focus entities and emotion/relationship domains.

    Each query is a dict with tool_id, input, and metadata.
    Queries are bounded by max_tool_calls.
    """

    def plan_queries(
        self,
        snapshot: RoundSnapshot,
        focus_entities: list[str],
        emotion_relationship_domains: list[str],
        max_tool_calls: int = 7,
    ) -> list[dict]:
        """Generate a list of tool queries.

        Returns list of dicts: {tool_id, input, card_id, session_id, domain}
        """
        queries: list[dict] = []
        card_id = snapshot.card_id
        session_id = snapshot.session_id

        # For each entity x domain, generate a query
        for entity in focus_entities:
            for domain in emotion_relationship_domains:
                if len(queries) >= max_tool_calls:
                    break

                tool_id = _DOMAIN_TO_TOOL.get(domain)
                if not tool_id:
                    continue

                query_input = self._build_query_input(tool_id, entity, snapshot)
                queries.append({
                    "tool_id": tool_id,
                    "input": query_input,
                    "card_id": card_id,
                    "session_id": session_id,
                    "domain": domain,
                    "entity": entity,
                })

            if len(queries) >= max_tool_calls:
                break

        # If no entity-specific queries, generate general queries
        if not queries and emotion_relationship_domains:
            for domain in emotion_relationship_domains:
                if len(queries) >= max_tool_calls:
                    break
                tool_id = _DOMAIN_TO_TOOL.get(domain)
                if not tool_id:
                    continue
                queries.append({
                    "tool_id": tool_id,
                    "input": {"query": snapshot.player_input[:100]},
                    "card_id": card_id,
                    "session_id": session_id,
                    "domain": domain,
                    "entity": "",
                })

        return queries[:max_tool_calls]

    def _build_query_input(
        self, tool_id: str, entity: str, snapshot: RoundSnapshot
    ) -> dict:
        """Build tool-specific input from entity and context."""
        if tool_id == "relationship_context_lookup":
            return {"entities": [entity, "player"]}
        elif tool_id == "timeline_lookup":
            return {"entity": entity, "range": "recent"}
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
