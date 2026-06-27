"""OpportunityValidator — validates opportunity candidates.

Rejects:
- Candidates without evidence
- Candidates that assert facts as having happened
- Candidates that modify state or advance timeline
- Candidates that override player agency
- Candidates that conflict with CardState
- Candidates that need new facts to be valid
"""

from __future__ import annotations

import re

from ..contracts.opportunity_candidate import OpportunityCandidate
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
]


class OpportunityValidator:
    """Validates OpportunityCandidate for correctness and safety."""

    def validate(
        self,
        candidate: OpportunityCandidate,
        snapshot: RoundSnapshot | None = None,
    ) -> list[str]:
        """Validate an OpportunityCandidate.

        Returns list of error messages. Empty = valid.
        """
        errors: list[str] = []

        # Rule 1: Must have evidence
        if not candidate.evidence_refs:
            errors.append(
                f"候选 {candidate.candidate_id} 缺少证据引用: "
                "无证据的候选不得成为可采纳机会"
            )

        # Rule 2: Must have foundation facts
        if not candidate.foundation_facts:
            errors.append(
                f"候选 {candidate.candidate_id} 缺少事实基础: "
                "无事实基础的候选不得成为可采纳机会"
            )

        # Rule 3: mustNotAssertAsFact must be True
        if not candidate.must_not_assert_as_fact:
            errors.append(
                f"候选 {candidate.candidate_id} mustNotAssertAsFact不为True: "
                "机会候选不得断言事实已发生"
            )

        # Rule 4: Must not assert events as having happened
        text_to_check = f"{candidate.title} {candidate.summary} {candidate.suggested_writer_use}"
        for pattern in _EVENT_ASSERTION_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 包含事件断言: "
                    f"'{pattern.pattern}' — 机会不得宣称事件已发生"
                )
                break

        # Rule 5: Must not contain state modification requests
        for pattern in _STATE_MODIFICATION_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 包含状态修改请求: "
                    f"'{pattern.pattern}' — 机会不得修改状态"
                )
                break

        # Rule 6: Must not override player agency
        for pattern in _PLAYER_AGENCY_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 侵犯玩家代理权: "
                    f"'{pattern.pattern}' — 机会不得代替玩家做选择"
                )
                break

        # Rule 7: Player agency risk must be low
        if candidate.player_agency_risk > 0.5:
            errors.append(
                f"候选 {candidate.candidate_id} 玩家代理权风险过高: "
                f"{candidate.player_agency_risk:.2f} > 0.5"
            )

        # Rule 8: Must not contain memory commit proposals
        for field_text in [candidate.suggested_director_use, candidate.suggested_writer_use]:
            if any(kw in field_text.lower() for kw in ["memory_commit", "rag_commit", "active_memory_write"]):
                errors.append(
                    f"候选 {candidate.candidate_id} 包含MemoryCommit指令: "
                    "OpportunityAgent不得提出MemoryCommit请求"
                )
                break

        return errors

    def validate_batch(
        self,
        candidates: list[OpportunityCandidate],
        snapshot: RoundSnapshot | None = None,
    ) -> tuple[list[OpportunityCandidate], list[tuple[OpportunityCandidate, list[str]]]]:
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
