"""ContinuityQueryPlanner — generates tool queries for continuity analysis.

Converts focus entities, locations, and domains into a list of tool queries.
Each query maps to a specific tool in the whitelist.
"""
from __future__ import annotations

from ..contracts.round_snapshot import RoundSnapshot


# Mapping from continuity domain to tool
_DOMAIN_TO_TOOL: dict[str, str] = {
    "continuity_reference": "accepted_turn_lookup",
    "entrance_exit": "npc_context_lookup",
    "time_change": "timeline_lookup",
    "location_change": "scene_context_lookup",
    "knowledge_boundary": "active_memory_lookup",
    "promise": "active_memory_lookup",
    "event_stage": "event_stage_lookup",
    "director_continuity": "accepted_turn_lookup",
    "memory_conflict": "active_memory_lookup",
    "rag_multiple": "rag_memory_lookup",
    "recent_entrance_exit": "accepted_turn_lookup",
    "director_push": "timeline_lookup",
}


class ContinuityQueryPlanner:
    """Plans tool queries based on focus entities, locations, and domains.

    Each query is a dict with tool_id, input, and metadata.
    Queries are bounded by max_tool_calls.
    """

    def plan_queries(
        self,
        snapshot: RoundSnapshot,
        focus_entities: list[str],
        focus_locations: list[str],
        continuity_domains: list[str],
        max_tool_calls: int = 10,
    ) -> list[dict]:
        """Generate a list of tool queries.

        Returns list of dicts: {tool_id, input, card_id, session_id, domain}
        """
        queries: list[dict] = []
        card_id = snapshot.card_id
        session_id = snapshot.session_id

        # For each entity × domain, generate a query
        for entity in focus_entities:
            for domain in continuity_domains:
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

        # For each location × domain, generate a query
        for location in focus_locations:
            for domain in continuity_domains:
                if len(queries) >= max_tool_calls:
                    break

                tool_id = _DOMAIN_TO_TOOL.get(domain)
                if not tool_id:
                    continue

                query_input = self._build_query_input(tool_id, location, snapshot)
                queries.append({
                    "tool_id": tool_id,
                    "input": query_input,
                    "card_id": card_id,
                    "session_id": session_id,
                    "domain": domain,
                    "location": location,
                })

            if len(queries) >= max_tool_calls:
                break

        # If no entity/location-specific queries, generate general queries
        if not queries and continuity_domains:
            for domain in continuity_domains:
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
        self, tool_id: str, entity_or_location: str, snapshot: RoundSnapshot,
    ) -> dict:
        """Build tool-specific input from entity/location and context."""
        if tool_id == "scene_context_lookup":
            return {"location": entity_or_location}
        elif tool_id == "npc_context_lookup":
            return {"npc_id": entity_or_location}
        elif tool_id == "event_stage_lookup":
            return {"event_id": entity_or_location}
        elif tool_id == "worldbook_lookup":
            return {"query": entity_or_location}
        elif tool_id == "timeline_lookup":
            return {"entity": entity_or_location, "range": "recent"}
        elif tool_id == "relationship_context_lookup":
            return {"entities": [entity_or_location, "player"]}
        elif tool_id == "entity_alias_lookup":
            return {"entity": entity_or_location}
        elif tool_id == "rag_memory_lookup":
            return {"query": entity_or_location, "entity_refs": [entity_or_location]}
        elif tool_id == "accepted_turn_lookup":
            return {"entity": entity_or_location, "query": snapshot.player_input[:100]}
        elif tool_id == "active_memory_lookup":
            return {"entity": entity_or_location}
        else:
            return {"query": entity_or_location}
