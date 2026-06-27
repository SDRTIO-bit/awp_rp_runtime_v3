"""HistoryRecallTriggerPolicy — deterministic trigger rules for History/Recall Agent.

Decides whether a history recall task should be created for the current turn.
Uses deterministic regex rules, not LLM judgment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from ..contracts.continuity_risk import RiskLevel


# Historical reference keywords (Chinese)
_HISTORICAL_KEYWORDS = [
    r"之前", r"上次", r"当年", r"那时候", r"那时",
    r"以前", r"过去", r"曾经", r"早已", r"当初",
    r"还记得", r"你记得", r"记得吗", r"那件事",
    r"那一次", r"那一回", r"往事", r"旧事",
]

# Promise/commitment keywords
_PROMISE_KEYWORDS = [
    r"答应", r"承诺", r"保证", r"说过", r"约定",
    r"约定过", r"保证过", r"承诺过", r"答应过",
]

# Secret/conflict keywords
_SECRET_CONFLICT_KEYWORDS = [
    r"秘密", r"隐瞒", r"隐藏", r"暗中",
    r"冲突", r"矛盾", r"债务", r"误会",
    r"背叛", r"欺骗", r"谎言", r"真相",
]

# Relationship change keywords
_RELATIONSHIP_KEYWORDS = [
    r"关系", r"信任", r"怀疑", r"敌意", r"友情",
    r"爱情", r"仇恨", r"和解", r"决裂",
]

# Pronoun / ambiguous reference patterns
_AMBIGUOUS_REF_PATTERNS = [
    r"他.{0,3}之前", r"她.{0,3}之前",
    r"他.{0,3}说过", r"她.{0,3}说过",
    r"那个人", r"那人", r"那个人说",
]

# Compile patterns
_HISTORICAL_RE = re.compile("|".join(_HISTORICAL_KEYWORDS))
_PROMISE_RE = re.compile("|".join(_PROMISE_KEYWORDS))
_SECRET_CONFLICT_RE = re.compile("|".join(_SECRET_CONFLICT_KEYWORDS))
_RELATIONSHIP_RE = re.compile("|".join(_RELATIONSHIP_KEYWORDS))
_AMBIGUOUS_RE = re.compile("|".join(_AMBIGUOUS_REF_PATTERNS))


@dataclass(frozen=True)
class TriggerResult:
    """Result of trigger policy evaluation."""
    should_trigger: bool = False
    trigger_reasons: list[str] = field(default_factory=list)
    suggested_focus_entities: list[str] = field(default_factory=list)
    suggested_recall_kinds: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.NONE


class HistoryRecallTriggerPolicy:
    """Deterministic trigger policy for History/Recall Agent.

    Uses regex rules on player input and snapshot signals.
    No LLM judgment involved.
    """

    def evaluate(
        self,
        snapshot: RoundSnapshot,
        director_plan: DirectorPlan,
    ) -> TriggerResult:
        """Evaluate whether history recall should be triggered."""
        reasons: list[str] = []
        focus_entities: list[str] = []
        recall_kinds: list[str] = []
        risk_level = RiskLevel.NONE

        player_input = snapshot.player_input

        # Rule 1: Historical reference keywords
        if _HISTORICAL_RE.search(player_input):
            reasons.append("玩家输入包含历史指代词")
            recall_kinds.append("event_history")
            risk_level = RiskLevel.MEDIUM

        # Rule 2: Promise/commitment keywords
        if _PROMISE_RE.search(player_input):
            reasons.append("玩家输入涉及承诺或约定")
            recall_kinds.append("promise_history")
            if risk_level == RiskLevel.NONE:
                risk_level = RiskLevel.MEDIUM

        # Rule 3: Secret/conflict keywords
        if _SECRET_CONFLICT_RE.search(player_input):
            reasons.append("玩家输入涉及秘密或冲突")
            recall_kinds.extend(["secret_history", "conflict_history"])
            risk_level = RiskLevel.HIGH

        # Rule 4: Relationship change keywords
        if _RELATIONSHIP_RE.search(player_input):
            reasons.append("玩家输入涉及关系变化")
            recall_kinds.append("relationship_history")
            if risk_level == RiskLevel.NONE:
                risk_level = RiskLevel.MEDIUM

        # Rule 5: Ambiguous references (pronouns + historical context)
        if _AMBIGUOUS_RE.search(player_input):
            reasons.append("玩家输入包含模糊指代")
            recall_kinds.append("identity_history")
            if risk_level == RiskLevel.NONE:
                risk_level = RiskLevel.LOW

        # Rule 6: Director risk flags
        if director_plan.risk_flags:
            reasons.append(f"Director标记风险: {', '.join(director_plan.risk_flags[:3])}")
            risk_level = RiskLevel.HIGH

        # Rule 7: Unresolved threads in DirectorPlan
        if director_plan.unresolved_threads:
            reasons.append(f"Director标记未解决伏笔: {len(director_plan.unresolved_threads)}条")
            recall_kinds.append("unresolved_thread")
            if risk_level == RiskLevel.NONE:
                risk_level = RiskLevel.MEDIUM

        # Rule 8: RAG recall conflicts in snapshot
        conflicted_rag = [
            r for r in snapshot.rag_recall
            if r.get("conflict_status") in ("conflicted", "stale")
        ]
        if conflicted_rag:
            reasons.append(f"RAG召回存在冲突: {len(conflicted_rag)}条")
            recall_kinds.append("conflict_history")
            risk_level = RiskLevel.HIGH

        # Rule 9: Multiple RAG candidates (ambiguity)
        if len(snapshot.rag_recall) >= 3:
            reasons.append(f"RAG召回多候选: {len(snapshot.rag_recall)}条")
            if risk_level == RiskLevel.NONE:
                risk_level = RiskLevel.LOW

        # Extract focus entities from active memories
        for mem in snapshot.active_memories:
            for ref in mem.get("entity_refs", []):
                if ref not in focus_entities:
                    focus_entities.append(ref)

        # Extract focus entities from RAG recall
        for rag in snapshot.rag_recall:
            for ref in rag.get("entity_refs", []):
                if ref not in focus_entities:
                    focus_entities.append(ref)

        # Deduplicate recall kinds
        recall_kinds = list(dict.fromkeys(recall_kinds))

        should_trigger = len(reasons) > 0

        return TriggerResult(
            should_trigger=should_trigger,
            trigger_reasons=reasons,
            suggested_focus_entities=focus_entities,
            suggested_recall_kinds=recall_kinds,
            risk_level=risk_level,
        )
