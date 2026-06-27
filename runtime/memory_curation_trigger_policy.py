"""MemoryCurationTriggerPolicy — deterministic trigger rules for Memory Curator.

Decides whether memory curation should run after an accepted turn.
Uses deterministic rules — no LLM judgment.

Only fires when ALL of:
  - QualityDecision = ACCEPT
  - CardStateCommit = SUCCESS
  - TurnRecordCommit = SUCCESS
  - Current TurnRecord is accepted
  - cardId / sessionId / turnId are valid
  - That turnId has not already been successfully curated
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..contracts.quality_decision import QualityDecision, QualityVerdict
from ..contracts.card_state_commit import CardStateCommitResult, CardStateCommitStatus
from ..contracts.turn_record import TurnRecord
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.memory_curation_trigger_diagnostics import (
    MemoryCurationTriggerDiagnostics,
)


# Promise / commitment keywords
_PROMISE_KEYWORDS = [
    r"答应", r"承诺", r"保证", r"约定", r"约定过",
    r"保证过", r"承诺过", r"答应过", r"欠", r"兑现",
]

# Secret / hidden information keywords
_SECRET_KEYWORDS = [
    r"秘密", r"隐瞒", r"隐藏", r"暗中", r"真相",
    r"假装", r"欺骗", r"谎言", r"身份",
]

# Relationship change keywords
_RELATIONSHIP_KEYWORDS = [
    r"关系", r"信任", r"怀疑", r"敌意", r"友情",
    r"爱情", r"仇恨", r"和解", r"决裂", r"背叛",
]

# Goal / intention keywords
_GOAL_KEYWORDS = [
    r"目标", r"计划", r"打算", r"想要", r"决定",
    r"决心", r"意图", r"追求",
]

# Event / stage change keywords
_EVENT_KEYWORDS = [
    r"事件", r"阶段", r"进展", r"完成", r"结束",
    r"开始", r"触发", r"推进", r"转折",
]

# Long-term impact keywords
_LONGTERM_KEYWORDS = [
    r"永远", r"长期", r"以后", r"未来", r"从此",
    r"之后", r"改变", r"影响",
]

_PROMISE_RE = re.compile("|".join(_PROMISE_KEYWORDS))
_SECRET_RE = re.compile("|".join(_SECRET_KEYWORDS))
_RELATIONSHIP_RE = re.compile("|".join(_RELATIONSHIP_KEYWORDS))
_GOAL_RE = re.compile("|".join(_GOAL_KEYWORDS))
_EVENT_RE = re.compile("|".join(_EVENT_KEYWORDS))
_LONGTERM_RE = re.compile("|".join(_LONGTERM_KEYWORDS))


class MemoryCurationTriggerPolicy:
    """Deterministic trigger policy for Memory Curator Agent.

    No LLM judgment. No randomness. Pure rule-based evaluation.
    """

    def evaluate(
        self,
        quality_decision: QualityDecision | None,
        card_state_commit_result: CardStateCommitResult | None,
        turn_record_committed: bool,
        turn_record: TurnRecord | None,
        snapshot: RoundSnapshot | None,
        existing_curated_turn_ids: set[str] | None = None,
    ) -> MemoryCurationTriggerDiagnostics:
        """Evaluate whether memory curation should be triggered."""
        reasons: list[str] = []
        domains: list[str] = []
        risk_level = "none"

        # --- Hard gate checks (all must pass) ---

        # Gate 1: QualityDecision must exist and be ACCEPT
        if quality_decision is None:
            return MemoryCurationTriggerDiagnostics(
                should_trigger=False,
                skip_reason="no_quality_decision",
            )
        if quality_decision.verdict != QualityVerdict.ACCEPTED:
            return MemoryCurationTriggerDiagnostics(
                should_trigger=False,
                skip_reason=f"quality_not_accepted: {quality_decision.verdict.value}",
            )

        # Gate 2: CardStateCommit must be SUCCESS (or None = no patch = trivially ok)
        if card_state_commit_result is not None:
            if card_state_commit_result.status != CardStateCommitStatus.ACCEPTED:
                return MemoryCurationTriggerDiagnostics(
                    should_trigger=False,
                    skip_reason=f"card_state_commit_failed: {card_state_commit_result.status}",
                )

        # Gate 3: TurnRecordCommit must be SUCCESS
        if not turn_record_committed:
            return MemoryCurationTriggerDiagnostics(
                should_trigger=False,
                skip_reason="turn_record_not_committed",
            )

        # Gate 4: TurnRecord must exist and be valid
        if turn_record is None:
            return MemoryCurationTriggerDiagnostics(
                should_trigger=False,
                skip_reason="no_turn_record",
            )
        if not turn_record.turn_id or not turn_record.card_id or not turn_record.session_id:
            return MemoryCurationTriggerDiagnostics(
                should_trigger=False,
                skip_reason="invalid_turn_record_ids",
            )

        # Gate 5: Idempotency — this turn must not already have been curated
        if existing_curated_turn_ids and turn_record.turn_id in existing_curated_turn_ids:
            return MemoryCurationTriggerDiagnostics(
                should_trigger=False,
                skip_reason=f"already_curated: {turn_record.turn_id}",
            )

        # --- Signal-based trigger rules ---
        accepted_output = turn_record.writer_output or ""
        player_input = turn_record.player_input or ""

        # Rule 1: Promise / commitment signals
        if _PROMISE_RE.search(player_input) or _PROMISE_RE.search(accepted_output):
            reasons.append("回合包含承诺或约定信号")
            domains.append("promise")
            risk_level = "medium"

        # Rule 2: Secret / hidden information signals
        if _SECRET_RE.search(player_input) or _SECRET_RE.search(accepted_output):
            reasons.append("回合包含秘密或隐瞒信号")
            domains.append("secret")
            risk_level = "high"

        # Rule 3: Relationship change signals
        if _RELATIONSHIP_RE.search(player_input) or _RELATIONSHIP_RE.search(accepted_output):
            reasons.append("回合包含关系变化信号")
            domains.append("relationship")
            if risk_level == "none":
                risk_level = "medium"

        # Rule 4: Goal / intention signals
        if _GOAL_RE.search(player_input) or _GOAL_RE.search(accepted_output):
            reasons.append("回合包含目标或意图信号")
            domains.append("goal")
            if risk_level == "none":
                risk_level = "low"

        # Rule 5: Event / stage change signals
        if _EVENT_RE.search(player_input) or _EVENT_RE.search(accepted_output):
            reasons.append("回合包含事件阶段变化信号")
            domains.append("event_stage")
            if risk_level == "none":
                risk_level = "medium"

        # Rule 6: Long-term impact signals
        if _LONGTERM_RE.search(accepted_output):
            reasons.append("回合包含长期影响信号")
            domains.append("longterm_impact")
            if risk_level == "none":
                risk_level = "low"

        # Rule 7: ActiveMemory near capacity (>=14) suggests curation needed
        if snapshot and len(snapshot.active_memories) >= 14:
            reasons.append(f"活跃记忆接近上限: {len(snapshot.active_memories)}/15")
            domains.append("active_memory_pressure")
            risk_level = "high"

        # Rule 8: ActiveMemory has items that may be resolvable by this turn
        if snapshot:
            for mem in snapshot.active_memories:
                kind = mem.get("kind", "")
                if kind in ("promise", "secret", "misunderstanding", "unresolved_thread"):
                    # Check if the accepted output mentions the same entities
                    entity_refs = mem.get("entity_refs", [])
                    for entity in entity_refs:
                        if entity in accepted_output:
                            reasons.append(f"回合推进了既有活跃记忆: {kind} ({entity})")
                            domains.append("active_memory_update")
                            if risk_level == "none":
                                risk_level = "medium"
                            break

        # Rule 9: CardState delta exists (something changed)
        if card_state_commit_result is not None and card_state_commit_result.success:
            reasons.append("CardState已变更，值得记录长期事实")
            domains.append("card_state_change")
            if risk_level == "none":
                risk_level = "low"

        # Deduplicate domains
        domains = list(dict.fromkeys(domains))

        # If no signals found, this is a low-value turn — no-op
        should_trigger = len(reasons) > 0
        skip_reason = "" if should_trigger else "no_long_term_signals"

        # Build idempotency key
        idempotency_key = ""
        if should_trigger and turn_record:
            idempotency_key = f"curation:{turn_record.turn_id}"

        return MemoryCurationTriggerDiagnostics(
            should_trigger=should_trigger,
            trigger_reasons=reasons,
            curation_domains=domains,
            max_active_candidates=5,
            max_rag_candidates=5,
            idempotency_key=idempotency_key,
            risk_level=risk_level,
            skip_reason=skip_reason,
        )
