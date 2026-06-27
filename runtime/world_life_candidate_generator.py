"""WorldLifeCandidateGenerator — generates world-life candidates from evidence.

This is the Fake Adapter for V1. It generates deterministic candidates
from snapshot data and evidence. A future LLM Adapter can replace this.

World-Life Candidate = based on existing facts, suggests how environment,
NPC side-tensions, or event pressures could naturally appear in narration.

It CANNOT:
- Assert facts as having happened
- Modify state or advance timeline
- Override player agency
- Create new events or NPCs
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.world_life_candidate import (
    WorldLifeCandidate, WorldLifeKind, WorldLayer, VisibilityMode,
)
from ..contracts.world_life_evidence import WorldLifeEvidence
from .world_life_trigger_policy import WorldLifeTriggerResult


class WorldLifeCandidateGenerator:
    """Generates world-life candidates from snapshot data and evidence.

    Fake Adapter mode: deterministic generation from snapshot data.
    Future: LLM Adapter can generate richer candidates.
    """

    def generate(
        self,
        snapshot: RoundSnapshot,
        trigger_result: WorldLifeTriggerResult,
        evidence: list[WorldLifeEvidence],
        max_candidates: int = 5,
    ) -> list[WorldLifeCandidate]:
        """Generate world-life candidates from evidence.

        Returns list of candidates, each grounded in evidence.
        """
        now = datetime.now(timezone.utc).isoformat()
        candidates: list[WorldLifeCandidate] = []
        scene_location = snapshot.card_state.scene_state.location if snapshot.card_state.scene_state else ""

        # Strategy 1: Environmental pressure from scene context
        if "environment" in trigger_result.world_life_domains:
            ev_refs = [ev.evidence_id for ev in evidence if ev.source_type == "scene_context"]
            if ev_refs:
                candidates.append(WorldLifeCandidate(
                    candidate_id=f"wlc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=WorldLifeKind.ENVIRONMENTAL_PRESSURE,
                    title=f"环境压力: {scene_location}",
                    summary=f"基于当前场景环境，可在描写中体现自然的环境变化和氛围",
                    world_layer=WorldLayer.ENVIRONMENT,
                    narrative_function="增强场景在场感",
                    focus_entities=[],
                    focus_location=scene_location,
                    foundation_facts=[f"当前地点: {scene_location}"],
                    evidence_refs=ev_refs,
                    activation_conditions=["描写场景时自然提及环境"],
                    visibility_mode=VisibilityMode.BACKGROUND,
                    player_agency_risk=0.0,
                    continuity_risk=0.1,
                    state_change_risk=0.0,
                    novelty_score=0.5,
                    relevance_score=0.7,
                    confidence=0.7,
                    suggested_writer_use="可在环境描写中自然体现天气、时间、氛围变化",
                    suggested_director_use="可作为场景氛围的自然背景",
                    must_not_assert_as_fact=True,
                    must_not_commit_state=True,
                    created_at=now,
                ))

        # Strategy 2: Weather/time atmosphere
        if "environment" in trigger_result.world_life_domains or "location" in trigger_result.world_life_domains:
            ev_refs = [ev.evidence_id for ev in evidence if ev.source_type == "scene_context"]
            if ev_refs and len(candidates) < max_candidates:
                candidates.append(WorldLifeCandidate(
                    candidate_id=f"wlc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=WorldLifeKind.WEATHER_OR_TIME_ATMOSPHERE,
                    title="天气/时间氛围",
                    summary="基于当前时间和天气状况，可在描写中体现自然的时间流逝感",
                    world_layer=WorldLayer.ENVIRONMENT,
                    narrative_function="增强时间在场感",
                    focus_entities=[],
                    focus_location=scene_location,
                    foundation_facts=["时间流逝是自然现象"],
                    evidence_refs=ev_refs,
                    activation_conditions=["描写场景时自然提及时间或天气"],
                    visibility_mode=VisibilityMode.BACKGROUND,
                    player_agency_risk=0.0,
                    continuity_risk=0.0,
                    state_change_risk=0.0,
                    novelty_score=0.4,
                    relevance_score=0.6,
                    confidence=0.6,
                    suggested_writer_use="可在描写中自然体现光线、温度、风向等变化",
                    suggested_director_use="可作为时间流逝的自然提示",
                    must_not_assert_as_fact=True,
                    must_not_commit_state=True,
                    created_at=now,
                ))

        # Strategy 3: Location life detail
        if "location" in trigger_result.world_life_domains:
            ev_refs = [ev.evidence_id for ev in evidence if ev.source_type == "scene_context"]
            if ev_refs and len(candidates) < max_candidates:
                candidates.append(WorldLifeCandidate(
                    candidate_id=f"wlc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=WorldLifeKind.LOCATION_LIFE_DETAIL,
                    title=f"地点生命力: {scene_location}",
                    summary=f"基于{scene_location}的特性，可在描写中体现该地点的自然生命力",
                    world_layer=WorldLayer.LOCATION,
                    narrative_function="增强地点在场感",
                    focus_entities=[],
                    focus_location=scene_location,
                    foundation_facts=[f"当前地点: {scene_location}"],
                    evidence_refs=ev_refs,
                    activation_conditions=["描写地点时自然提及生活细节"],
                    visibility_mode=VisibilityMode.SUBTLE_SIGNAL,
                    player_agency_risk=0.0,
                    continuity_risk=0.1,
                    state_change_risk=0.0,
                    novelty_score=0.5,
                    relevance_score=0.7,
                    confidence=0.7,
                    suggested_writer_use="可在地点描写中自然体现声响、气味、人流等细节",
                    suggested_director_use="可作为地点氛围的自然补充",
                    must_not_assert_as_fact=True,
                    must_not_commit_state=True,
                    created_at=now,
                ))

        # Strategy 4: NPC side tension from active memories
        if "npc_pressure" in trigger_result.world_life_domains:
            for mem in snapshot.active_memories:
                if len(candidates) >= max_candidates:
                    break
                kind = mem.get("kind", "")
                if kind in ("tension", "conflict", "pressure"):
                    ev_refs = [ev.evidence_id for ev in evidence
                               if ev.source_ref == mem.get("memory_id")]
                    if ev_refs:
                        candidates.append(WorldLifeCandidate(
                            candidate_id=f"wlc_{uuid.uuid4().hex[:8]}",
                            trace_id=snapshot.trace_id,
                            snapshot_id=snapshot.snapshot_id,
                            kind=WorldLifeKind.NPC_SIDE_TENSION,
                            title=f"NPC侧张力: {mem.get('summary', '')[:30]}",
                            summary="基于NPC的当前状态，可在描写中体现其自然的情绪或压力",
                            world_layer=WorldLayer.NPC,
                            narrative_function="增强角色在场感",
                            focus_entities=mem.get("entity_refs", []),
                            focus_location=scene_location,
                            foundation_facts=[mem.get("summary", "")],
                            evidence_refs=ev_refs,
                            activation_conditions=["NPC出场或互动时自然体现"],
                            visibility_mode=VisibilityMode.OPTIONAL_DIALOGUE_COLOR,
                            player_agency_risk=0.1,
                            continuity_risk=0.2,
                            state_change_risk=0.0,
                            novelty_score=0.6,
                            relevance_score=0.7,
                            confidence=mem.get("confidence", 0.7),
                            suggested_writer_use="NPC的语气、停顿、表情可自然带有压力感",
                            suggested_director_use="可作为NPC状态的自然提示",
                            must_not_assert_as_fact=True,
                            must_not_commit_state=True,
                            created_at=now,
                        ))

        # Strategy 5: Event stage echo from active memories
        if "event_stage" in trigger_result.world_life_domains:
            for mem in snapshot.active_memories:
                if len(candidates) >= max_candidates:
                    break
                kind = mem.get("kind", "")
                if kind in ("event", "world_event"):
                    ev_refs = [ev.evidence_id for ev in evidence
                               if ev.source_ref == mem.get("memory_id")]
                    if ev_refs:
                        candidates.append(WorldLifeCandidate(
                            candidate_id=f"wlc_{uuid.uuid4().hex[:8]}",
                            trace_id=snapshot.trace_id,
                            snapshot_id=snapshot.snapshot_id,
                            kind=WorldLifeKind.EVENT_STAGE_ECHO,
                            title=f"事件阶段回声: {mem.get('summary', '')[:30]}",
                            summary="基于当前事件阶段，可在描写中体现事件的自然压力",
                            world_layer=WorldLayer.EVENT_STAGE,
                            narrative_function="增强事件在场感",
                            focus_entities=mem.get("entity_refs", []),
                            focus_location=scene_location,
                            foundation_facts=[mem.get("summary", "")],
                            evidence_refs=ev_refs,
                            activation_conditions=["描写场景时自然提及事件进展"],
                            visibility_mode=VisibilityMode.SUBTLE_SIGNAL,
                            player_agency_risk=0.1,
                            continuity_risk=0.2,
                            state_change_risk=0.0,
                            novelty_score=0.6,
                            relevance_score=0.7,
                            confidence=mem.get("confidence", 0.7),
                            suggested_writer_use="可在场景中自然体现事件的酝酿感或迫近感",
                            suggested_director_use="可作为事件阶段的自然提示",
                            must_not_assert_as_fact=True,
                            must_not_commit_state=True,
                            created_at=now,
                        ))

        # Strategy 6: Worldbook resonance
        if "worldbook" in trigger_result.world_life_domains:
            for wb in snapshot.active_worldbook_entries:
                if len(candidates) >= max_candidates:
                    break
                content = wb.get("content", "")
                title = wb.get("title", "")
                ev_refs = [f"worldbook:{title}"]
                candidates.append(WorldLifeCandidate(
                    candidate_id=f"wlc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=WorldLifeKind.WORLDBOOK_RESONANCE,
                    title=f"世界书共振: {title[:30]}",
                    summary="基于世界书中的背景信息，可在描写中自然体现世界观",
                    world_layer=WorldLayer.WORLDBOOK,
                    narrative_function="增强世界观在场感",
                    focus_entities=[],
                    focus_location=scene_location,
                    foundation_facts=[content[:200]],
                    evidence_refs=ev_refs,
                    activation_conditions=["描写场景时自然提及世界背景"],
                    visibility_mode=VisibilityMode.BACKGROUND,
                    player_agency_risk=0.0,
                    continuity_risk=0.1,
                    state_change_risk=0.0,
                    novelty_score=0.5,
                    relevance_score=0.6,
                    confidence=0.5,
                    suggested_writer_use="可在描写中自然体现世界观元素",
                    suggested_director_use="可作为世界观的自然补充",
                    must_not_assert_as_fact=True,
                    must_not_commit_state=True,
                    created_at=now,
                ))

        # Strategy 7: Social background signal
        if len(candidates) < max_candidates:
            ev_refs = [ev.evidence_id for ev in evidence if ev.source_type == "scene_context"]
            if ev_refs:
                candidates.append(WorldLifeCandidate(
                    candidate_id=f"wlc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=WorldLifeKind.SOCIAL_BACKGROUND_SIGNAL,
                    title="社会背景信号",
                    summary="基于当前场景的社会背景，可在描写中体现自然的社会氛围",
                    world_layer=WorldLayer.SOCIAL_WORLD,
                    narrative_function="增强社会在场感",
                    focus_entities=[],
                    focus_location=scene_location,
                    foundation_facts=["场景存在社会背景"],
                    evidence_refs=ev_refs,
                    activation_conditions=["描写场景时自然提及社会氛围"],
                    visibility_mode=VisibilityMode.BACKGROUND,
                    player_agency_risk=0.0,
                    continuity_risk=0.1,
                    state_change_risk=0.0,
                    novelty_score=0.4,
                    relevance_score=0.5,
                    confidence=0.5,
                    suggested_writer_use="可在描写中自然体现人群、声音、活动等社会背景",
                    suggested_director_use="可作为社会氛围的自然补充",
                    must_not_assert_as_fact=True,
                    must_not_commit_state=True,
                    created_at=now,
                ))

        return candidates[:max_candidates]
