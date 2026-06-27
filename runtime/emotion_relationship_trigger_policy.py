"""EmotionRelationshipTriggerPolicy — deterministic trigger rules for Emotion/Relationship Agent.

Decides whether an emotion/relationship analysis task should be created for the current turn.
Uses deterministic rules, not LLM judgment.

Emotion/Relationship Agent asks: what relational dynamics or emotional undercurrents
are present in the narrative context? It provides soft guidance about trust, boundaries,
emotional residue, and subtext — without asserting facts or modifying relationships.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from ..contracts.history_recall_result import HistoryRecallResult


# Relationship action keywords
_RELATIONSHIP_KEYWORDS = [
    r"承诺", r"拒绝", r"靠近", r"回避", r"误会",
    r"秘密", r"嫉妒", r"冲突", r"和解", r"道歉",
    r"对不起", r"试探", r"安慰", r"质问", r"冷落",
    r"邀请", r"原谅", r"背叛", r"信任", r"怀疑",
    r"表白", r"好感", r"敌意", r"依赖", r"防备",
    r"心虚", r"生气", r"在乎", r"冷淡", r"疏远",
]

# Emotion signal keywords
_EMOTION_KEYWORDS = [
    r"犹豫", r"迟疑", r"欲言又止", r"沉默", r"叹气",
    r"紧张", r"期待", r"担心", r"害怕", r"矛盾",
    r"纠结", r"心酸", r"委屈", r"失落", r"温柔",
    r"愤怒", r"伤心", r"开心", r"感动", r"尴尬",
    r"不安", r"心疼", r"心虚", r"愧疚", r"后悔",
]

# Active memory kinds relevant to emotion/relationship
_RELATIONSHIP_MEMORY_KINDS = {
    "relationship_shift", "misunderstanding", "promise",
    "secret", "emotional_trend",
}

_RELATIONSHIP_RE = re.compile("|".join(_RELATIONSHIP_KEYWORDS))
_EMOTION_RE = re.compile("|".join(_EMOTION_KEYWORDS))


@dataclass(frozen=True)
class EmotionRelationshipTriggerResult:
    """Result of emotion/relationship trigger policy evaluation."""
    should_trigger: bool = False
    trigger_reasons: list[str] = field(default_factory=list)
    emotion_relationship_domains: list[str] = field(default_factory=list)
    focus_entities: list[str] = field(default_factory=list)
    risk_level: str = "none"
    max_candidate_count: int = 2


class EmotionRelationshipTriggerPolicy:
    """Deterministic trigger policy for Emotion/Relationship Agent.

    Uses rule-based checks on snapshot signals, director plan, and context.
    No LLM judgment involved.
    """

    def evaluate(
        self,
        snapshot: RoundSnapshot,
        director_plan: DirectorPlan,
        history_recall_result: HistoryRecallResult | None = None,
    ) -> EmotionRelationshipTriggerResult:
        """Evaluate whether emotion/relationship analysis should be triggered."""
        reasons: list[str] = []
        domains: list[str] = []
        focus_entities: list[str] = []
        risk_level = "none"

        player_input = snapshot.player_input

        # Rule 1: Relationship keywords in player input
        if _RELATIONSHIP_RE.search(player_input):
            reasons.append("玩家输入包含关系动作关键词")
            domains.append("relationship_action")
            risk_level = "low"

        # Rule 2: Emotion signal keywords in player input
        if _EMOTION_RE.search(player_input):
            reasons.append("玩家输入包含情感信号关键词")
            domains.append("emotion_signal")
            if risk_level == "none":
                risk_level = "low"

        # Rule 3: Active memories with relationship-related kinds
        for mem in snapshot.active_memories:
            kind = mem.get("kind", "")
            if kind in _RELATIONSHIP_MEMORY_KINDS:
                reasons.append(f"活跃记忆包含关系相关类型: {kind} ({mem.get('memory_id', '?')})")
                domains.append(f"memory_{kind}")
                if risk_level == "none":
                    risk_level = "low"

        # Rule 4: DirectorPlan relationship tensions
        if director_plan.relationship_tensions:
            reasons.append(f"Director标记关系张力: {len(director_plan.relationship_tensions)}条")
            domains.append("relationship_tension")
            risk_level = "medium"

        # Rule 5: History recall found relationship facts
        if history_recall_result:
            for fact in history_recall_result.facts:
                if any(kw in fact.get("summary", "") for kw in ["关系", "情感", "信任", "误会", "秘密"]):
                    reasons.append(f"历史回查发现关系相关事实")
                    domains.append("history_relationship")
                    if risk_level == "none":
                        risk_level = "low"
                    break

        # Rule 6: RAG recall with relationship content
        for rag in snapshot.rag_recall:
            kind = rag.get("kind", "")
            summary = rag.get("summary", "")
            if kind in _RELATIONSHIP_MEMORY_KINDS or any(
                kw in summary for kw in ["关系", "情感", "信任", "误会"]
            ):
                reasons.append(f"RAG记忆包含关系内容: {rag.get('memory_id', '?')}")
                domains.append("rag_relationship")
                if risk_level == "none":
                    risk_level = "low"
                break

        # Should NOT trigger checks:
        # Check for pure info queries (no relationship/emotion signals)
        if not reasons:
            # No signals found at all — do not trigger
            return EmotionRelationshipTriggerResult(
                should_trigger=False,
                trigger_reasons=[],
                emotion_relationship_domains=[],
                focus_entities=[],
                risk_level="none",
                max_candidate_count=2,
            )

        # Extract focus entities from active memories and RAG
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

        return EmotionRelationshipTriggerResult(
            should_trigger=True,
            trigger_reasons=reasons,
            emotion_relationship_domains=domains,
            focus_entities=focus_entities,
            risk_level=risk_level,
            max_candidate_count=2,
        )
