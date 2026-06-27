"""ContinuityTriggerPolicy — deterministic trigger rules for Continuity Agent.

Decides whether a continuity check task should be created for the current turn.
Uses deterministic rules, not LLM judgment.

Continuity Agent asks: which confirmed facts, character states, timelines,
locations, knowledge boundaries, or adopted suggestions must not be
contradicted in the upcoming Writer output?
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from ..contracts.history_recall_result import HistoryRecallResult
from ..contracts.opportunity_result import OpportunityResult


# Continuity reference keywords (player uses "之前/刚才/已经/还没/回来/离开/答应/知道/秘密")
_CONTINUITY_REFERENCE_KEYWORDS = [
    r"之前", r"刚才", r"已经", r"还没", r"还没有",
    r"回来", r"离开", r"答应", r"知道", r"秘密",
    r"记得", r"忘记", r"承诺", r"约定", r"上次",
    r"那件事", r"那时候", r"当年", r"从前",
]

# Character entrance/exit signals
_ENTRANCE_EXIT_KEYWORDS = [
    r"进来", r"出去", r"离开", r"到达", r"出现",
    r"消失", r"入场", r"退场", r"回来", r"走开",
]

# Time change signals
_TIME_CHANGE_KEYWORDS = [
    r"时间", r"天亮", r"天黑", r"黎明", r"黄昏",
    r"过去", r"以后", r"之后", r"明天", r"昨天",
]

# Location change signals
_LOCATION_CHANGE_KEYWORDS = [
    r"来到", r"前往", r"移动", r"转移", r"走到",
    r"进入", r"走出", r"回到", r"到达",
]

# Knowledge boundary signals
_KNOWLEDGE_BOUNDARY_KEYWORDS = [
    r"秘密", r"隐瞒", r"真相", r"知道", r"不知道",
    r"以为", r"误会", r"身份", r"假装",
]

# Promise/commitment signals
_PROMISE_KEYWORDS = [
    r"答应", r"承诺", r"保证", r"约定", r"欠",
    r"还债", r"兑现", r"背叛",
]

# Event stage signals
_EVENT_STAGE_KEYWORDS = [
    r"事件", r"阶段", r"进展", r"完成", r"结束",
    r"开始", r"触发", r"推进",
]

_CONTINUITY_REF_RE = re.compile("|".join(_CONTINUITY_REFERENCE_KEYWORDS))
_ENTRANCE_EXIT_RE = re.compile("|".join(_ENTRANCE_EXIT_KEYWORDS))
_TIME_CHANGE_RE = re.compile("|".join(_TIME_CHANGE_KEYWORDS))
_LOCATION_CHANGE_RE = re.compile("|".join(_LOCATION_CHANGE_KEYWORDS))
_KNOWLEDGE_BOUNDARY_RE = re.compile("|".join(_KNOWLEDGE_BOUNDARY_KEYWORDS))
_PROMISE_RE = re.compile("|".join(_PROMISE_KEYWORDS))
_EVENT_STAGE_RE = re.compile("|".join(_EVENT_STAGE_KEYWORDS))


@dataclass(frozen=True)
class ContinuityTriggerResult:
    """Result of continuity trigger policy evaluation."""
    should_trigger: bool = False
    trigger_reasons: list[str] = field(default_factory=list)
    continuity_domains: list[str] = field(default_factory=list)
    focus_entities: list[str] = field(default_factory=list)
    focus_locations: list[str] = field(default_factory=list)
    focus_turns: list[str] = field(default_factory=list)
    risk_level: str = "none"
    max_issue_count: int = 6


class ContinuityTriggerPolicy:
    """Deterministic trigger policy for Continuity Agent.

    Uses rule-based checks on snapshot signals, director plan, and context.
    No LLM judgment involved.
    """

    def evaluate(
        self,
        snapshot: RoundSnapshot,
        director_plan: DirectorPlan,
        history_recall_result: HistoryRecallResult | None = None,
        opportunity_result: OpportunityResult | None = None,
    ) -> ContinuityTriggerResult:
        """Evaluate whether continuity analysis should be triggered."""
        reasons: list[str] = []
        domains: list[str] = []
        focus_entities: list[str] = []
        focus_locations: list[str] = []
        focus_turns: list[str] = []
        risk_level = "none"

        player_input = snapshot.player_input
        scene_location = snapshot.card_state.scene_state.location if snapshot.card_state.scene_state else ""

        # Rule 1: Continuity reference keywords
        if _CONTINUITY_REF_RE.search(player_input):
            reasons.append("玩家输入包含连续性指代词")
            domains.append("continuity_reference")
            risk_level = "medium"

        # Rule 2: Character entrance/exit signals
        if _ENTRANCE_EXIT_RE.search(player_input):
            reasons.append("玩家输入涉及角色出入场")
            domains.append("entrance_exit")
            risk_level = "medium"

        # Rule 3: Time change signals
        if _TIME_CHANGE_RE.search(player_input):
            reasons.append("玩家输入涉及时间变化")
            domains.append("time_change")
            if risk_level == "none":
                risk_level = "low"

        # Rule 4: Location change signals
        if _LOCATION_CHANGE_RE.search(player_input):
            reasons.append("玩家输入涉及地点变化")
            domains.append("location_change")
            if risk_level == "none":
                risk_level = "low"

        # Rule 5: Knowledge boundary signals
        if _KNOWLEDGE_BOUNDARY_RE.search(player_input):
            reasons.append("玩家输入涉及知识边界、秘密或身份")
            domains.append("knowledge_boundary")
            risk_level = "high"

        # Rule 6: Promise/commitment signals
        if _PROMISE_RE.search(player_input):
            reasons.append("玩家输入涉及承诺或约定")
            domains.append("promise")
            risk_level = "high"

        # Rule 7: Event stage signals
        if _EVENT_STAGE_RE.search(player_input):
            reasons.append("玩家输入涉及事件阶段变化")
            domains.append("event_stage")
            if risk_level == "none":
                risk_level = "medium"

        # Rule 8: DirectorPlan has risk flags related to continuity
        for flag in director_plan.risk_flags:
            if any(kw in flag for kw in ["连续", "矛盾", "冲突", "一致", "事实"]):
                reasons.append(f"DirectorPlan标记连续性风险: {flag}")
                domains.append("director_continuity")
                risk_level = "high"
                break

        # Rule 9: Multiple active memories with potential conflicts
        if len(snapshot.active_memories) >= 3:
            # Check for conflicting kinds
            kinds = [m.get("kind", "") for m in snapshot.active_memories]
            if "promise" in kinds and "conflict" in kinds:
                reasons.append("活跃记忆中同时存在承诺和冲突")
                domains.append("memory_conflict")
                risk_level = "high"

        # Rule 10: RAG recall with conflicting information
        if len(snapshot.rag_recall) >= 3:
            reasons.append("RAG召回包含多条记忆，可能存在冲突")
            domains.append("rag_multiple")
            if risk_level == "none":
                risk_level = "low"

        # Rule 11: Recent turns with character/location changes
        if len(snapshot.recent_turn_records) >= 2:
            recent_outputs = [tr.writer_output for tr in snapshot.recent_turn_records[:3] if tr.writer_output]
            for output in recent_outputs:
                if _ENTRANCE_EXIT_RE.search(output):
                    reasons.append("最近回合涉及角色出入场")
                    domains.append("recent_entrance_exit")
                    if risk_level == "none":
                        risk_level = "low"
                    break

        # Rule 12: DirectorPlan plans to push scene, relationship, event, or character behavior
        if director_plan.narrative_opportunities:
            for opp in director_plan.narrative_opportunities:
                if any(kw in opp for kw in ["推进", "变化", "转折", "揭露"]):
                    reasons.append(f"DirectorPlan计划推动叙事变化: {opp[:30]}")
                    domains.append("director_push")
                    if risk_level == "none":
                        risk_level = "medium"
                    break

        # Extract focus entities from active memories
        for mem in snapshot.active_memories:
            for ref in mem.get("entity_refs", []):
                if ref not in focus_entities:
                    focus_entities.append(ref)

        # Extract focus locations
        if scene_location:
            focus_locations.append(scene_location)

        # Extract focus turns from recent records
        for tr in snapshot.recent_turn_records[:3]:
            if tr.turn_id:
                focus_turns.append(tr.turn_id)

        # Deduplicate domains
        domains = list(dict.fromkeys(domains))

        should_trigger = len(reasons) > 0

        return ContinuityTriggerResult(
            should_trigger=should_trigger,
            trigger_reasons=reasons,
            continuity_domains=domains,
            focus_entities=focus_entities,
            focus_locations=focus_locations,
            focus_turns=focus_turns,
            risk_level=risk_level,
            max_issue_count=6,
        )
