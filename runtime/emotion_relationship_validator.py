"""EmotionRelationshipValidator — validates emotion/relationship candidates.

Rejects:
- Candidates without evidence
- Candidates without foundation facts
- Candidates with mustNotAssertAsFact=False
- Candidates with mustNotModifyRelationship=False
- Candidates that assert relationship events as having happened
- Candidates that override player agency
- Candidates that modify relationships
- Candidates with sudden shifts
- Candidates with player_agency_risk > 0.5
- Candidates with sudden_shift_risk > 0.5
- Candidates that propose memory commits
"""

from __future__ import annotations

import re

from ..contracts.emotion_relationship_candidate import EmotionRelationshipCandidate
from ..contracts.round_snapshot import RoundSnapshot


# Patterns that indicate a candidate is asserting a relationship event as having happened
_RELATIONSHIP_EVENT_PATTERNS = [
    re.compile(r"已经原谅"),
    re.compile(r"已经接受"),
    re.compile(r"已经表白"),
    re.compile(r"已经背叛"),
    re.compile(r"已经和好"),
    re.compile(r"突然告白"),
    re.compile(r"突然背叛"),
    re.compile(r"自动接受"),
    re.compile(r"自动表态"),
]

# Patterns that indicate player agency violation
_PLAYER_AGENCY_PATTERNS = [
    re.compile(r"玩家接受"),
    re.compile(r"玩家同意"),
    re.compile(r"代替玩家"),
    re.compile(r"玩家被默认"),
    re.compile(r"玩家表态"),
    re.compile(r"玩家决定"),
    re.compile(r"让玩家"),
    re.compile(r"替玩家"),
]

# Patterns that indicate relationship modification
_RELATIONSHIP_MODIFICATION_PATTERNS = [
    re.compile(r"关系值.*增加"),
    re.compile(r"好感.*增加"),
    re.compile(r"修改关系"),
    re.compile(r"改变关系"),
    re.compile(r"提升好感"),
    re.compile(r"降低好感"),
    re.compile(r"关系升级"),
    re.compile(r"关系降级"),
]

# Patterns that indicate sudden shifts
_SUDDEN_SHIFT_PATTERNS = [
    re.compile(r"突然升温"),
    re.compile(r"突然冷漠"),
    re.compile(r"立刻原谅"),
    re.compile(r"立刻信任"),
    re.compile(r"瞬间改变"),
    re.compile(r"马上和好"),
    re.compile(r"立即接受"),
]


class EmotionRelationshipValidator:
    """Validates EmotionRelationshipCandidate for correctness and safety."""

    def validate(
        self,
        candidate: EmotionRelationshipCandidate,
        snapshot: RoundSnapshot | None = None,
    ) -> list[str]:
        """Validate an EmotionRelationshipCandidate.

        Returns list of error messages. Empty = valid.
        """
        errors: list[str] = []

        # Rule 1: Must have evidence
        if not candidate.evidence_refs:
            errors.append(
                f"候选 {candidate.candidate_id} 缺少证据引用: "
                "无证据的候选不得成为可采纳情感关系建议"
            )

        # Rule 2: Must have foundation facts
        if not candidate.foundation_facts:
            errors.append(
                f"候选 {candidate.candidate_id} 缺少事实基础: "
                "无事实基础的候选不得成为可采纳情感关系建议"
            )

        # Rule 3: mustNotAssertAsFact must be True
        if not candidate.must_not_assert_as_fact:
            errors.append(
                f"候选 {candidate.candidate_id} mustNotAssertAsFact不为True: "
                "情感关系候选不得断言事实已发生"
            )

        # Rule 4: mustNotModifyRelationship must be True
        if not candidate.must_not_modify_relationship:
            errors.append(
                f"候选 {candidate.candidate_id} mustNotModifyRelationship不为True: "
                "情感关系候选不得修改关系"
            )

        # Rule 5: Must not assert relationship events as having happened
        text_to_check = f"{candidate.summary} {candidate.suggested_writer_use} {candidate.relationship_state_interpretation}"
        for pattern in _RELATIONSHIP_EVENT_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 包含关系事件断言: "
                    f"'{pattern.pattern}' — 情感关系不得宣称关系事件已发生"
                )
                break

        # Rule 6: Must not override player agency
        for pattern in _PLAYER_AGENCY_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 侵犯玩家代理权: "
                    f"'{pattern.pattern}' — 情感关系不得代替玩家做选择"
                )
                break

        # Rule 7: Must not contain relationship modification
        for pattern in _RELATIONSHIP_MODIFICATION_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 包含关系修改请求: "
                    f"'{pattern.pattern}' — 情感关系不得修改关系数值或状态"
                )
                break

        # Rule 8: Must not contain sudden shifts
        for pattern in _SUDDEN_SHIFT_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"候选 {candidate.candidate_id} 包含突然转变: "
                    f"'{pattern.pattern}' — 情感关系不得推动突然的关系转变"
                )
                break

        # Rule 9: Player agency risk must be low
        if candidate.player_agency_risk > 0.5:
            errors.append(
                f"候选 {candidate.candidate_id} 玩家代理权风险过高: "
                f"{candidate.player_agency_risk:.2f} > 0.5"
            )

        # Rule 10: Sudden shift risk must be low
        if candidate.sudden_shift_risk > 0.5:
            errors.append(
                f"候选 {candidate.candidate_id} 突然转变风险过高: "
                f"{candidate.sudden_shift_risk:.2f} > 0.5"
            )

        # Rule 11: Must not contain memory commit proposals
        for field_text in [candidate.suggested_director_use, candidate.suggested_writer_use]:
            if any(kw in field_text.lower() for kw in ["memory_commit", "rag_commit", "active_memory_write"]):
                errors.append(
                    f"候选 {candidate.candidate_id} 包含MemoryCommit指令: "
                    "EmotionRelationshipAgent不得提出MemoryCommit请求"
                )
                break

        return errors

    def validate_batch(
        self,
        candidates: list[EmotionRelationshipCandidate],
        snapshot: RoundSnapshot | None = None,
    ) -> tuple[list[EmotionRelationshipCandidate], list[tuple[EmotionRelationshipCandidate, list[str]]]]:
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
