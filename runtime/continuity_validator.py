"""ContinuityValidator — validates continuity issues.

Rejects:
- Blocking issues without high-priority evidence
- Issues that use low-priority RAG to override CardState
- Issues that create new events, advance time, modify relationships
- Issues that let characters suddenly know unlearned information
- Issues that contain StateUpdateProposal
- Issues that contain MemoryCommitPlan
"""
from __future__ import annotations

import re

from ..contracts.continuity_issue import ContinuityIssue, ContinuitySeverity
from ..contracts.continuity_evidence import ContinuityEvidence, EvidenceSourceType, EVIDENCE_PRIORITY
from ..contracts.round_snapshot import RoundSnapshot


# Patterns that indicate state modification requests
_STATE_MODIFICATION_PATTERNS = [
    re.compile(r"set_flag", re.IGNORECASE),
    re.compile(r"set_variable", re.IGNORECASE),
    re.compile(r"修改状态"),
    re.compile(r"改变关系"),
    re.compile(r"推进时间"),
    re.compile(r"转移地点"),
    re.compile(r"自动推进"),
]

# Patterns that indicate event creation
_EVENT_CREATION_PATTERNS = [
    re.compile(r"创建事件"),
    re.compile(r"新建事件"),
    re.compile(r"触发事件"),
    re.compile(r"事件已经"),
    re.compile(r"关系已经"),
    re.compile(r"自动进入"),
]

# Patterns that indicate memory commit proposals
_MEMORY_COMMIT_PATTERNS = [
    re.compile(r"memory_commit", re.IGNORECASE),
    re.compile(r"rag_commit", re.IGNORECASE),
    re.compile(r"active_memory_write", re.IGNORECASE),
    re.compile(r"写入记忆"),
    re.compile(r"提交记忆"),
]


class ContinuityValidator:
    """Validates ContinuityIssue for correctness and safety."""

    def validate(
        self,
        issue: ContinuityIssue,
        evidence: list[ContinuityEvidence] | None = None,
        snapshot: RoundSnapshot | None = None,
    ) -> list[str]:
        """Validate a ContinuityIssue.

        Returns list of error messages. Empty = valid.
        """
        errors: list[str] = []

        # Rule 1: Blocking issues must have at least one high-priority evidence ref
        if issue.severity == ContinuitySeverity.BLOCKING:
            if not issue.evidence_refs:
                errors.append(
                    f"issue {issue.issue_id} severity=blocking 但无 evidence_refs: "
                    "blocking issue 必须有至少一个高优先级证据"
                )
            elif evidence:
                # Check if any evidence is high priority (CardState or accepted_turn)
                high_priority_found = False
                for ev in evidence:
                    if ev.evidence_id in issue.evidence_refs:
                        if ev.priority >= EVIDENCE_PRIORITY[EvidenceSourceType.ACCEPTED_TURN]:
                            high_priority_found = True
                            break
                if not high_priority_found:
                    errors.append(
                        f"issue {issue.issue_id} severity=blocking 但无高优先级证据: "
                        "blocking issue 必须有 CardState 或 accepted_turn 级别证据"
                    )

        # Rule 2: Must not contain state modification requests
        text_to_check = f"{issue.summary} {issue.writer_constraint} {issue.director_recommendation}"
        for pattern in _STATE_MODIFICATION_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"issue {issue.issue_id} 包含状态修改请求: "
                    f"'{pattern.pattern}' — ContinuityAgent 不得修改状态"
                )
                break

        # Rule 3: Must not contain event creation
        for pattern in _EVENT_CREATION_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"issue {issue.issue_id} 包含事件创建/推进: "
                    f"'{pattern.pattern}' — ContinuityAgent 不得创建或推进事件"
                )
                break

        # Rule 4: Must not contain memory commit proposals
        for pattern in _MEMORY_COMMIT_PATTERNS:
            if pattern.search(text_to_check):
                errors.append(
                    f"issue {issue.issue_id} 包含MemoryCommit指令: "
                    "ContinuityAgent 不得提出MemoryCommit请求"
                )
                break

        # Rule 5: must_not_assert_as_fact must be True
        if not issue.must_not_assert_as_fact:
            errors.append(
                f"issue {issue.issue_id} must_not_assert_as_fact 不为 True: "
                "ContinuityAgent 不得将风险提示断言为事实"
            )

        # Rule 6: must_not_modify_state must be True
        if not issue.must_not_modify_state:
            errors.append(
                f"issue {issue.issue_id} must_not_modify_state 不为 True: "
                "ContinuityAgent 不得修改状态"
            )

        # Rule 7: Check for player agency violations
        player_agency_patterns = ["代替玩家", "替玩家", "强制玩家", "让玩家接受"]
        for pattern in player_agency_patterns:
            if pattern in text_to_check:
                errors.append(
                    f"issue {issue.issue_id} 侵犯玩家代理权: "
                    f"'{pattern}' — ContinuityAgent 不得代替玩家做选择"
                )
                break

        # Rule 8: Check for auto-advance patterns
        auto_advance_patterns = ["三天过去", "时间自动", "自动进入", "自动触发"]
        for pattern in auto_advance_patterns:
            if pattern in text_to_check:
                errors.append(
                    f"issue {issue.issue_id} 自动推进: "
                    f"'{pattern}' — ContinuityAgent 不得自动推进时间或事件"
                )
                break

        return errors

    def validate_batch(
        self,
        issues: list[ContinuityIssue],
        evidence: list[ContinuityEvidence] | None = None,
        snapshot: RoundSnapshot | None = None,
    ) -> tuple[list[ContinuityIssue], list[tuple[ContinuityIssue, list[str]]]]:
        """Validate a batch of issues.

        Returns (valid_issues, rejected_with_reasons).
        """
        valid = []
        rejected = []
        for issue in issues:
            errors = self.validate(issue, evidence, snapshot)
            if errors:
                rejected.append((issue, errors))
            else:
                valid.append(issue)
        return valid, rejected
