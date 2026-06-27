"""OpportunityQueryPlanner — generates tool queries for opportunity analysis.

Converts focus entities + opportunity domains into a list of tool queries.
Each query maps to a specific tool in the whitelist.
"""

from __future__ import annotations

from ..contracts.round_snapshot import RoundSnapshot


# Mapping from opportunity domain to tool
_DOMAIN_TO_TOOL: dict[str, str] = {
    "unresolved_thread": "timeline_lookup",
    "relationship_tension": "relationship_context_lookup",
    "scene_pressure": "worldbook_lookup",
    "player_intent_signal": "accepted_turn_lookup",
    "memory_promise": "active_memory_lookup",
    "memory_secret": "rag_memory_lookup",
    "memory_misunderstanding": "rag_memory_lookup",
    "memory_future_hook": "active_memory_lookup",
    "rag_thread": "rag_memory_lookup",
    "history_risk": "timeline_lookup",
    "narrative_opportunity": "worldbook_lookup",
    "pace_variation": "accepted_turn_lookup",
}


class OpportunityQueryPlanner:
    """Plans tool queries based on focus entities and opportunity domains.

    Each query is a dict with tool_id, input, and metadata.
    Queries are bounded by max_tool_calls.
    """

    def plan_queries(
        self,
        snapshot: RoundSnapshot,
        focus_entities: list[str],
        opportunity_domains: list[str],
        max_tool_calls: int = 7,
    ) -> list[dict]:
        """Generate a list of tool queries.

        Returns list of dicts: {tool_id, input, card_id, session_id, domain}
        """
        queries: list[dict] = []
        card_id = snapshot.card_id
        session_id = snapshot.session_id

        # For each entity × domain, generate a query
        for entity in focus_entities:
            for domain in opportunity_domains:
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
        if not queries and opportunity_domains:
            for domain in opportunity_domains:
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
        if tool_id == "timeline_lookup":
            return {"entity": entity, "range": "recent"}
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
