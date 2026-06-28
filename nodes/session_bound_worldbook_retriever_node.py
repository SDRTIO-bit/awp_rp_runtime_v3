"""AWPV2SessionBoundWorldbookRetriever -- retrieves worldbook entries from Session binding."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.first_turn_context import SessionBoundWorldbookRetrievalResult


class AWPV2SessionBoundWorldbookRetriever:
    """Retrieve worldbook entries from the current Session's WorldbookBinding.

    Only reads from the bound entries. Never reads from global card library,
    other sessions, or disabled entries. Constant entries activate within budget.
    Selective entries are deferred. Disabled entries are excluded.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "worldbook_binding": ("WORLDBOOK_BINDING",),
                "card_definition": ("CARD_DEFINITION",),
                "session_id": ("STRING", {"default": ""}),
            },
            "optional": {
                "max_budget": ("INT", {"default": 4000, "min": 100, "max": 20000}),
            },
        }

    RETURN_TYPES = ("WORLDBOOK_RETRIEVAL_RESULT",)
    RETURN_NAMES = ("worldbook_retrieval",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2/First Turn"
    OUTPUT_NODE = False

    def execute(
        self,
        worldbook_binding: dict[str, Any],
        card_definition: dict[str, Any],
        session_id: str,
        max_budget: int = 4000,
    ) -> tuple[dict]:
        now = datetime.now(timezone.utc).isoformat()
        binding_id = worldbook_binding.get("worldbook_binding_id", "")
        bound_ids = set(worldbook_binding.get("bound_entry_ids", []))
        disabled_ids = list(worldbook_binding.get("disabled_entry_ids", []))
        deferred_ids = list(worldbook_binding.get("deferred_entry_ids", []))

        # Get entries from card definition's worldbook catalog
        catalog = card_definition.get("worldbook_catalog", [])
        chunks = card_definition.get("worldbook_chunks", [])

        candidates = []
        activated = []
        activated_content = []
        rejected = {}
        budget_dropped = []
        used_budget = 0
        branch_selections = []
        chunk_parents = []

        for entry in catalog:
            entry_id = entry.get("entry_id", "")
            if not entry_id:
                continue

            candidates.append(entry_id)

            # Only process entries that are in the bound set
            if entry_id not in bound_ids:
                if entry_id in disabled_ids:
                    rejected[entry_id] = "disabled"
                elif entry_id in deferred_ids:
                    rejected[entry_id] = "deferred_selective"
                else:
                    rejected[entry_id] = "not_in_binding"
                continue

            content = entry.get("content", "")
            content_len = len(content)

            # Budget check
            if used_budget + content_len > max_budget:
                budget_dropped.append(entry_id)
                rejected[entry_id] = "budget_exceeded"
                continue

            # Activate
            activated.append(entry_id)
            activated_content.append({
                "entry_id": entry_id,
                "title": entry.get("title", ""),
                "content": content,
                "keys": entry.get("keys", []),
                "priority": entry.get("priority", 50),
                "constant": entry.get("constant", False),
            })
            used_budget += content_len

            # Collect chunk references
            for chunk in chunks:
                if chunk.get("parent_entry_id") == entry_id:
                    chunk_parents.append(entry_id)

        result = SessionBoundWorldbookRetrievalResult(
            retrieval_id=f"wbr_{session_id}_{binding_id[:8]}",
            session_id=session_id,
            worldbook_binding_id=binding_id,
            candidate_entry_ids=candidates,
            activated_entry_ids=activated,
            rejected_entry_ids_with_reasons=rejected,
            deferred_entry_ids=deferred_ids,
            disabled_entry_ids=disabled_ids,
            budget_dropped_entry_ids=budget_dropped,
            branch_selections=branch_selections,
            chunk_parent_entry_ids=chunk_parents,
            activated_content=activated_content,
            total_budget_used=used_budget,
            max_budget=max_budget,
            created_at=now,
        )
        return (result.to_dict(),)


NODE_CLASS_MAPPINGS = {
    "AWPV2SessionBoundWorldbookRetriever": AWPV2SessionBoundWorldbookRetriever,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2SessionBoundWorldbookRetriever": "AWP V2 会话绑定世界书检索",
}
