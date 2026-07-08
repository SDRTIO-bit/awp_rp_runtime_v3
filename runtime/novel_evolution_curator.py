"""NovelEvolutionCurator — novel-mode ledger + memory evolution.

Adapts the RP memory stores to novel projects by mapping:
  card_id = project_id
  session_id = novel:{project_id}
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from ..contracts.active_memory import ActiveMemoryKind, ActiveMemoryRecord
from ..contracts.memory_commit_plan import MemoryCommitPlan, MemoryCommitRequest
from ..contracts.novel_chapter import ChapterPlan
from ..contracts.novel_character import NovelCharacter
from ..contracts.novel_ledger import LedgerItem
from ..contracts.quality_decision import QualityDecision
from ..contracts.rag_memory import RagMemoryRecord
from .active_memory_commit_runtime import ActiveMemoryCommitRuntime
from .novel_ledger_curator import NovelLedgerCurator
from .rag_memory_commit_runtime import RagMemoryCommitRuntime


def novel_memory_scope(project_id: str) -> tuple[str, str]:
    return project_id, f"novel:{project_id}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class NovelEvolutionCurator:
    """Updates novel continuity, active memory, RAG memory and character state."""

    def __init__(
        self,
        registry,
        ledger_curator: NovelLedgerCurator | None = None,
        use_ledger_llm: bool | None = None,
    ):
        self._registry = registry
        self._ledger_curator = ledger_curator or NovelLedgerCurator(registry)
        self._use_ledger_llm = (
            use_ledger_llm
            if use_ledger_llm is not None
            else os.environ.get("NOVEL_EVOLUTION_USE_LEDGER_LLM") == "1"
        )

    def curate(
        self,
        *,
        chapter_text: str,
        chapter_plan: ChapterPlan,
        current_ledger_items: list[LedgerItem],
        characters: list[NovelCharacter],
        quality_decision: QualityDecision | None,
    ) -> dict[str, Any]:
        ledger_result = self._curate_ledger(
            chapter_text, chapter_plan, current_ledger_items
        )
        ledger_updates = []
        for item in ledger_result.get("ledger_updates", []):
            if isinstance(item, LedgerItem):
                normalized = self._normalize_ledger_item(item, chapter_plan)
            elif isinstance(item, dict):
                normalized = self._normalize_ledger_item(
                    LedgerItem.from_dict(item), chapter_plan
                )
            else:
                normalized = None
            if normalized is not None:
                ledger_updates.append(normalized)
        ledger_updates.extend(
            self._deterministic_ledger_updates(
                chapter_text, chapter_plan, current_ledger_items, ledger_updates
            )
        )

        for item in ledger_updates:
            self._registry.novel_ledger_store.upsert(item)
        for item_id in ledger_result.get("ledger_resolves", []):
            self._registry.novel_ledger_store.resolve(item_id)

        active_result = None
        rag_result = None
        updated_character_ids: list[str] = []
        if quality_decision is not None and quality_decision.is_accepted():
            plan = self._build_memory_commit_plan(
                chapter_text=chapter_text,
                chapter_plan=chapter_plan,
                characters=characters,
                quality_decision=quality_decision,
            )
            request = self._build_commit_request(plan)
            active_result = ActiveMemoryCommitRuntime(
                self._registry.active_memory_store
            ).commit_request(request, quality_decision)
            rag_result = RagMemoryCommitRuntime(
                self._registry.rag_memory_store
            ).commit_request(request, quality_decision)
            updated_character_ids = self._update_character_states(
                chapter_text, chapter_plan, characters
            )

        return {
            "ledger_updates": [i.to_dict() for i in ledger_updates],
            "ledger_resolves": list(ledger_result.get("ledger_resolves", [])),
            "active_commit": active_result.to_dict() if active_result else None,
            "rag_commit": rag_result.to_dict() if rag_result else None,
            "updated_character_ids": updated_character_ids,
        }

    def _curate_ledger(
        self,
        chapter_text: str,
        chapter_plan: ChapterPlan,
        current_ledger_items: list[LedgerItem],
    ) -> dict[str, Any]:
        if not self._use_ledger_llm:
            return {}
        try:
            result = self._ledger_curator.curate(
                chapter_text, chapter_plan, current_ledger_items
            )
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    def _normalize_ledger_item(
        self, item: LedgerItem, chapter_plan: ChapterPlan
    ) -> LedgerItem | None:
        if not item.section or not item.content:
            return None
        project_id = item.project_id or chapter_plan.project_id
        source_chapter = item.source_chapter or chapter_plan.chapter_index
        entity = item.entity or chapter_plan.title or f"第{chapter_plan.chapter_index}章"
        item_id = item.item_id or (
            f"novel-ledger-{project_id}-ch{source_chapter}-"
            f"{item.section}-{_hash(entity + item.content)}"
        )
        return replace(
            item,
            item_id=item_id,
            project_id=project_id,
            entity=entity,
            source_chapter=source_chapter,
            created_at=item.created_at or _now(),
            updated_at=item.updated_at or _now(),
        )

    def _deterministic_ledger_updates(
        self,
        chapter_text: str,
        chapter_plan: ChapterPlan,
        current_ledger_items: list[LedgerItem],
        proposed_updates: list[LedgerItem],
    ) -> list[LedgerItem]:
        existing_keys = {
            (i.section, i.entity, i.content)
            for i in list(current_ledger_items) + list(proposed_updates)
        }
        updates: list[LedgerItem] = []

        def add(section: str, entity: str, content: str) -> None:
            key = (section, entity, content)
            if key in existing_keys:
                return
            existing_keys.add(key)
            updates.append(
                LedgerItem(
                    item_id=(
                        f"novel-ledger-{chapter_plan.project_id}-"
                        f"ch{chapter_plan.chapter_index}-{section}-{_hash(content)}"
                    ),
                    project_id=chapter_plan.project_id,
                    section=section,
                    entity=entity,
                    content=content,
                    status="active",
                    source_chapter=chapter_plan.chapter_index,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )

        entity = chapter_plan.title or f"第{chapter_plan.chapter_index}章"
        if any(k in chapter_text for k in ("伏笔", "悬念", "秘密")):
            add("foreshadowing", entity, self._summary(chapter_text, 80))
        if "规则" in chapter_text:
            add("world_rules", entity, self._summary(chapter_text, 80))
        if any(k in chapter_text for k in ("承诺", "未解决", "回来", "验证")):
            add("open_threads", entity, self._summary(chapter_text, 80))
        return updates

    def _build_memory_commit_plan(
        self,
        *,
        chapter_text: str,
        chapter_plan: ChapterPlan,
        characters: list[NovelCharacter],
        quality_decision: QualityDecision,
    ) -> MemoryCommitPlan:
        card_id, session_id = novel_memory_scope(chapter_plan.project_id)
        turn_id = self._turn_id(chapter_plan)
        memory_commit_id = f"novel-mc-{_hash(turn_id + chapter_text)}"
        entity_refs = [c.name for c in characters if c.name and c.name in chapter_text]

        active_entries = self._active_entries(
            chapter_text, chapter_plan, card_id, session_id, turn_id, entity_refs
        )
        rag_entry = RagMemoryRecord(
            memory_id=f"novel-rag-{_hash(turn_id)}",
            card_id=card_id,
            session_id=session_id,
            scope="session",
            content=chapter_text[:1200],
            summary=self._summary(chapter_text, 80),
            entity_refs=entity_refs,
            event_tags=["novel_chapter", f"chapter_{chapter_plan.chapter_index}"],
            source_turn_ids=[turn_id],
            source_card_state_revision=chapter_plan.chapter_index,
            importance=0.7,
            confidence=0.8,
            provenance=f"novel_evolution:{turn_id}",
            evidence=[turn_id],
            created_at=_now(),
            updated_at=_now(),
        )

        return MemoryCommitPlan(
            turn_id=turn_id,
            card_id=card_id,
            session_id=session_id,
            trace_id=quality_decision.trace_id,
            expected_card_state_revision=chapter_plan.chapter_index,
            memory_commit_id=memory_commit_id,
            idempotency_key=f"{turn_id}:novel-evolution",
            quality_decision_ref=quality_decision.trace_id,
            new_active_entries=active_entries,
            new_rag_entries=[rag_entry],
            write_reasons=["novel_chapter_evolution"],
        )

    def _active_entries(
        self,
        chapter_text: str,
        chapter_plan: ChapterPlan,
        card_id: str,
        session_id: str,
        turn_id: str,
        entity_refs: list[str],
    ) -> list[ActiveMemoryRecord]:
        patterns = [
            ("承诺", ActiveMemoryKind.PROMISE.value, 0.85),
            ("秘密", ActiveMemoryKind.SECRET.value, 0.85),
            ("伏笔", ActiveMemoryKind.FUTURE_HOOK.value, 0.8),
            ("悬念", ActiveMemoryKind.FUTURE_HOOK.value, 0.8),
            ("规则", ActiveMemoryKind.PERSISTENT_FACT_REFERENCE.value, 0.75),
            ("未解决", ActiveMemoryKind.UNRESOLVED_THREAD.value, 0.75),
        ]
        entries: list[ActiveMemoryRecord] = []
        seen_kinds: set[str] = set()
        for keyword, kind, importance in patterns:
            if keyword not in chapter_text or kind in seen_kinds:
                continue
            seen_kinds.add(kind)
            summary = self._active_summary(chapter_text, keyword)
            entries.append(
                ActiveMemoryRecord(
                    memory_id=f"novel-am-{_hash(turn_id + kind)}",
                    card_id=card_id,
                    session_id=session_id,
                    summary=summary,
                    kind=kind,
                    entity_refs=entity_refs,
                    source_turn_ids=[turn_id],
                    source_card_state_revision=chapter_plan.chapter_index,
                    importance=importance,
                    confidence=0.8,
                    status="active",
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
        if not entries and chapter_text.strip():
            entries.append(
                ActiveMemoryRecord(
                    memory_id=f"novel-am-{_hash(turn_id + 'chapter')}",
                    card_id=card_id,
                    session_id=session_id,
                    summary=self._active_summary(chapter_text, ""),
                    kind=ActiveMemoryKind.UNRESOLVED_THREAD.value,
                    entity_refs=entity_refs,
                    source_turn_ids=[turn_id],
                    source_card_state_revision=chapter_plan.chapter_index,
                    importance=0.5,
                    confidence=0.7,
                    status="active",
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
        return entries[:3]

    def _build_commit_request(self, plan: MemoryCommitPlan) -> MemoryCommitRequest:
        return MemoryCommitRequest(
            plan=plan,
            card_id=plan.card_id,
            session_id=plan.session_id,
            turn_id=plan.turn_id,
            trace_id=plan.trace_id,
            memory_commit_id=plan.memory_commit_id,
            idempotency_key=plan.idempotency_key,
            quality_decision_ref=plan.quality_decision_ref,
            expected_card_state_revision=plan.expected_card_state_revision,
            card_state_commit_success=True,
            turn_record_commit_success=True,
        )

    def _update_character_states(
        self,
        chapter_text: str,
        chapter_plan: ChapterPlan,
        characters: list[NovelCharacter],
    ) -> list[str]:
        updated: list[str] = []
        for character in characters:
            if not character.name or character.name not in chapter_text:
                continue
            current_state = dict(character.current_state)
            current_state["last_chapter_index"] = chapter_plan.chapter_index
            current_state["recent_summary"] = self._summary(chapter_text, 100)
            current_state["updated_by"] = "novel_evolution_curator"
            self._registry.novel_character_store.save(
                replace(character, current_state=current_state, updated_at=_now())
            )
            updated.append(character.character_id)
        return updated

    def _turn_id(self, chapter_plan: ChapterPlan) -> str:
        return (
            f"novel:{chapter_plan.project_id}:"
            f"ch{chapter_plan.chapter_index}:{chapter_plan.chapter_id}"
        )

    def _active_summary(self, text: str, keyword: str) -> str:
        if keyword and keyword in text:
            idx = text.index(keyword)
            start = max(0, idx - 28)
            raw = text[start: start + 70]
        else:
            raw = text[:70]
        return self._fit_active_summary(raw)

    def _summary(self, text: str, limit: int) -> str:
        compact = " ".join((text or "").split())
        return compact[:limit]

    def _fit_active_summary(self, text: str) -> str:
        compact = self._summary(text, 80)
        if len(compact) >= 30:
            return compact
        suffix = "，需要在后续章节保持连续性和因果回收。"
        return (compact + suffix)[:80]


__all__ = ["NovelEvolutionCurator", "novel_memory_scope"]
