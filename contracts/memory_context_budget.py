"""MemoryContextBudget — deterministic budget decision for a round's memory context.

schemaId: awp.rp.memory-context-budget.v1

When the context budget is insufficient, low-priority content is cut in this
fixed order (L1 full turns are cut LAST, and never truncated):
  1. low-priority RAG
  2. worldbook expansions
  3. tool results
  4. optional subagent evidence
The 5th full TurnRecord is never silently truncated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.memory-context-budget.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BudgetDecision:
    """Records what was kept and what was trimmed for a round's memory context."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    l1_turns_used: int = 0
    l1_turns_available: int = 0
    l1_truncated: bool = False  # must always be False — full turns never truncated

    active_memories_used: int = 0
    active_memories_available: int = 0

    rag_used: int = 0
    rag_available: int = 0

    worldbook_used: int = 0
    worldbook_available: int = 0

    trimmed: list[dict[str, Any]] = field(default_factory=list)
    # Each trimmed entry: {"layer": "rag|worldbook|tool|subagent", "reason": "...", "count": n}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "l1_turns_used": self.l1_turns_used,
            "l1_turns_available": self.l1_turns_available,
            "l1_truncated": self.l1_truncated,
            "active_memories_used": self.active_memories_used,
            "active_memories_available": self.active_memories_available,
            "rag_used": self.rag_used,
            "rag_available": self.rag_available,
            "worldbook_used": self.worldbook_used,
            "worldbook_available": self.worldbook_available,
            "trimmed": list(self.trimmed),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BudgetDecision:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            l1_turns_used=data.get("l1_turns_used", 0),
            l1_turns_available=data.get("l1_turns_available", 0),
            l1_truncated=data.get("l1_truncated", False),
            active_memories_used=data.get("active_memories_used", 0),
            active_memories_available=data.get("active_memories_available", 0),
            rag_used=data.get("rag_used", 0),
            rag_available=data.get("rag_available", 0),
            worldbook_used=data.get("worldbook_used", 0),
            worldbook_available=data.get("worldbook_available", 0),
            trimmed=list(data.get("trimmed", [])),
        )


# Alias used by RoundSnapshot / assembler.
MemoryContextBudget = BudgetDecision
