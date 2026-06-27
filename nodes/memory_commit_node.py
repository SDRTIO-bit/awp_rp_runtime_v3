"""MemoryCommitNode — commits to active and RAG memory.

Input: accepted_text, state_update_proposal, round_snapshot
Output: active_memories, rag_memories
"""

from __future__ import annotations

from typing import Any


class MemoryCommitNode:
    """Commit to active and RAG memory."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "accepted_text": ("STRING",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
            "optional": {
                "state_update_proposal": ("STATE_UPDATE_PROPOSAL",),
            },
        }

    RETURN_TYPES = ("ACTIVE_MEMORIES", "RAG_RECALL")
    RETURN_NAMES = ("active_memories", "rag_memories")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        accepted_text: str,
        round_snapshot: dict[str, Any],
        state_update_proposal: dict[str, Any] | None = None,
    ) -> tuple[list, list]:
        """Commit to memory.

        V1: placeholder — returns current memories unchanged.
        """
        snapshot_data = round_snapshot
        return (
            snapshot_data.get("active_memories", []),
            snapshot_data.get("rag_recall", []),
        )
