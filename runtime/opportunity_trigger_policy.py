"""OpportunityTriggerPolicy — deterministic trigger rules for Opportunity Agent.

Decides whether an opportunity analysis task should be created for the current turn.
Uses deterministic rules, not LLM judgment.

Opportunity ≠ Event. This policy identifies when there are narrative openings
that could enrich the current turn, based on existing facts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from ..contracts.history_recall_result import HistoryRecallResult


# Player intent signals suggesting opportunity
_OPPORTUNITY_KEYWORDS = [
    r"犹豫", r"试探", r"回避", r"追问", r"靠近",
    r"迟疑", r"欲言又止", r"沉默", r"叹气", r"紧张",
    r"期待", r"担心", r"害怕", r"矛盾", r"纠结",
]

# Unresolved thread signals
_THREAD_SIGNALS = [
    r"承诺", r"约定", r"秘密", r"误会", r"债务",
    r"未解", r"伏笔", r"暗示", r"线索", r"悬念",
]

# Relationship tension signals
_TENSION_SIGNALS = [
    r"张力", r"紧张", r"冷淡", r"疏远", r"尴尬",
    r"暧昧", r"敌意", r"防备", r"试探", r"不信任",
]

_OPPORTUNITY_RE = re.compile("|".join(_OPPORTUNITY_KEYWORDS))
_THREAD_RE = re.compile("|".join(_THREAD_SIGNALS))
_TENSION_RE = re.compile("|".join(_TENSION_SIGNALS))


@dataclass(frozen=True)
class OpportunityTriggerResult:
    """Result of opportunity trigger policy evaluation."""
    should_trigger: bool = False
    trigger_reasons: list[str] = field(default_factory=list)
    opportunity_domains: list[str] = field(default_factory=list)
    focus_entities: list[str] = field(default_factory=list)
    risk_level: str = "none"
    max_opportunity_count: int = 2


class OpportunityTriggerPolicy:
    """Deterministic trigger policy for Opportunity Agent.

    Uses rule-based checks on snapshot signals, director plan, and history recall.
    No LLM judgment involved.
    """

    def evaluate(
        self,
        snapshot: RoundSnapshot,
        director_plan: DirectorPlan,
        history_recall_result: HistoryRecallResult | None = None,
    ) -> OpportunityTriggerResult:
        """Evaluate whether opportunity analysis should be triggered."""
        reasons: list[str] = []
        domains: list[str] = []
        focus_entities: list[str] = []
        risk_level = "none"

        player_input = snapshot.player_input

        # Rule 1: Player intent signals (hesitation, probing, avoidance)
        if _OPPORTUNITY_RE.search(player_input):
            reasons.append("玩家输入表现出犹豫/试探/回避/追问倾向")
            domains.append("player_intent_signal")
            risk_level = "low"

        # Rule 2: Unresolved threads from DirectorPlan
        if director_plan.unresolved_threads:
            reasons.append(f"Director标记未解决线索: {len(director_plan.unresolved_threads)}条")
            domains.append("unresolved_thread")
            if risk_level == "none":
                risk_level = "medium"

        # Rule 3: Relationship tensions from DirectorPlan
        if director_plan.relationship_tensions:
            reasons.append(f"Director标记关系张力: {len(director_plan.relationship_tensions)}条")
            domains.append("relationship_tension")
            if risk_level == "none":
                risk_level = "medium"

        # Rule 4: Scene pressure (risk flags)
        if director_plan.risk_flags:
            reasons.append(f"Director标记场景压力: {len(director_plan.risk_flags)}项")
            domains.append("scene_pressure")
            risk_level = "medium"

        # Rule 5: Narrative opportunities from DirectorPlan
        if director_plan.narrative_opportunities:
            reasons.append(f"Director标记叙事机会: {len(director_plan.narrative_opportunities)}条")
            domains.append("narrative_opportunity")

        # Rule 6: History recall found unresolved issues
        if history_recall_result and history_recall_result.continuity_risks:
            reasons.append(f"历史回查发现连续性风险: {len(history_recall_result.continuity_risks)}条")
            domains.append("history_risk")
            risk_level = "medium"

        # Rule 7: Active memories with unresolved promises/secrets
        for mem in snapshot.active_memories:
            kind = mem.get("kind", "")
            if kind in ("promise", "secret", "misunderstanding", "future_hook"):
                reasons.append(f"活跃记忆包含未解决{kind}: {mem.get('memory_id', '?')}")
                domains.append(f"memory_{kind}")
                if risk_level == "none":
                    risk_level = "low"

        # Rule 8: RAG recall with unresolved threads
        for rag in snapshot.rag_recall:
            kind = rag.get("kind", "")
            if kind in ("unresolved_thread", "foreshadowing"):
                reasons.append(f"RAG记忆包含未解决线索: {rag.get('memory_id', '?')}")
                domains.append("rag_thread")
                if risk_level == "none":
                    risk_level = "low"

        # Rule 9: Multiple recent turns without variation (pacing)
        if len(snapshot.recent_turn_records) >= 4:
            # Check if recent turns have similar patterns
            recent_outputs = [tr.writer_output[:50] for tr in snapshot.recent_turn_records[:4]]
            if len(set(recent_outputs)) <= 2:
                reasons.append("连续多回合缺少叙事变化")
                domains.append("pace_variation")

        # Extract focus entities
        for mem in snapshot.active_memories:
            for ref in mem.get("entity_refs", []):
                if ref not in focus_entities:
                    focus_entities.append(ref)
        for rag in snapshot.rag_recall:
            for ref in rag.get("entity_refs", []):
                if ref not in focus_entities:
                    focus_entities.append(ref)

        # Deduplicate domains
        domains = list(dict.fromkeys(domains))

        should_trigger = len(reasons) > 0

        return OpportunityTriggerResult(
            should_trigger=should_trigger,
            trigger_reasons=reasons,
            opportunity_domains=domains,
            focus_entities=focus_entities,
            risk_level=risk_level,
            max_opportunity_count=2,
        )
