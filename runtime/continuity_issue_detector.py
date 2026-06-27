"""ContinuityIssueDetector — detects continuity issues from evidence.

This is the Fake Adapter for V1. It generates deterministic issues
from snapshot data and evidence. A future LLM Adapter can replace this.

Continuity issues are NOT facts — they are risk warnings that the Writer
must not contradict confirmed facts.

It CANNOT:
- Create new facts
- Write missing events
- Make choices for the player
- Modify character positions
- Advance time
- Modify relationships
- Let characters suddenly know unlearned information
- Generate StateUpdateProposal
- Generate MemoryCommitPlan
- Directly modify CardState
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.continuity_evidence import ContinuityEvidence, EvidenceSourceType
from ..contracts.continuity_issue import (
    ContinuityIssue, ContinuityIssueKind, ContinuitySeverity,
)
from .continuity_trigger_policy import ContinuityTriggerResult


class ContinuityIssueDetector:
    """Detects continuity issues from evidence and snapshot data.

    Fake Adapter mode: deterministic detection from snapshot data.
    Future: LLM Adapter can detect more nuanced issues.
    """

    def detect(
        self,
        snapshot: RoundSnapshot,
        trigger_result: ContinuityTriggerResult,
        evidence: list[ContinuityEvidence],
        max_issues: int = 6,
    ) -> list[ContinuityIssue]:
        """Detect continuity issues from evidence.

        Returns list of issues, each grounded in evidence.
        """
        now = datetime.now(timezone.utc).isoformat()
        issues: list[ContinuityIssue] = []
        scene_location = snapshot.card_state.scene_state.location if snapshot.card_state.scene_state else ""

        # Strategy 1: Location continuity — CardState says scene is at X
        if scene_location and "location_change" in trigger_result.continuity_domains:
            card_ev = [e for e in evidence if e.source_type == EvidenceSourceType.CARD_STATE]
            if card_ev:
                issues.append(ContinuityIssue(
                    issue_id=f"ci_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=ContinuityIssueKind.LOCATION_CONFLICT,
                    severity=ContinuitySeverity.BLOCKING,
                    summary=f"CardState 确认当前场景在 {scene_location}；正文不得直接写成其他地点",
                    affected_entities=[],
                    affected_locations=[scene_location],
                    foundation_facts=[f"当前地点: {scene_location}"],
                    evidence_refs=[e.evidence_id for e in card_ev],
                    priority_decision="CardState 权威优先",
                    writer_constraint=f"正文中的场景必须在 {scene_location}，除非有明确的场景切换描写",
                    director_recommendation="如需切换场景，应由 Director 明确规划",
                    must_not_assert_as_fact=True,
                    must_not_modify_state=True,
                    created_at=now,
                ))

        # Strategy 2: Character availability — NPCs in recent turns
        if "entrance_exit" in trigger_result.continuity_domains:
            for turn in snapshot.recent_turn_records[:3]:
                output = turn.writer_output or ""
                # Check for exit signals
                exit_keywords = ["离开", "退场", "走开", "消失"]
                for kw in exit_keywords:
                    if kw in output:
                        issues.append(ContinuityIssue(
                            issue_id=f"ci_{uuid.uuid4().hex[:8]}",
                            trace_id=snapshot.trace_id,
                            snapshot_id=snapshot.snapshot_id,
                            kind=ContinuityIssueKind.CHARACTER_AVAILABILITY_CONFLICT,
                            severity=ContinuitySeverity.WARNING,
                            summary=f"回合 {turn.turn_id} 中有角色 {kw}；没有回归依据时不应让其参与当前对话",
                            affected_turns=[turn.turn_id],
                            foundation_facts=[f"回合 {turn.turn_id}: {output[:100]}"],
                            evidence_refs=[f"turn:{turn.turn_id}"],
                            priority_decision="accepted Turn 证据",
                            writer_constraint=f"离场角色不应突然出现，除非有明确的回归描写",
                            director_recommendation="如需角色回归，应有合理的叙事依据",
                            must_not_assert_as_fact=True,
                            must_not_modify_state=True,
                            created_at=now,
                        ))
                        break

        # Strategy 3: Knowledge boundary — secrets and identity
        if "knowledge_boundary" in trigger_result.continuity_domains:
            for mem in snapshot.active_memories:
                kind = mem.get("kind", "")
                if kind in ("secret", "misunderstanding", "identity"):
                    entity_refs = mem.get("entity_refs", [])
                    issues.append(ContinuityIssue(
                        issue_id=f"ci_{uuid.uuid4().hex[:8]}",
                        trace_id=snapshot.trace_id,
                        snapshot_id=snapshot.snapshot_id,
                        kind=ContinuityIssueKind.KNOWLEDGE_BOUNDARY_CONFLICT,
                        severity=ContinuitySeverity.BLOCKING,
                        summary=f"活跃记忆 {mem.get('memory_id', '?')} 包含秘密/误会/身份信息；角色不应表现出已知真相",
                        affected_entities=entity_refs,
                        foundation_facts=[mem.get("summary", "")],
                        evidence_refs=[f"am:{mem.get('memory_id', '')}"],
                        priority_decision="ActiveMemory 证据",
                        writer_constraint="角色的知识边界必须与其实际获知的信息一致",
                        director_recommendation="秘密揭露应由 Director 明确规划",
                        must_not_assert_as_fact=True,
                        must_not_modify_state=True,
                        created_at=now,
                    ))

        # Strategy 4: Promise resolution — unresolved promises
        if "promise" in trigger_result.continuity_domains:
            for mem in snapshot.active_memories:
                kind = mem.get("kind", "")
                if kind in ("promise", "commitment", "debt"):
                    issues.append(ContinuityIssue(
                        issue_id=f"ci_{uuid.uuid4().hex[:8]}",
                        trace_id=snapshot.trace_id,
                        snapshot_id=snapshot.snapshot_id,
                        kind=ContinuityIssueKind.PROMISE_RESOLUTION_RISK,
                        severity=ContinuitySeverity.WARNING,
                        summary=f"活跃记忆 {mem.get('memory_id', '?')} 包含未兑现承诺；不得写成已经兑现",
                        affected_entities=mem.get("entity_refs", []),
                        foundation_facts=[mem.get("summary", "")],
                        evidence_refs=[f"am:{mem.get('memory_id', '')}"],
                        priority_decision="ActiveMemory 证据",
                        writer_constraint="未兑现的承诺不得在正文中被当作已兑现",
                        director_recommendation="承诺兑现应由 Director 明确规划",
                        must_not_assert_as_fact=True,
                        must_not_modify_state=True,
                        created_at=now,
                    ))

        # Strategy 5: Event stage continuity
        if "event_stage" in trigger_result.continuity_domains:
            for mem in snapshot.active_memories:
                kind = mem.get("kind", "")
                if kind in ("event", "world_event"):
                    issues.append(ContinuityIssue(
                        issue_id=f"ci_{uuid.uuid4().hex[:8]}",
                        trace_id=snapshot.trace_id,
                        snapshot_id=snapshot.snapshot_id,
                        kind=ContinuityIssueKind.EVENT_STAGE_CONFLICT,
                        severity=ContinuitySeverity.WARNING,
                        summary=f"事件 {mem.get('memory_id', '?')} 处于特定阶段；不得自动推进或跳过",
                        affected_entities=mem.get("entity_refs", []),
                        foundation_facts=[mem.get("summary", "")],
                        evidence_refs=[f"am:{mem.get('memory_id', '')}"],
                        priority_decision="ActiveMemory 证据",
                        writer_constraint="事件阶段不得在正文中被自动推进",
                        director_recommendation="事件推进应由 Director 明确规划",
                        must_not_assert_as_fact=True,
                        must_not_modify_state=True,
                        created_at=now,
                    ))

        # Strategy 6: Timeline consistency
        if "time_change" in trigger_result.continuity_domains:
            turn_ev = [e for e in evidence if e.source_type == EvidenceSourceType.ACCEPTED_TURN]
            if turn_ev:
                issues.append(ContinuityIssue(
                    issue_id=f"ci_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=ContinuityIssueKind.TIMELINE_CONFLICT,
                    severity=ContinuitySeverity.WARNING,
                    summary="玩家输入涉及时间变化；需确保时间线一致",
                    foundation_facts=[e.excerpt[:100] for e in turn_ev[:2]],
                    evidence_refs=[e.evidence_id for e in turn_ev[:2]],
                    priority_decision="accepted Turn 证据",
                    writer_constraint="时间推进必须与最近回合的时间线一致",
                    director_recommendation="大幅时间跳跃应由 Director 规划",
                    must_not_assert_as_fact=True,
                    must_not_modify_state=True,
                    created_at=now,
                ))

        return issues[:max_issues]
