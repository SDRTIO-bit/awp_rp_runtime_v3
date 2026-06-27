"""WorldLifeTriggerPolicy — deterministic trigger rules for World-Life Agent.

Decides whether a world-life analysis task should be created for the current turn.
Uses deterministic rules, not LLM judgment.

World-Life Agent asks: what might be happening in the world beyond the protagonist's view?
It provides atmospheric, environmental, and NPC-side pressure candidates.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from ..contracts.history_recall_result import HistoryRecallResult
from ..contracts.opportunity_result import OpportunityResult


# Environment/weather/time signals
_ENVIRONMENT_KEYWORDS = [
    r"雨", r"雪", r"风", r"雾", r"雷", r"闪电",
    r"晴朗", r"阴天", r"黄昏", r"黎明", r"深夜", r"正午",
    r"寒冷", r"炎热", r"潮湿", r"干燥", r"闷热",
    r"节日", r"集市", r"宵禁", r"庆典", r"祭祀",
]

# Location atmosphere signals
_LOCATION_KEYWORDS = [
    r"庭院", r"街道", r"市场", r"酒馆", r"客栈",
    r"森林", r"山", r"河", r"湖", r"海",
    r"宫殿", r"神殿", r"废墟", r"村庄", r"城镇",
    r"喧闹", r"安静", r"繁忙", r"冷清", r"拥挤",
]

# NPC pressure signals
_NPC_PRESSURE_KEYWORDS = [
    r"紧张", r"焦虑", r"愤怒", r"悲伤", r"恐惧",
    r"犹豫", r"迟疑", r"沉默", r"叹气", r"回避",
    r"防备", r"敌意", r"不信任", r"怀疑", r"戒备",
]

# Event stage signals
_EVENT_STAGE_KEYWORDS = [
    r"事件", r"阶段", r"进展", r"酝酿", r"迫近",
    r"即将", r"将要", r"临近", r"逼近", r"来临",
]

_ENVIRONMENT_RE = re.compile("|".join(_ENVIRONMENT_KEYWORDS))
_LOCATION_RE = re.compile("|".join(_LOCATION_KEYWORDS))
_NPC_PRESSURE_RE = re.compile("|".join(_NPC_PRESSURE_KEYWORDS))
_EVENT_STAGE_RE = re.compile("|".join(_EVENT_STAGE_KEYWORDS))


@dataclass(frozen=True)
class WorldLifeTriggerResult:
    """Result of world-life trigger policy evaluation."""
    should_trigger: bool = False
    trigger_reasons: list[str] = field(default_factory=list)
    world_life_domains: list[str] = field(default_factory=list)
    focus_entities: list[str] = field(default_factory=list)
    focus_locations: list[str] = field(default_factory=list)
    focus_event_stages: list[str] = field(default_factory=list)
    risk_level: str = "none"
    max_candidate_count: int = 2


class WorldLifeTriggerPolicy:
    """Deterministic trigger policy for World-Life Agent.

    Uses rule-based checks on snapshot signals, director plan, and context.
    No LLM judgment involved.
    """

    def evaluate(
        self,
        snapshot: RoundSnapshot,
        director_plan: DirectorPlan,
        history_recall_result: HistoryRecallResult | None = None,
        opportunity_result: OpportunityResult | None = None,
    ) -> WorldLifeTriggerResult:
        """Evaluate whether world-life analysis should be triggered."""
        reasons: list[str] = []
        domains: list[str] = []
        focus_entities: list[str] = []
        focus_locations: list[str] = []
        focus_event_stages: list[str] = []
        risk_level = "none"

        player_input = snapshot.player_input
        scene_location = snapshot.card_state.scene_state.location if snapshot.card_state.scene_state else ""

        # Rule 1: Scene has environmental features
        if _ENVIRONMENT_RE.search(player_input) or _ENVIRONMENT_RE.search(scene_location):
            reasons.append("场景存在明确的环境特征、天气或时间压力")
            domains.append("environment")
            risk_level = "low"

        # Rule 2: Location has atmosphere
        if _LOCATION_RE.search(scene_location):
            reasons.append(f"当前地点具有可描写的空间氛围: {scene_location}")
            domains.append("location")
            if risk_level == "none":
                risk_level = "low"

        # Rule 3: NPC pressure signals
        if _NPC_PRESSURE_RE.search(player_input):
            reasons.append("玩家输入或场景中存在NPC侧压力信号")
            domains.append("npc_pressure")
            if risk_level == "none":
                risk_level = "low"

        # Rule 4: Event stage signals
        if _EVENT_STAGE_RE.search(player_input):
            reasons.append("存在事件阶段或进展信号")
            domains.append("event_stage")
            if risk_level == "none":
                risk_level = "medium"

        # Rule 5: Active worldbook entries with location/time relevance
        for wb in snapshot.active_worldbook_entries:
            content = wb.get("content", "")
            title = wb.get("title", "")
            if any(kw in content or kw in title for kw in ["地点", "时间", "节日", "天气", "氛围"]):
                reasons.append(f"世界书与当前地点/时间相关: {title[:30]}")
                domains.append("worldbook")
                if risk_level == "none":
                    risk_level = "low"
                break

        # Rule 6: DirectorPlan indicates need for world presence
        if director_plan.risk_flags:
            for flag in director_plan.risk_flags:
                if any(kw in flag for kw in ["世界", "环境", "氛围", "背景", "压力"]):
                    reasons.append(f"DirectorPlan指示需要增强世界在场感: {flag}")
                    domains.append("director_world_presence")
                    risk_level = "medium"
                    break

        # Rule 7: Multiple recent turns without world variation
        if len(snapshot.recent_turn_records) >= 3:
            recent_locations = set()
            for tr in snapshot.recent_turn_records[:3]:
                # Check if location changed
                if tr.writer_output and scene_location in tr.writer_output:
                    recent_locations.add(scene_location)
            if len(recent_locations) <= 1:
                # Check if narrative is too closed (only player-focused)
                player_focused_count = sum(
                    1 for tr in snapshot.recent_turn_records[:3]
                    if tr.writer_output and len(tr.writer_output) < 100
                )
                if player_focused_count >= 2:
                    reasons.append("连续多回合叙事过于封闭，缺少世界在场感")
                    domains.append("narrative_closure")

        # Rule 8: Active memories with event/world context
        for mem in snapshot.active_memories:
            kind = mem.get("kind", "")
            if kind in ("event", "world_event", "festival", "conflict"):
                reasons.append(f"活跃记忆包含世界事件: {mem.get('memory_id', '?')}")
                domains.append(f"memory_{kind}")
                if risk_level == "none":
                    risk_level = "low"

        # Rule 9: RAG recall with world context
        for rag in snapshot.rag_recall:
            kind = rag.get("kind", "")
            if kind in ("world_event", "location_history", "npc_background"):
                reasons.append(f"RAG记忆包含世界背景: {rag.get('memory_id', '?')}")
                domains.append(f"rag_{kind}")
                if risk_level == "none":
                    risk_level = "low"

        # Extract focus entities
        for mem in snapshot.active_memories:
            for ref in mem.get("entity_refs", []):
                if ref not in focus_entities:
                    focus_entities.append(ref)
        for rag in snapshot.rag_recall:
            for ref in rag.get("entity_refs", []):
                if ref not in focus_entities:
                    focus_entities.append(ref)

        # Extract focus locations
        if scene_location:
            focus_locations.append(scene_location)

        # Extract focus event stages
        for mem in snapshot.active_memories:
            if mem.get("kind") in ("event", "world_event"):
                focus_event_stages.append(mem.get("memory_id", ""))

        # Deduplicate domains
        domains = list(dict.fromkeys(domains))

        should_trigger = len(reasons) > 0

        return WorldLifeTriggerResult(
            should_trigger=should_trigger,
            trigger_reasons=reasons,
            world_life_domains=domains,
            focus_entities=focus_entities,
            focus_locations=focus_locations,
            focus_event_stages=focus_event_stages,
            risk_level=risk_level,
            max_candidate_count=2,
        )
