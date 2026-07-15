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
from ..contracts.novel_npc_agenda import NpcAction, SelectedNpcAction
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
            else os.environ.get("NOVEL_EVOLUTION_USE_LEDGER_LLM", "1") != "0"
        )

    def curate(
        self,
        *,
        chapter_text: str,
        chapter_plan: ChapterPlan,
        current_ledger_items: list[LedgerItem],
        characters: list[NovelCharacter],
        quality_decision: QualityDecision | None,
        selected_npc_actions: tuple[SelectedNpcAction, ...] = (),
    ) -> dict[str, Any]:
        # Convert selected autonomous NPC actions to deterministic ledger updates
        # so later chapters recall them as visible consequences.
        npc_ledger_items = [
            self._selected_npc_action_to_ledger(action, chapter_plan)
            for action in selected_npc_actions
        ]

        ledger_result = self._curate_ledger(
            chapter_text, chapter_plan, current_ledger_items, characters,
        )
        chapter_summary = ledger_result.get("chapter_summary", "") if ledger_result else ""
        ledger_updates = list(npc_ledger_items)
        llm_items = ledger_result.get("ledger_updates", [])
        if llm_items and isinstance(llm_items, list) and len(llm_items) > 0:
            print(f"[LedgerCurator] LLM returned {len(llm_items)} ledger_updates, first item keys={list(llm_items[0].keys()) if isinstance(llm_items[0], dict) else type(llm_items[0])}", flush=True)
        for item in llm_items:
            if isinstance(item, LedgerItem):
                normalized = self._normalize_ledger_item(item, chapter_plan)
                if normalized:
                    print(f"[LedgerCurator] ACCEPTED LedgerItem: section={normalized.section} entity={normalized.entity}", flush=True)
            elif isinstance(item, dict):
                conv = self._convert_llm_ledger_item(item, chapter_plan)
                if conv:
                    normalized = self._normalize_ledger_item(conv, chapter_plan)
                    if normalized:
                        print(f"[LedgerCurator] ACCEPTED dict→LedgerItem: section={normalized.section} entity={normalized.entity}", flush=True)
                    else:
                        print(f"[LedgerCurator] REJECTED by normalize: section={conv.section!r} content_len={len(conv.content)}", flush=True)
                else:
                    print(f"[LedgerCurator] REJECTED by convert: keys={list(item.keys())}", flush=True)
                    normalized = None
            else:
                normalized = None
            if normalized is not None:
                ledger_updates.append(normalized)
        ledger_updates.extend(
            self._deterministic_ledger_updates(
                chapter_text, chapter_plan, current_ledger_items, ledger_updates, characters
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
                chapter_summary=chapter_summary,
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
        characters: list[NovelCharacter],
    ) -> dict[str, Any]:
        ch_idx = getattr(chapter_plan, "chapter_index", 0)
        print(f"[LedgerCurator] _curate_ledger called for ch{ch_idx}, use_llm={self._use_ledger_llm}", flush=True)
        if not self._use_ledger_llm:
            print(f"[LedgerCurator] SKIPPED (use_ledger_llm=False)", flush=True)
            return {}

        previous_chapter_summaries = [
            i.content for i in current_ledger_items
            if i.section == "chapter_summary" and i.content
        ]

        try:
            print(f"[LedgerCurator] Calling curator.curate() for ch{ch_idx} (prev_summaries={len(previous_chapter_summaries)})...", flush=True)
            result = self._ledger_curator.curate(
                chapter_text, chapter_plan, current_ledger_items,
                previous_chapter_summaries=previous_chapter_summaries,
            )
            print(f"[LedgerCurator] curator.curate() returned OK, type={type(result)}, keys={list(result.keys()) if isinstance(result, dict) else 'N/A'}", flush=True)

            if result and isinstance(result, dict):
                ch_summary = (result.get("chapter_summary") or "").strip()
                project_id = getattr(chapter_plan, "project_id", "")
                if ch_summary:
                    result.setdefault("ledger_updates", [])
                    result["ledger_updates"].insert(0, {
                        "section": "chapter_summary",
                        "entity": f"ch{ch_idx}",
                        "content": ch_summary,
                        "status": "active",
                    })

            return result if isinstance(result, dict) else {}
        except Exception as e:
            import traceback
            print(f"[LedgerCurator] LLM call FAILED for ch{ch_idx}: {e}", flush=True)
            traceback.print_exc()
            return {}

    def _selected_npc_action_to_ledger(
        self,
        action: SelectedNpcAction,
        chapter_plan: ChapterPlan,
    ) -> LedgerItem:
        """Persist an autonomous NPC action as a ledger item for continuity."""
        project_id = chapter_plan.project_id
        source_chapter = chapter_plan.chapter_index
        entity = action.character_name
        consequence = action.visible_consequence
        content = f"{consequence.observable_event} | consequence: {consequence.observable_clue}"
        return LedgerItem(
            item_id=f"novel-ledger-{project_id}-ch{source_chapter}-npc_action-{_hash(entity + content)}",
            project_id=project_id,
            section=NpcAction.LEDGER_SECTION,
            entity=entity,
            content=content,
            source_chapter=source_chapter,
            status="active",
            created_at=_now(),
            updated_at=_now(),
        )

    def _normalize_ledger_item(
        self, item: LedgerItem, chapter_plan: ChapterPlan
    ) -> LedgerItem | None:
        if not item.section or not item.content:
            return None
        project_id = item.project_id or chapter_plan.project_id
        source_chapter = item.source_chapter or chapter_plan.chapter_index
        entity = item.entity or (chapter_plan.title or f"第{chapter_plan.chapter_index}章")
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

    @staticmethod
    def _convert_llm_ledger_item(item: dict, chapter_plan: ChapterPlan) -> LedgerItem | None:
        """Convert LLM output format to LedgerItem.

        Uses heuristic field detection to handle any LLM output format.
        """
        # ── 1. Detect SECTION ──
        section_keys = ["section", "type", "category"]
        section = ""
        for k in section_keys:
            v = item.get(k)
            if v and isinstance(v, str) and v.strip():
                section = v.strip()
                break
        known_sections = {
            "chapter_summary", "character_state", "relationship", "timeline",
            "foreshadowing", "world_rules", "open_threads",
            "character", "state", "char",
            "npc_agenda", "npc_action",
        }
        if section and section.lower().replace(" ", "_") not in known_sections:
            section = "character_state"

        if not section:
            section = "character_state"

        # ── 2. Detect ENTITY ──
        entity_keys = ["entity", "target", "name", "character", "person", "field"]
        entity = ""
        for k in entity_keys:
            v = item.get(k)
            if v and isinstance(v, str) and v.strip():
                entity = v.strip()
                break
        if not entity:
            entity = str(item.get("entity") or item.get("target") or item.get("name") or item.get("field") or "")

        # ── 3. Detect CONTENT ──
        content_keys = ["content", "update", "description", "summary", "detail"]
        content = ""
        for k in content_keys:
            v = item.get(k)
            if v and isinstance(v, str) and v.strip():
                content = v.strip()
                break

        # Fallback: build content from all remaining string fields
        if not content:
            extra_keys = {"attribute", "old_value", "new_value", "location", "emotion", "tension", "tag"}
            parts = []
            for k in extra_keys:
                v = item.get(k, "")
                if v and isinstance(v, str) and v.strip():
                    parts.append(f"{k}: {v.strip()}")
            if parts:
                content = "; ".join(parts)
            elif not entity:
                return None

        if not entity or not content:
            return None

        return LedgerItem(
            project_id=chapter_plan.project_id,
            item_id=str(item.get("id") or item.get("item_id") or ""),
            section=section,
            entity=entity,
            content=content,
            source_chapter=chapter_plan.chapter_index,
        )

    def _deterministic_ledger_updates(
        self,
        chapter_text: str,
        chapter_plan: ChapterPlan,
        current_ledger_items: list[LedgerItem],
        proposed_updates: list[LedgerItem],
        characters: list[NovelCharacter],
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

        present_chars = [c.name for c in characters if c.name and c.name in chapter_text]
        entity = ", ".join(present_chars[:2]) if present_chars else (chapter_plan.title or f"第{chapter_plan.chapter_index}章")
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
        chapter_summary: str = "",
    ) -> MemoryCommitPlan:
        card_id, session_id = novel_memory_scope(chapter_plan.project_id)
        turn_id = self._turn_id(chapter_plan)
        memory_commit_id = f"novel-mc-{_hash(turn_id + chapter_text)}"
        entity_refs = [c.name for c in characters if c.name and c.name in chapter_text]

        active_entries = self._active_entries(
            chapter_text, chapter_plan, card_id, session_id, turn_id, entity_refs
        )
        rag_content = chapter_summary if chapter_summary else self._summary(chapter_text, 300)
        rag_summary = self._summary(chapter_text, 120)
        rag_entry = RagMemoryRecord(
            memory_id=f"novel-rag-{_hash(turn_id)}",
            card_id=card_id,
            session_id=session_id,
            scope="session",
            content=rag_content,
            summary=rag_summary,
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
            start = max(0, idx - 80)
            raw = text[start: start + 200]
        else:
            raw = text[:200]
        return self._fit_active_summary(raw)

    def _summary(self, text: str, limit: int) -> str:
        compact = " ".join((text or "").split())
        return compact[:limit]

    def _fit_active_summary(self, text: str) -> str:
        compact = self._summary(text, 80)
        if len(compact) >= 60:
            return compact
        suffix = "，需要在后续章节保持连续性和因果回收。"
        return (compact + suffix)[:80]


__all__ = ["NovelEvolutionCurator", "novel_memory_scope"]
