"""NovelStyleCleaner — DEPRECATED since 2026-07-25.

Legacy style/design/drumbeat/rewrite tools. OFF-LINE ONLY.
For write-path HARD audit, use novel_mechanical_gate.NovelMechanicalGate.

Retained for:
- audit-design (CLI offline tool)
- audit-style (CLI offline tool)
- Historical compatibility
"""

from __future__ import annotations

import re
import uuid
import warnings
from typing import Any

from ..contracts.novel_pi_role_protocol import NovelPiRoleTask
from .novel_role_context import get_novel_role_context
from .novel_role_runtime import get_novel_role_runtime
from .novel_mechanical_gate import NovelMechanicalGate, METADATA_LEAK_PATTERN, AI_REFUSAL_PATTERNS, TIER1_ENGINEERING_WORDS, SCENE_REPEAT_FINGERPRINT_CHARS, SCENE_REPEAT_NGRAM, SCENE_REPEAT_THRESHOLD

# ── 保留但冻结：AI 味检测常量（不进入热路径）──

BANNED_WORDS_TIER1 = {
    # 情态类
    "仿佛", "犹如", "宛若", "如同", "一丝", "一抹", "些许", "几分", "隐约",
    # 动作类
    "深吸一口气", "缓缓", "不禁", "微微", "轻轻", "淡淡",
    # 表情类
    "眼中闪过", "嘴角勾起", "眉头微皱", "眉眼低垂", "瞳孔微缩",
    # 心理类
    "心中一动", "心头一震", "心下了然", "心中暗道", "心底泛起", "不由得",
    # 判断类
    "不容置疑", "不容置喙", "不易察觉", "显而易见", "毫无疑问", "不可否认",
    # 形容类
    "坚定", "闪烁着光芒", "狡黠", "深邃", "凛冽", "冰冷",
    # 过渡类
    "不由自主", "情不自禁", "自然而然",
}

BANNED_WORDS_TIER2 = {
    "突然", "好像", "瞬间",
}

BANNED_PATTERNS = [
    r"不是.{1,20}，而是",
    r"不是.{1,20}。\s*是.{1,20}[。！]",
    r"没有.{1,20}。\s*没有.{1,20}。\s*只有",
    r"第一遍.{1,20}第二遍.{1,20}第三遍",
    r"(?m)^[^。\n]{1,8}[的着了]$",
    r"他看见.{1,20}然后.{1,20}[。！]",
    r"，带着[一几分些]",
    r"声音不大，却带着",
    r"眼中闪过一丝",
    r"嘴角勾起一抹",
    r"心中涌起一股",
    r"他不知道的是",
    r"终于明白了",
    r"这才意识到",
    r"仿佛.{2,10}一般",
]

BANNED_ENDING_PATTERNS = [
    r"他终于明白了",
    r"这一夜，注定",
    r"人生就是这样",
    r"他不知道的是，",
]


class NovelStyleCleaner(NovelMechanicalGate):
    """Deprecated — offline analysis tools only.

    Inherits all mechanical gate methods. Adds legacy AI-voice checks
    and DESIGN/STYLE audit tools retained for CLI offline use.
    """

    # STYLE-specific constant only needed in deprecated class
    _PATCH_MAX_BEFORE_CHARS_STYLE = 120

    def __init__(self, registry, model: str = "deepseek-v4-pro"):
        warnings.warn(
            "NovelStyleCleaner is deprecated. Use NovelMechanicalGate for "
            "the write path. This class is retained for audit-design / "
            "audit-style CLI tools only.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Skip NovelMechanicalGate.__init__ signature differences by init'ing here
        self._registry = registry
        self._model = model

    # ── 保留但冻结：AI 味检测（不进入热路径）──

    def check_banned_words(self, text: str) -> list[dict]:
        issues = []
        for word in BANNED_WORDS_TIER1:
            count = text.count(word)
            if count > 0:
                issues.append({
                    "type": "banned_word_tier1",
                    "severity": "blocking",
                    "detail": f"一级禁用词 '{word}' 出现 {count} 次",
                    "word": word,
                })
        for word in BANNED_WORDS_TIER2:
            count = text.count(word)
            if count >= 3:
                issues.append({
                    "type": "banned_word_tier2",
                    "severity": "warning",
                    "detail": f"二级禁用词 '{word}' 出现 {count} 次（高频）",
                    "word": word,
                })
        return issues

    def check_banned_patterns(self, text: str) -> list[dict]:
        issues = []
        for pattern in BANNED_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                issues.append({
                    "type": "banned_pattern",
                    "severity": "blocking",
                    "detail": f"禁用句式: {pattern}，匹配: {matches[:3]}",
                })
        return issues

    def check_drumbeat_density(self, text: str) -> list[dict]:
        issues = []
        lines = text.split("\n")
        all_sentences = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            parts = re.split(r'[。！？]', stripped)
            for p in parts:
                p = p.strip()
                if p:
                    all_sentences.append(p)

        if len(all_sentences) < 20:
            return issues

        short_count = sum(1 for s in all_sentences if len(s) <= 12)
        short_ratio = short_count / len(all_sentences)

        consecutive_streak = 0
        max_streak = 0
        for line in lines:
            stripped = line.strip()
            if stripped and len(stripped) <= 15:
                consecutive_streak += 1
                max_streak = max(max_streak, consecutive_streak)
            else:
                consecutive_streak = 0

        if short_ratio > 0.40:
            issues.append({
                "type": "drumbeat_density",
                "severity": "blocking",
                "detail": f"短句密度过高: {short_count}/{len(all_sentences)} 句 ≤12字 (比例 {short_ratio:.0%})，AI鼓点综合征",
            })
        if max_streak >= 3:
            issues.append({
                "type": "drumbeat_consecutive",
                "severity": "blocking",
                "detail": f"连续 {max_streak} 个短句独立成段，禁止节拍器式写法",
            })

        return issues

    # ── 保留但冻结：综合检查（仅测试使用）──

    def full_check(self, text: str, chapter_plan: Any = None) -> dict:
        all_issues = []
        all_issues.extend(self.check_banned_words(text))
        all_issues.extend(self.check_banned_patterns(text))
        all_issues.extend(self.check_metadata_leak(text))
        all_issues.extend(self.check_degeneration(text))
        all_issues.extend(self.check_drumbeat_density(text))
        if chapter_plan is not None:
            all_issues.extend(self.check_scene_repeat(text, chapter_plan))

        structure_issues = self.check_chapter_structure(text)
        for si in structure_issues:
            all_issues.append({
                "type": "structure",
                "severity": "warning",
                "detail": si,
            })

        blocking_count = sum(1 for i in all_issues if i.get("severity") == "blocking")
        normalized = self.normalize_punctuation(text)

        return {
            "issues": all_issues,
            "blocking_count": blocking_count,
            "normalized_text": normalized,
        }

    # ── 保留但冻结：鼓点段落提取 + LLM 片段改写 ──────────────────

    _DRUMBEAT_SNIPPET_PROMPT = """你是网文句式润色器。输入是一段文字片段（约100-300字），其中短句过多、节奏像节拍器。

你的任务：把碎片化的短句串成自然流动的叙述。规则：
1. 信息量、情节、对白、人物——都不改，只换句式。
2. 两个短句能连起来就连成一个长句。三个孤立短句可以拆成一个长句+一个短句收尾。
3. 禁止输出"不是A。是B。"、"没有X。只有Y。"等否定对比碎句。
4. 允许一段只有1-2句话，但要保证句子内部的因果、动作、感官是串起来的。
5. 视角红线：保持主角陈默的第三人称有限视角。不改视角、不引入上帝视角。
6. 输出只包含改写后的片段文字，不要标签、解释、标记。"""

    def find_drumbeat_regions(
        self, text: str,
        short_threshold: int = 12,
        density_threshold: float = 0.6,
        context_radius: int = 80,
    ) -> list[tuple[int, int, str]]:
        paragraphs = text.split("\n")
        para_info = []
        pos = 0
        for i, para in enumerate(paragraphs):
            start = pos
            end = pos + len(para)
            para_info.append((i, para, start, end))
            pos = end + 1

        regions = []
        for idx, para, p_start, p_end in para_info:
            stripped = para.strip()
            if not stripped or len(stripped) < 20:
                continue
            sentences = [s.strip() for s in re.split(r'[。！？]', stripped) if s.strip()]
            if len(sentences) < 3:
                continue
            short_count = sum(1 for s in sentences if len(s) <= short_threshold)
            density = short_count / len(sentences) if sentences else 0
            if density >= density_threshold:
                ctx_start = p_start
                ctx_end = p_end
                if idx > 0:
                    ctx_start = para_info[idx - 1][2]
                if idx < len(para_info) - 1:
                    ctx_end = para_info[idx + 1][3]
                snippet = text[ctx_start:ctx_end].strip()
                if len(snippet) < 40:
                    continue
                regions.append((ctx_start, ctx_end, snippet))

        if not regions:
            return []
        merged = [regions[0]]
        for r in regions[1:]:
            prev = merged[-1]
            if r[0] <= prev[1] + 50:
                merged[-1] = (prev[0], max(prev[1], r[1]),
                              text[prev[0]:max(prev[1], r[1])].strip())
            else:
                merged.append(r)
        return merged

    def rewrite_drumbeat_snippets(self, text: str, max_retries: int = 1) -> str:
        regions = self.find_drumbeat_regions(text)
        if not regions:
            return text

        result = text
        for start, end, snippet in reversed(regions):
            snippet_len = len(snippet)
            if snippet_len > 600:
                continue

            user_prompt = (
                "=== 需要改写的片段 ===\n"
                f"{snippet}\n\n"
                "=== 输出 ===\n"
                "改写后的片段（只改句式，不改内容）："
            )

            for _attempt in range(max_retries + 1):
                try:
                    out = self._run_style_role(
                        user_prompt,
                        system_prompt=self._DRUMBEAT_SNIPPET_PROMPT,
                        phase="drumbeat_snippet",
                        max_tokens=max(500, int(snippet_len * 1.5)),
                    )
                except Exception:
                    continue
                if not out or not out.strip():
                    continue
                cleaned = out.strip()
                if len(cleaned) < snippet_len * 0.4 or len(cleaned) > snippet_len * 2.0:
                    continue
                result = result[:start] + cleaned + result[end:]
                break

        return result

    # ── 保留但冻结：整章 AI 味改写 ─────────────────────────────────

    _REWRITE_SYSTEM_PROMPT = """=== STABLE REWRITE CONTRACT ===
你是网文去 AI 味改写器。输入是章节正文 + 检查出的问题清单。
你的职责：只针对问题清单中点出的表达做最小改动修复，其余文字一字不改。

=== 目标风格：自然流动的口语化叙事 ===
改写时必须保持以下风格特征：
- 长短句交替，自然呼吸，不要全短句堆叠（清单感）
- 段落参差不齐，有长有短，禁止连续3个以上单句独段
- 段落之间有过渡逻辑，不要硬切
- 内心独白融入叙述流，不要每段单独成段
- 大白话，不用华丽辞藻
- 物件具体化，身体细节替代情绪词

参照风格：
「林舟忽然觉得连一个病毒都那么努力，无视风险就为了薅他账户里的0.38元，他有什么资格沮丧呢？"这笔钱给你赚吧，其实你也不容易。"林舟选择点开了软件，想看看有没有其他卸载的方法。」
——长句叙述→对话融入→动作推进，自然流动，不是碎片短句堆叠。

=== 硬规则 ===
1. 不改情节、人物、对话内容、信息量、字数级、段落顺序，只换表达形式。
2. 问题清单列出的禁用词/句式必须替换为更具体、更身体的描写。
3. 视角红线（不可违背）：严格保持主角陈默的第三人称有限视角。
4. 保持原有文风、语气、信息密度，不得添加原文没有的新情节或新人物。
5. 输出只有改写后的完整正文，无标签、无 JSON、无解释、无前后说明。
6. 字数与原文相差不超过 ±10%。

=== 替换指引（禁止→替换为）===
- 心痛/心碎 → 手指掐进肉里自己不知道疼
- 仿佛/犹如/如同 → 直接写具体画面，不用比喻词
- 缓缓/微微/轻轻/淡淡 → 用具体动作或身体反应替代
- 不禁/不由得 → 删除，直接写动作
- 心中一动/心头一震 → 用身体反应替代
"""

    def rewrite_for_issues(
        self, text: str, issues: list[dict[str, Any]], max_retries: int = 1,
    ) -> str:
        if not text or not text.strip():
            return text
        blocking = [i for i in issues if i.get("severity") == "blocking"]
        if not blocking:
            return text

        report_lines = []
        for i in blocking:
            t = i.get("type", "")
            d = i.get("detail", "")
            report_lines.append(f"- [{t}] {d}")
        issues_block = "\n".join(report_lines)

        user_prompt = (
            "=== 原文 ===\n"
            f"{text}\n\n"
            "=== 检查出的问题清单（只修这些问题，其它不动）===\n"
            f"{issues_block}\n\n"
            "=== 输出 ===\n"
            "只输出改写后的完整正文，不要任何解释或标记。"
        )

        max_tokens = max(2000, min(len(text) + 800, 8000))

        for _attempt in range(max_retries + 1):
            try:
                out = self._run_style_role(
                    user_prompt, system_prompt=self._REWRITE_SYSTEM_PROMPT,
                    phase="issue_rewrite", max_tokens=max_tokens,
                )
            except Exception:
                continue
            if not out or not out.strip():
                continue
            cleaned = out.strip()
            if self._looks_truncated_or_broken(cleaned, text):
                continue
            return cleaned
        return text

    # ── 保留但冻结：STYLE 审计回路 ────────────────────────────────

    def _run_style_loop(self, text: str, orig_len: int, *,
                        plot_beats: tuple[str, ...] = (),
                        hard_passed_text: str = "") -> str:
        baseline = hard_passed_text or text
        audit = self._run_audit(text, audit_mode="STYLE", plot_beats=plot_beats)
        if not audit or not audit.get("issues"):
            return text

        patches_json = self._run_patch_gen(text, audit.get("issues", []), plot_beats=plot_beats)
        if not patches_json:
            return text

        patched, _ = self._apply_patches(text, patches_json.get("patches", []),
                                          budget=orig_len, budget_ratio=self._PATCH_BUDGET_STYLE)

        verdict_json = self._run_verify(text, audit, patched,
                                         patches_json.get("patches", []),
                                         plot_beats=plot_beats)
        verdict = verdict_json.get("verdict", "REJECT") if verdict_json else "REJECT"
        if verdict == "REJECT":
            return baseline
        return patched if patched else text

    # ═══════════════════════════════════════════════════════════
    # 旁路 CLI 工具：DESIGN / STYLE 审计
    # ═══════════════════════════════════════════════════════════

    _DESIGN_AUDIT_SYSTEM_PROMPT = """你是叙事设计过载审计器。不修改正文，只诊断。

检查 D1-D5，每个最多标记 1 处。不设硬性上限但总数不超过 8。

D1_ACTION_OVERLOAD
单个动作是否同时承担 3+ 个功能（解围/暧昧/象征/绑定/视觉特写）。
命中的动作：列出每个功能的原文证据。

D2_SCENE_FUNCTION_OVERLOAD
单个场景是否同时完成 4+ 个独立功能（秘密暴露/人设展示/救场/关系绑定/道具交付/主线建立）。
命中的场景：列出每个功能。

D3_SUPPORTING_CAST_FUNCTIONAL
配角是否每次出场都贡献精准有效台词。
检测：王磊是否每次都负责笑点、顾远是否每次都冷静补刀。
允许配角吃包子不推动剧情、没接上话、理解错重点。

D4_PROP_OVERLOADED
单一物件（钥匙、信纸、意见箱）是否同时承担 3+ 个功能。
检测物件是否同时作为：情节工具 + 人物象征 + 关系象征 + 章节结尾 + 主线入口。

D5_NARRATIVE_VOICE_SHIFT
检测同一场景是否在这些叙述模式间切换：
人物吐槽 → 中性镜头 → 偶像剧特写 → 作者心理分析 → 章末总结。

输出 JSON：
{"verdict":"PASS|WARN|REGENERATE_SCENE|AUTHOR_DECISION",
 "issues":[{"id":"","category":"D1_ACTION_OVERLOAD|D2_SCENE_FUNCTION_OVERLOAD|D3_SUPPORTING_CAST_FUNCTIONAL|D4_PROP_OVERLOADED|D5_NARRATIVE_VOICE_SHIFT",
            "quote":"原文证据","diagnosis":"为什么是设计过载","severity":"warn|regenerate|decision"}],
 "summary":"PASS=无过载|WARN=有过载但不阻塞|REGENERATE_SCENE=场景需局部重写|AUTHOR_DECISION=结构问题需人类裁决"}"""

    def _run_design_audit(self, text: str, *,
                           plot_beats: tuple[str, ...] = ()) -> dict[str, Any] | None:
        """DESIGN 审计：检查叙事设计过载 (D1-D5)。不自动补丁，只诊断。"""
        prompt = self._build_constraint_prompt(plot_beats=plot_beats)
        user_prompt = prompt + f"\n\n正文：\n{text}"
        return self._call_llm_json(
            self._DESIGN_AUDIT_SYSTEM_PROMPT, user_prompt,
            role="design_audit", max_tokens=4000,
        )

    def _run_style_audit(self, text: str, *,
                          plot_beats: tuple[str, ...] = ()) -> dict[str, Any] | None:
        """STYLE audit — offline only. Wraps inherited _run_audit."""
        return self._run_audit(text, audit_mode="STYLE", plot_beats=plot_beats)

    # ═══════════════════════════════════════════════════════════
    # Pi Role 调用（旧改写方法依赖）
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _run_style_role(prompt: str, *, system_prompt: str, phase: str,
                        max_tokens: int) -> str:
        context = get_novel_role_context()
        result = get_novel_role_runtime().run(
            NovelPiRoleTask(
                role="style_cleaner",
                project_id=context.project_id,
                chapter_index=context.chapter_index,
                revision=context.revision,
                phase=phase,
                session_key=f"task:{uuid.uuid4().hex}",
                task_contract=system_prompt,
                input_payload={"prompt": prompt, "response_format": "rewritten_prose"},
                max_tokens=max_tokens,
            ),
            context=context,
        )
        return result.text
