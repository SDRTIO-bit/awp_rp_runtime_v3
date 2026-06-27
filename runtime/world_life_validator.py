"""WorldLifeValidator — validates world-life candidates.

Rejects:
- Candidates without evidence
- Candidates that assert facts as having happened
- Candidates that modify state or advance timeline
- Candidates that override player agency
- Candidates that conflict with CardState
- Candidates that auto-advance events, relationships, or scenes
"""
from __future__ import annotations

import re

from ..contracts.world_life_candidate import WorldLifeCandidate
from ..contracts.round_snapshot import RoundSnapshot


# Patterns that indicate a candidate is asserting a fact as having happened
_EVENT_ASSERTION_PATTERNS = [
    re.compile(r"已经发生"),
    re.compile(r"已经完成"),
    re.compile(r"已经暴露"),
    re.compile(r"已经公开"),
    re.compile(r"突然闯入"),
    re.compile(r"突然出现"),
    re.compile(r"自动接受"),
    re.compile(r"自动表态"),
    re.compile(r"自动离开"),
    re.compile(r"直接推进"),
    re.compile(r"直接修改"),
    re.compile(r"直接改变"),
]

# Patterns that indicate state modification
_STATE_MODIFICATION_PATTERNS = [
    re.compile(r"set_flag", re.IGNORECASE),
    re.compile(r"set_variable", re.IGNORECASE),
    re.compile(r"increment", re.IGNORECASE),
    re.compile(r"append_unique", re.IGNORECASE),
    re.compile(r"修改状态"),
    re.compile(r"改变关系"),
    re.compile(r"推进时间"),
    re.compile(r"转移地点"),
    re.compile(r"自动推进"),
    re.compile(r"自动触发"),
    re.compile(r"自动改变"),
]

# Patterns that indicate player agency violation
_PLAYER_AGENCY_PATTERNS = [
    re.compile(r"玩家接受"),
    re.compile(r"玩家同意"),
    re.compile(r"玩家表态"),
    re.compile(r"玩家决定"),
    re.compile(r"玩家选择"),
    re.compile(r"让玩家"),
    re.compile(r"代替玩家"),
    re.compile(r"替玩家"),
    re.compile(r"强制玩家"),
]

# Patterns that indicate auto-advance of events/relationships
_AUTO_ADVANCE_PATTERNS = [
    re.compile(r"事件已经"),
    re.compile(r"关系已经"),
    re.compile(r"阶段已经"),
    re.compile(r"自动进入"),
    re.compile(r"自动触发"),
    re.compile(r"自动推进"),
    re.compile(r"三天过去"),
    re.compile(r"时间自动"),
]


class WorldLifeValidator:
    """Validates WorldLifeCandidate for correctness and safety."""

    def validate(
        self,
        candidate: WorldLifeCandidate,
        snapshot: RoundSnapshot | None = None,
    ) -> list[str]:
        """Validate a WorldLifeCandidate.

        Returns list of error messages. Empty = valid.
        """
        errors: list[str] = []

        # Rule 1: Must have evidence
        if not candidate.evidence_refs:
            errors.append(
                f"候选 {candidate.candidate_id} 缺少证据引用: "
                "无证据的候选不得成为可采纳世界活性建议"
            )

        # Rule 2: Must have foundation facts
        if not candidate.foundation_facts:
            errors.append(
                f"候选 {candidate.candidate_id} 缺少事实基础: "
                "无事实基础的候选不得成为可采纳世界活性建议"
            )

        # Rule 3: mustNotAssertAsFact must be True
        if not candidate.must_not_assert_as_fact:
            errors.append(
                f"候选 {candidate.candidate_id} mustNotAssertAsFact不为True: "
                "世界活性候选不得断言事实已发生"
            )

        # Rule 4: mustNotCommitState must be True
        if not candidate.must_not_commit_state:
            errors.append(
                f"候选 {candidate.candidate_id} mustNotCommitState不为True: "
                "世界活性候选不得提交状态变更"
            )

        # Rule 5: Must not assert events as having happened
        text_to_check = f"{candidate.title} {candidate.summary} {candidate.suggested_writer_use}"
        for pattern in _EVENT_ASSERTION_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 包含事件断言: "
                    f"'{pattern.pattern}' — 世界活性不得宣称事件已发生"
                )
                break

        # Rule 6: Must not contain state modification requests
        for pattern in _STATE_MODIFICATION_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 包含状态修改请求: "
                    f"'{pattern.pattern}' — 世界活性不得修改状态或推进时间"
                )
                break

        # Rule 7: Must not override player agency
        for pattern in _PLAYER_AGENCY_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 侵犯玩家代理权: "
                    f"'{pattern.pattern}' — 世界活性不得代替玩家做选择"
                )
                break

        # Rule 8: Must not auto-advance events/relationships
        for pattern in _AUTO_ADVANCE_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 自动推进事件/关系: "
                    f"'{pattern.pattern}' — 世界活性不得自动推进事件阶段或关系"
                )
                break

        # Rule 9: Player agency risk must be low
        if candidate.player_agency_risk > 0.5:
            errors.append(
                f"候选 {candidate.candidate_id} 玩家代理权风险过高: "
                f"{candidate.player_agency_risk:.2f} > 0.5"
            )

        # Rule 10: State change risk must be zero
        if candidate.state_change_risk > 0.1:
            errors.append(
                f"候选 {candidate.candidate_id} 状态变更风险过高: "
                f"{candidate.state_change_risk:.2f} > 0.1"
            )

        # Rule 11: Must not contain memory commit proposals
        for field_text in [candidate.suggested_director_use, candidate.suggested_writer_use]:
            if any(kw in field_text.lower() for kw in ["memory_commit", "rag_commit", "active_memory_write"]):
                errors.append(
                    f"候选 {candidate.candidate_id} 包含MemoryCommit指令: "
                    "WorldLifeAgent不得提出MemoryCommit请求"
                )
                break

        return errors

    def validate_batch(
        self,
        candidates: list[WorldLifeCandidate],
        snapshot: RoundSnapshot | None = None,
    ) -> tuple[list[WorldLifeCandidate], list[tuple[WorldLifeCandidate, list[str]]]]:
        """Validate a batch of candidates.

        Returns (valid_candidates, rejected_with_reasons).
        """
        valid = []
        rejected = []
        for c in candidates:
            errors = self.validate(c, snapshot)
            if errors:
                rejected.append((c, errors))
            else:
                valid.append(c)
        return valid, rejected
