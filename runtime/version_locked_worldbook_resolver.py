"""Resolve version-locked worldbook content for a bound session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..contracts.card_definition import CardDefinition
from ..contracts.first_turn_context import SessionBoundWorldbookRetrievalResult
from ..storage.card_import_interfaces import CardDefinitionStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ResolverBudget:
    max_constant_entries: int = 2
    max_selective_entries: int = 3
    max_entry_chars: int = 400
    max_total_chars: int = 1800


class VersionLockedWorldbookResolver:
    """Reads worldbook content from the exact card version bound to a session."""

    def __init__(
        self,
        definition_store: CardDefinitionStore,
        budget: ResolverBudget | None = None,
    ):
        self._defs = definition_store
        self._budget = budget or ResolverBudget()

    def resolve(
        self,
        *,
        binding: Any,
        worldbook_binding: Any,
        opening_record: Any,
        player_input: str,
        recent_turns: list[Any],
    ) -> dict[str, Any]:
        card = self._load_bound_definition(binding, worldbook_binding)
        catalog = card.worldbook_catalog or []
        chunks = card.worldbook_chunks or []

        candidate_entry_ids: list[str] = []
        activated_entry_ids: list[str] = []
        rejected: dict[str, str] = {}
        deferred_ids: list[str] = []
        disabled_ids: list[str] = []
        budget_dropped: list[str] = []
        branch_selections: list[dict[str, Any]] = []
        chunk_parent_ids: list[str] = []
        activated_content: list[dict[str, Any]] = []

        catalog_by_id = {entry.get("entry_id", ""): entry for entry in catalog}
        content_seen: set[tuple[str, int, str]] = set()
        total_budget = 0
        constant_count = 0
        selective_count = 0

        opening_text = getattr(opening_record, "safe_display_content", "") or ""
        recent_text = " ".join(
            f"{getattr(turn, 'player_input', '')} {getattr(turn, 'writer_output', '')}"
            for turn in recent_turns[:5]
        )
        match_haystack = f"{player_input} {opening_text} {recent_text}".lower()

        binding_entries = list(getattr(worldbook_binding, "entries", []) or [])
        binding_entries.sort(
            key=lambda item: (
                0 if item.get("constant", False) else 1,
                -int(catalog_by_id.get(item.get("entry_id", ""), {}).get("priority", 0) or 0),
                int(catalog_by_id.get(item.get("entry_id", ""), {}).get("source_order", 0) or 0),
            )
        )

        for raw_binding_entry in binding_entries:
            entry_id = raw_binding_entry.get("entry_id", "")
            if not entry_id:
                continue
            candidate_entry_ids.append(entry_id)

            entry = catalog_by_id.get(entry_id)
            if not entry:
                rejected[entry_id] = "missing_from_bound_card_definition"
                continue

            if not raw_binding_entry.get("enabled", True):
                disabled_ids.append(entry_id)
                rejected[entry_id] = "disabled"
                continue

            if raw_binding_entry.get("activation_status") == "deferred":
                deferred_ids.append(entry_id)
                rejected[entry_id] = "deferred"
                continue

            unsupported_reason = self._unsupported_reason(entry)
            if unsupported_reason:
                rejected[entry_id] = unsupported_reason
                continue

            entry_kind = "constant" if entry.get("constant", False) else "selective" if entry.get("selective", False) else "constant"
            matched_keywords: list[str] = []
            activation_reason = "constant"
            if entry_kind == "selective":
                matched_keywords = [
                    key for key in entry.get("keys", [])
                    if isinstance(key, str) and key.lower() in match_haystack
                ]
                if not matched_keywords:
                    rejected[entry_id] = "ignored_with_reason:no_primary_keyword_match"
                    continue
                activation_reason = "matched_primary_keywords"

            if entry_kind == "constant" and constant_count >= self._budget.max_constant_entries:
                budget_dropped.append(entry_id)
                rejected[entry_id] = "budget_constant_cap"
                continue

            if entry_kind == "selective" and selective_count >= self._budget.max_selective_entries:
                budget_dropped.append(entry_id)
                rejected[entry_id] = "budget_selective_cap"
                continue

            excerpt, used_chunks = self._build_excerpt(entry, chunks)
            excerpt = excerpt[: self._budget.max_entry_chars]
            projected_total = total_budget + len(excerpt)
            if projected_total > self._budget.max_total_chars:
                budget_dropped.append(entry_id)
                rejected[entry_id] = "budget_total_cap"
                continue

            content_key = (
                entry_id,
                int(entry.get("source_uid", -1) or -1),
                excerpt,
            )
            if content_key in content_seen:
                rejected[entry_id] = "ignored_with_reason:duplicate_excerpt"
                continue
            content_seen.add(content_key)

            activated_entry_ids.append(entry_id)
            total_budget = projected_total
            if entry_kind == "constant":
                constant_count += 1
            else:
                selective_count += 1

            if used_chunks:
                chunk_parent_ids.append(entry_id)

            activated_content.append({
                "entry_id": entry_id,
                "title": entry.get("title", ""),
                "content_excerpt": excerpt,
                "activation_reason": activation_reason,
                "matched_keywords": matched_keywords,
                "matched_condition": "",
                "source_entry_id": entry_id,
                "source_hash": binding.source_hash,
                "budget_rank": len(activated_content) + 1,
                "entry_kind": entry_kind,
            })
            branch_selections.append({
                "entry_id": entry_id,
                "selected": True,
                "reason": activation_reason,
            })

        result = SessionBoundWorldbookRetrievalResult(
            retrieval_id=f"wbr_{binding.session_id}_{binding.card_version}",
            session_id=binding.session_id,
            worldbook_binding_id=worldbook_binding.worldbook_binding_id,
            candidate_entry_ids=candidate_entry_ids,
            activated_entry_ids=activated_entry_ids,
            rejected_entry_ids_with_reasons=rejected,
            deferred_entry_ids=deferred_ids,
            disabled_entry_ids=disabled_ids,
            budget_dropped_entry_ids=budget_dropped,
            branch_selections=branch_selections,
            chunk_parent_entry_ids=chunk_parent_ids,
            activated_content=activated_content,
            total_budget_used=total_budget,
            max_budget=self._budget.max_total_chars,
            created_at=_now(),
        )
        return result.to_dict()

    def _load_bound_definition(self, binding: Any, worldbook_binding: Any) -> CardDefinition:
        card = self._defs.load(binding.logical_card_id, binding.card_version)
        if card is None:
            raise ValueError(
                f"Missing bound CardDefinition for "
                f"{binding.logical_card_id} v{binding.card_version} ({binding.source_hash})"
            )
        if card.source_hash != binding.source_hash or card.source_hash != worldbook_binding.source_hash:
            raise ValueError(
                f"Bound CardDefinition source hash mismatch for "
                f"{binding.logical_card_id} v{binding.card_version}: "
                f"expected {binding.source_hash}, got {card.source_hash}"
            )
        return card

    def _build_excerpt(
        self,
        entry: dict[str, Any],
        chunks: list[dict[str, Any]],
    ) -> tuple[str, bool]:
        entry_id = entry.get("entry_id", "")
        entry_chunks = [
            chunk for chunk in chunks
            if chunk.get("parent_entry_id") == entry_id
        ]
        if entry_chunks:
            ordered = sorted(entry_chunks, key=lambda chunk: int(chunk.get("ordinal", 0)))
            excerpt = "\n".join(
                str(chunk.get("content", "")).strip()
                for chunk in ordered
                if str(chunk.get("content", "")).strip()
            ).strip()
            if excerpt:
                return excerpt, True
        return str(entry.get("content", "")).strip(), False

    def _unsupported_reason(self, entry: dict[str, Any]) -> str:
        if entry.get("secondary_keys"):
            return "ignored_with_reason:secondary_keys_unsupported_in_p0"
        activation_raw = entry.get("activation_raw", {})
        if not isinstance(activation_raw, dict):
            return ""
        unsupported_fields = [
            key
            for key in (
                "position",
                "probability",
                "useProbability",
                "recursive",
                "delayUntilRecursion",
                "group",
                "groupOverride",
                "groupWeight",
                "preventGroupRecursion",
                "sticky",
                "cooldown",
                "delay",
            )
            if key in activation_raw
        ]
        if unsupported_fields:
            return "ignored_with_reason:unsupported_activation_fields:" + ",".join(unsupported_fields)
        if entry.get("selective") and not entry.get("keys"):
            return "ignored_with_reason:no_primary_keyword_match"
        return ""
