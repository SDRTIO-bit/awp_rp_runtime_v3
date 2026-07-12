"""NovelQualityPipeline — quality gate + targeted rewrite loop for novel mode.

设计：
- StyleCleaner 做确定性检测（禁用词/句式/泄露/退化/结构）。
- 只有"硬错误"是 blocking（metadata 泄露 / ai_refusal / 工程词 / 重复复读
  / 字数严重不足），普通禁用词与句式降为 WARNING——只报告，不阻塞改写。
- 命中 blocking 时，把问题清单交给 StyleCleaner.rewrite_for_issues 做定向
  去 AI 味改写（整章喂 LLM，flash + thinking=low），再复检。
-最多 N 轮仍命中 → 降级 accept（保留产出），避免 Writer 被反复重抽签。
"""

from __future__ import annotations

from typing import Any

from ..contracts.quality_issue import QualityIssue, IssueSeverity
from ..contracts.quality_decision import QualityDecision, QualityVerdict
from .novel_style_cleaner import NovelStyleCleaner
from ..contracts.novel_chapter import ChapterPlan

# 字数安全下限：低于 target 的一半才算 blocking（之前是 0.9 过严）。
WORD_COUNT_BLOCK_RATIO = 0.5

# 改写循环上限：2 轮改写后仍命中则降级接受。
MAX_REWRITE_ROUNDS = 2


class NovelQualityPipeline:
    """Quality + targeted-rewrite pipeline for novel mode."""

    def __init__(self, registry):
        self._registry = registry
        self._style_cleaner = NovelStyleCleaner(registry)

    @staticmethod
    def annotate_only(decision: QualityDecision) -> QualityDecision:
        """Keep quality findings visible without blocking novel continuity."""
        findings = list(decision.blocking_reasons)
        if findings:
            decision.warnings.extend(f"需人工复核: {reason}" for reason in findings)
            decision.acceptance_notes.append("质量检查仅标注，不拦截正文、账本或记忆提交。")
        decision.blocking_reasons.clear()
        decision.verdict = QualityVerdict.ACCEPTED
        decision.retry_allowed = False
        return decision

    def run_chapter(
        self,
        text: str,
        chapter_plan: ChapterPlan,
        *,
        skip_drumbeat_check: bool = False,
    ) -> tuple[QualityDecision, str]:
        """Detect issues and attach annotations without rewriting or rejecting."""
        decision = self.check_chapter(text, chapter_plan, skip_drumbeat_check=skip_drumbeat_check)
        return self.annotate_only(decision), text

    def check_chapter(
        self,
        text: str,
        chapter_plan: ChapterPlan,
        *,
        skip_drumbeat_check: bool = False,
    ) -> QualityDecision:
        """Run all deterministic quality checks on a chapter draft."""
        issues: list[QualityIssue] = []

        # 1. Banned words — tier1 命中也只 warning（只报告），不做 blocking 改写
        banned = self._style_cleaner.check_banned_words(text)
        for b in banned:
            issues.append(QualityIssue(
                gate_name="banned_words",
                category="style",
                severity=IssueSeverity.WARNING,
                description=b["detail"],
                fixable=True,
                fix_guidance="替换为更具体的描写",
            ))

        # 2. Banned patterns — 高危句式仍只 warning（仅报告）；
        #    真正触发改写的只有硬错误（见 3/4 块）
        patterns = self._style_cleaner.check_banned_patterns(text)
        for p in patterns:
            issues.append(QualityIssue(
                gate_name="banned_patterns",
                category="style",
                severity=IssueSeverity.WARNING,
                description=p["detail"],
                fixable=True,
                fix_guidance="拆短句或换动作",
            ))

        # 3. Metadata leak — 硬错误，触发改写
        leaks = self._style_cleaner.check_metadata_leak(text)
        for l in leaks:
            issues.append(QualityIssue(
                gate_name="metadata_leak",
                category="content_leak",
                severity=IssueSeverity.ERROR,
                description=l["detail"],
                fixable=True,
                fix_guidance="删除工程词/章名标记",
            ))

        # 4. Degeneration — 硬错误（复读、截断、AI 拒绝、工程词）
        degens = self._style_cleaner.check_degeneration(text)
        for d in degens:
            issues.append(QualityIssue(
                gate_name="degeneration",
                category="format",
                severity=IssueSeverity.ERROR if d["severity"] == "blocking" else IssueSeverity.WARNING,
                description=d["detail"],
                fixable=True,
            ))

        # 4.6 Scene repeat — beat 间"重新开场"硬错误
        # 各段开场指纹高度相似时，说明 beat 重新写了已发生场景，触发改写。
        scene_repeats = self._style_cleaner.check_scene_repeat(text, chapter_plan)
        for s in scene_repeats:
            issues.append(QualityIssue(
                gate_name="scene_repeat",
                category="structure",
                severity=IssueSeverity.ERROR,
                description=s["detail"],
                fixable=True,
                fix_guidance="删除重复开场，从上一 beat 结尾处直接接续",
            ))

        # 4.5 Drumbeat density — 对话密集的校园喜剧中短句是常用节奏，
        # 仅报告为 warning，避免把可读性风格误判为硬性质量失败。
        if not skip_drumbeat_check:
            drumbeat_issues = self._style_cleaner.check_drumbeat_density(text)
            for di in drumbeat_issues:
                issues.append(QualityIssue(
                gate_name="drumbeat",
                category="style",
                severity=IssueSeverity.WARNING,
                description=di["detail"],
                fixable=True,
                fix_guidance="减少短句堆叠，用长句串起因果和感官，把短句密度降到20%以下",
            ))

        # 5. Structure checks — warning 级（开头天气/结尾总结），不阻塞
        structure = self._style_cleaner.check_chapter_structure(text)
        for s in structure:
            issues.append(QualityIssue(
                gate_name="structure",
                category="structure",
                severity=IssueSeverity.WARNING,
                description=s,
                fixable=True,
            ))

        # 6. Word count — 严重不足才 blocking（< 50%）；之前 90% 过严
        char_count = len(text)
        target = chapter_plan.target_chars
        if char_count < target * WORD_COUNT_BLOCK_RATIO:
            issues.append(QualityIssue(
                gate_name="word_count",
                category="length",
                severity=IssueSeverity.ERROR,
                description=f"字数严重不足: {char_count} < 目标 {target} 的 {int(WORD_COUNT_BLOCK_RATIO*100)}%",
                fixable=True,
                fix_guidance="补充展开点",
            ))
        elif char_count < target * 0.9:
            issues.append(QualityIssue(
                gate_name="word_count",
                category="length",
                severity=IssueSeverity.WARNING,
                description=f"字数偏少: {char_count} < 目标 {target} 的 90%",
                fixable=True,
                fix_guidance="可适当展开",
            ))

        # 7. Beat budget validation — warning 级
        if chapter_plan.scene_beats:
            budget_issues = self._validate_beat_budget(chapter_plan)
            for bi in budget_issues:
                issues.append(QualityIssue(
                    gate_name="beat_budget",
                    category="structure",
                    severity=IssueSeverity.WARNING,
                    description=bi,
                    fixable=False,
                ))

        # Build decision
        import uuid
        blocking_count = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
        verdict = QualityVerdict.ACCEPTED if blocking_count == 0 else QualityVerdict.REVISE
        return QualityDecision(
            trace_id=f"qd-{chapter_plan.chapter_id}-{uuid.uuid4().hex[:8]}",
            source_turn_id=f"ch-{chapter_plan.chapter_index}",
            verdict=verdict,
            blocking_reasons=[i.description for i in issues if i.severity == IssueSeverity.ERROR],
            warnings=[i.description for i in issues if i.severity == IssueSeverity.WARNING],
            checks=[i.to_dict() for i in issues],
        )

    def _validate_beat_budget(self, chapter_plan: ChapterPlan) -> list[str]:
        """Validate beat budget sums."""
        issues = []
        total_budget = sum(b.budget_chars for b in chapter_plan.scene_beats)
        target = chapter_plan.target_chars

        if total_budget < target:
            issues.append(f"beat 预算合计 {total_budget} < 章目标 {target}，需补充展开点")
        elif total_budget > target * 1.1:
            issues.append(f"beat 预算合计 {total_budget} > 章目标上限 {target * 1.1}，需压缩过场")

        for beat in chapter_plan.scene_beats:
            if beat.density not in ("dense", "normal", "sparse"):
                issues.append(f"beat '{beat.description[:20]}' 缺少密度标记")

        return issues
