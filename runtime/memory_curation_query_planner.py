"""MemoryCurationQueryPlanner — plans what the Memory Curator should look at.

Deterministic planner that identifies which active memories may need updates,
which entities are relevant, and what domains to curate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.memory_curation_trigger_diagnostics import (
    MemoryCurationTriggerDiagnostics,
)
from ..contracts.turn_record import TurnRecord
from ..contracts.round_snapshot import RoundSnapshot


@dataclass(frozen=True)
class CurationQueryPlan:
    """Plan for what the Memory Curator should examine."""
    focus_entities: list[str] = field(default_factory=list)
    focus_kinds: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    should_check_active_for_resolution: bool = False
    should_check_rag_for_staleness: bool = False
    max_active_candidates: int = 5
    max_rag_candidates: int = 5


class MemoryCurationQueryPlanner:
    """Deterministic query planner for Memory Curator.

    Examines the trigger diagnostics, turn record, and snapshot to decide
    what the curator should focus on. No LLM involved.
    """

    def plan(
        self,
        trigger_diagnostics: MemoryCurationTriggerDiagnostics,
        turn_record: TurnRecord,
        snapshot: RoundSnapshot,
    ) -> CurationQueryPlan:
        """Plan what to curate based on trigger signals."""
        focus_entities: list[str] = []
        focus_kinds: list[str] = []
        domains = list(trigger_diagnostics.curation_domains)

        accepted_output = turn_record.writer_output or ""
        player_input = turn_record.player_input or ""

        # Extract entities from current active memories
        for mem in snapshot.active_memories:
            for ref in mem.get("entity_refs", []):
                if ref not in focus_entities:
                    focus_entities.append(ref)

        # Extract entities from recent turns
        for tr in snapshot.recent_turn_records[:3]:
            if hasattr(tr, "player_input"):
                # Can't extract entities from raw text without NLP,
                # but we can use entity_refs if present
                pass

        # Determine focus kinds based on domains
        if "promise" in domains:
            focus_kinds.append("promise")
        if "secret" in domains:
            focus_kinds.append("secret")
        if "relationship" in domains:
            focus_kinds.append("relationship_shift")
        if "goal" in domains:
            focus_kinds.append("player_goal")
        if "event_stage" in domains:
            focus_kinds.append("scene_pressure")
        if "active_memory_update" in domains:
            focus_kinds.append("unresolved_thread")

        # Deduplicate
        focus_kinds = list(dict.fromkeys(focus_kinds))
        focus_entities = list(dict.fromkeys(focus_entities))

        # Should we check active memories for resolution?
        should_check_active = (
            "active_memory_update" in domains
            or "active_memory_pressure" in domains
            or len(snapshot.active_memories) >= 10
        )

        # Should we check RAG for staleness?
        should_check_rag = (
            "card_state_change" in domains
            or len(snapshot.rag_recall) >= 3
        )

        return CurationQueryPlan(
            focus_entities=focus_entities,
            focus_kinds=focus_kinds,
            domains=domains,
            should_check_active_for_resolution=should_check_active,
            should_check_rag_for_staleness=should_check_rag,
            max_active_candidates=trigger_diagnostics.max_active_candidates,
            max_rag_candidates=trigger_diagnostics.max_rag_candidates,
        )
