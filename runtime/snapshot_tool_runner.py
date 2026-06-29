"""Read-only tool runner backed by the current RoundSnapshot."""

from __future__ import annotations

from typing import Any

from ..contracts.round_snapshot import RoundSnapshot


def _safe(text: Any, max_len: int = 300) -> str:
    return str(text or "")[:max_len]


class SnapshotToolRunner:
    """Executes Director read-only tools against the in-memory snapshot.

    This runner has no file, network, environment, database, state-write, or
    memory-write access. It only projects data already present in RoundSnapshot.
    """

    def run(
        self,
        tool_id: str,
        sanitized_input: dict[str, Any],
        snapshot: RoundSnapshot,
    ) -> dict[str, Any]:
        _ = sanitized_input
        if tool_id == "scene_context_lookup":
            return self._scene(snapshot)
        if tool_id == "worldbook_lookup":
            return self._worldbook(snapshot)
        if tool_id == "accepted_turn_lookup":
            return self._accepted_turns(snapshot)
        if tool_id == "active_memory_lookup":
            return self._active_memories(snapshot)
        if tool_id == "rag_memory_lookup":
            return self._rag_memories(snapshot)
        if tool_id == "timeline_lookup":
            return self._timeline(snapshot)
        if tool_id == "relationship_context_lookup":
            return self._relationships(snapshot)
        if tool_id == "entity_alias_lookup":
            return self._entities(snapshot)
        return {"result": "unsupported_tool", "source_refs": []}

    def _scene(self, snapshot: RoundSnapshot) -> dict[str, Any]:
        scene = snapshot.card_state.scene_state
        return {
            "context": {
                "location": scene.location,
                "time_of_day": scene.time_of_day,
                "weather": scene.weather,
                "active_npcs": list(scene.active_npcs),
                "description": _safe(scene.description, 400),
            },
            "source_refs": [f"scene:{snapshot.card_id}:{snapshot.session_id}"],
        }

    def _worldbook(self, snapshot: RoundSnapshot) -> dict[str, Any]:
        entries = []
        for entry in (snapshot.active_worldbook_entries or [])[:12]:
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("entry_id", "") or entry.get("id", "")
            entries.append({
                "entry_id": entry_id,
                "title": _safe(entry.get("title", "") or entry_id, 80),
                "content_excerpt": _safe(entry.get("content_excerpt", "") or entry.get("content", ""), 300),
                "activation_reason": _safe(entry.get("activation_reason", ""), 80),
            })
        return {
            "entries": entries,
            "source_refs": [f"worldbook:{snapshot.card_id}:{snapshot.session_id}"],
        }

    def _accepted_turns(self, snapshot: RoundSnapshot) -> dict[str, Any]:
        turns = []
        for turn in (snapshot.recent_turn_records or [])[-5:]:
            turns.append({
                "turn_id": turn.turn_id,
                "turn_index": turn.turn_index,
                "player_input": _safe(turn.player_input, 180),
                "writer_output": _safe(turn.writer_output, 240),
            })
        return {
            "turns": turns,
            "source_refs": [f"accepted_turn:{snapshot.card_id}:{snapshot.session_id}"],
        }

    def _active_memories(self, snapshot: RoundSnapshot) -> dict[str, Any]:
        memories = []
        for memory in (snapshot.active_memories or [])[:10]:
            if isinstance(memory, dict):
                memories.append({
                    "memory_id": memory.get("memory_id", ""),
                    "kind": memory.get("kind", ""),
                    "summary": _safe(memory.get("summary", "") or memory.get("content", ""), 220),
                    "status": memory.get("status", ""),
                })
        return {
            "memories": memories,
            "source_refs": [f"active_memory:{snapshot.card_id}:{snapshot.session_id}"],
        }

    def _rag_memories(self, snapshot: RoundSnapshot) -> dict[str, Any]:
        hits = []
        for memory in (snapshot.rag_recall or [])[:10]:
            if isinstance(memory, dict):
                hits.append({
                    "memory_id": memory.get("memory_id", ""),
                    "summary": _safe(memory.get("summary", "") or memory.get("content", ""), 220),
                    "score": memory.get("score", memory.get("relevance_score", 0)),
                })
        return {
            "hits": hits,
            "source_refs": [f"rag:{snapshot.card_id}:{snapshot.session_id}"],
        }

    def _timeline(self, snapshot: RoundSnapshot) -> dict[str, Any]:
        events = []
        for turn in (snapshot.recent_turn_records or [])[-5:]:
            events.append({
                "turn": turn.turn_index,
                "event": _safe(turn.writer_output, 180),
            })
        return {
            "events": events,
            "source_refs": [f"timeline:{snapshot.card_id}:{snapshot.session_id}"],
        }

    def _relationships(self, snapshot: RoundSnapshot) -> dict[str, Any]:
        relationships = []
        for memory in (snapshot.active_memories or [])[:10]:
            if isinstance(memory, dict) and str(memory.get("kind", "")).lower() in {
                "relationship", "emotion", "promise",
            }:
                relationships.append({
                    "memory_id": memory.get("memory_id", ""),
                    "summary": _safe(memory.get("summary", "") or memory.get("content", ""), 220),
                })
        return {
            "relationships": relationships,
            "source_refs": [f"relationship:{snapshot.card_id}:{snapshot.session_id}"],
        }

    def _entities(self, snapshot: RoundSnapshot) -> dict[str, Any]:
        scene = snapshot.card_state.scene_state
        aliases = list(scene.active_npcs)
        aliases.extend(snapshot.card_state.variables.keys())
        return {
            "aliases": sorted(str(item) for item in aliases if item)[:20],
            "source_refs": [f"entity:{snapshot.card_id}:{snapshot.session_id}"],
        }
