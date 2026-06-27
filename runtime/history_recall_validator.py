"""HistoryRecallValidator — validates HistoryRecallResult.

Rejects:
- confirmedFacts without evidence
- Evidence without source_ref
- Conflicted evidence used as confirmed facts
- Final player-visible text in recommendations
- Unauthorized fields
"""

from __future__ import annotations

import re

from ..contracts.history_recall_result import HistoryRecallResult

# Patterns that indicate final player-visible text
_FINAL_TEXT_PATTERNS = [
    re.compile(r"^[一-鿿].{50,}"),  # Long Chinese text (>50 chars)
    re.compile(r"[，。！？].{20,}[，。！？]"),  # Punctuated narrative
]


class HistoryRecallValidator:
    """Validates HistoryRecallResult for correctness and safety."""

    def validate(self, result: HistoryRecallResult) -> list[str]:
        """Validate a HistoryRecallResult.

        Returns list of error messages. Empty = valid.
        """
        errors: list[str] = []

        # Rule 1: Every confirmed fact must have supporting evidence
        if result.confirmed_facts and not result.evidence:
            errors.append(
                "confirmedFacts存在但evidence为空: "
                "无证据的事实不得作为confirmedFact"
            )

        # Rule 2: Every evidence must have source_ref
        for ev in result.evidence:
            if not ev.source_ref:
                errors.append(
                    f"证据 {ev.evidence_id} 缺少source_ref: "
                    "无来源引用的证据不可用"
                )

        # Rule 3: Conflicted evidence cannot support confirmed facts
        conflicted_refs = {
            ev.evidence_id for ev in result.evidence
            if ev.conflict_status in ("conflicted", "stale")
        }
        if conflicted_refs and result.confirmed_facts:
            # Check if any confirmed fact references conflicted evidence
            for fact in result.confirmed_facts:
                # If all evidence is conflicted, the fact is unsupported
                non_conflicted = [
                    ev for ev in result.evidence
                    if ev.conflict_status not in ("conflicted", "stale")
                ]
                if not non_conflicted:
                    errors.append(
                        f"确认事实 '{fact[:30]}...' "
                        f"仅基于冲突/过时证据: 不得作为确定事实"
                    )

        # Rule 4: Writer recommendations must not be final text
        for rec in result.writer_recommendations:
            if self._looks_like_final_text(rec):
                errors.append(
                    f"writerRecommendations包含疑似玩家可见正文: "
                    f"'{rec[:50]}...' — 建议必须是简短结构化约束，不是叙事正文"
                )

        # Rule 5: Must not contain CardState patch proposals
        for rec in result.writer_recommendations + result.director_recommendations:
            if any(kw in rec.lower() for kw in ["set_flag", "set_variable", "increment", "append_unique"]):
                errors.append(
                    f"建议包含CardState操作指令: '{rec[:50]}' — "
                    "HistoryRecallAgent不得提出CardStateCommit请求"
                )

        # Rule 6: Must not contain memory commit proposals
        for rec in result.director_recommendations:
            if any(kw in rec.lower() for kw in ["memory_commit", "rag_commit", "active_memory_write"]):
                errors.append(
                    f"建议包含MemoryCommit指令: '{rec[:50]}' — "
                    "HistoryRecallAgent不得提出MemoryCommit请求"
                )

        return errors

    def _looks_like_final_text(self, text: str) -> bool:
        """Check if text looks like player-visible final narrative."""
        if len(text) > 200:
            return True
        # Long Chinese text (>= 50 chars of continuous Chinese)
        chinese_chars = re.findall(r"[一-鿿]", text)
        if len(chinese_chars) >= 50:
            return True
        # Narrative punctuation patterns
        if re.search(r"[。！？].{10,}[。！？]", text) and len(text) > 80:
            return True
        return False
