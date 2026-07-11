"""NovelStyleCleaner — Style Cleaner for novel mode.

Deterministic checks + optional LLM style verification.
"""

from __future__ import annotations

import re
from typing import Any

# Banned words tier 1 (from oh-story)
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

# Banned words tier 2 (context-sensitive)
BANNED_WORDS_TIER2 = {
    "突然", "好像", "瞬间",
}

# Banned patterns (most toxic)
BANNED_PATTERNS = [
    r"不是.{1,20}，而是",             # "不是A，而是B"
    r"不是.{1,20}。\s*是.{1,20}[。！]", # "不是A。是B。" (句号版)
    r"没有.{1,20}。\s*没有.{1,20}。\s*只有", # 否定堆叠 "没有X。没有X。只有Y"
    r"第一遍.{1,20}第二遍.{1,20}第三遍",    # 数字递增
    r"(?m)^[^。\n]{1,8}[的着了]$",         # X的/Y的 short adjective fragment line
    r"他看见.{1,20}然后.{1,20}[。！]",       # 感知流水账 "他看见A。然后B。"
    r"，带着[一几分些]",              # "，带着一丝..."
    r"声音不大，却带着",             # "声音不大，却带着一种..."
    r"眼中闪过一丝",                 # "眼中闪过一丝..."
    r"嘴角勾起一抹",                 # "嘴角勾起一抹..."
    r"心中涌起一股",                 # "心中涌起一股..."
    r"他不知道的是",                 # 章末预告
    r"终于明白了",                   # 总结句式
    r"这才意识到",                   # 总结句式
    r"仿佛.{2,10}一般",             # "仿佛...一般"
]

# Banned ending patterns
BANNED_ENDING_PATTERNS = [
    r"他终于明白了",
    r"这一夜，注定",
    r"人生就是这样",
    r"他不知道的是，",
]

# Metadata leak pattern
METADATA_LEAK_PATTERN = re.compile(
    r"第[一二三四五六七八九十百千万两0-9]+章"
    r"|上一章|上章|前一章|本章|这一章"
    r"|前文|后文|伏笔|细纲|读者"
)

# AI refusal patterns
AI_REFUSAL_PATTERNS = [
    r"作为AI", r"作为语言模型", r"我无法续写",
    r"（此处省略）", r"此处省略", r"�",
    r"抱歉，我", r"对不起，我",
]

# Engineering words tier 1
TIER1_ENGINEERING_WORDS = ["细纲", "情节点", "卷纲", "功能标签", "字数预算"]

# Scene-repeat detection — beat 间"重新开场"兜底
# 取每段前 N 字作开场指纹，与前序段做 NGRAM-gram Jaccard 相似度比对。
SCENE_REPEAT_FINGERPRINT_CHARS = 120
SCENE_REPEAT_NGRAM = 3
SCENE_REPEAT_THRESHOLD = 0.5


class NovelStyleCleaner:
    """Style Cleaner for novel mode — deterministic checks + optional LLM."""

    def __init__(self, registry, model: str = "deepseek-v4-flash"):
        self._registry = registry
        self._model = model

    def check_banned_words(self, text: str) -> list[dict]:
        """Check for banned words."""
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
            if count >= 3:  # Only flag if frequent
                issues.append({
                    "type": "banned_word_tier2",
                    "severity": "warning",
                    "detail": f"二级禁用词 '{word}' 出现 {count} 次（高频）",
                    "word": word,
                })
        return issues

    def check_banned_patterns(self, text: str) -> list[dict]:
        """Check for banned patterns."""
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

    def check_metadata_leak(self, text: str) -> list[dict]:
        """Check for metadata leak in body text."""
        issues = []
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if i == 0 and line.startswith("#"):
                continue
            matches = METADATA_LEAK_PATTERN.findall(line)
            if matches:
                issues.append({
                    "type": "metadata_leak",
                    "severity": "blocking",
                    "detail": f"行{i+1}: 工程词泄露 {matches}",
                })
        return issues

    def check_degeneration(self, text: str) -> list[dict]:
        """Check for model degeneration."""
        issues = []

        # Repetition detection
        sentences = re.split(r'[。！？\n]', text)
        seen: dict[str, int] = {}
        for s in sentences:
            s = s.strip()
            if len(s) < 5:
                continue
            seen[s] = seen.get(s, 0) + 1
            if seen[s] >= 3:
                issues.append({
                    "type": "repetition",
                    "severity": "blocking",
                    "detail": f"复读: '{s}' 出现 {seen[s]} 次",
                })

        # Truncation detection (only for texts long enough to expect sentence terminators)
        if len(text) > 100:
            last_50 = text[-50:].strip()
            if last_50 and last_50[-1] not in "。！？」』）】":
                issues.append({
                    "type": "truncation",
                    "severity": "blocking",
                    "detail": "末尾可能被截断",
                })

        # AI refusal detection
        for pattern in AI_REFUSAL_PATTERNS:
            if re.search(pattern, text):
                issues.append({
                    "type": "ai_refusal",
                    "severity": "blocking",
                    "detail": f"AI拒绝语: {pattern}",
                })

        # Engineering word leak
        for word in TIER1_ENGINEERING_WORDS:
            if word in text:
                issues.append({
                    "type": "engineering_leak",
                    "severity": "blocking",
                    "detail": f"工程词泄露: '{word}'",
                })

        return issues

    def check_drumbeat_density(self, text: str) -> list[dict]:
        """Detect excessive short-sentence drumbeat patterns.

        When >25% of sentences are ≤12 chars, or there are >3 consecutive
        isolated short paragraphs, the chapter has AI drumbeat syndrome.
        """
        issues = []
        lines = text.split("\n")
        all_sentences = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Split each line into sentences
            parts = re.split(r'[。！？]', stripped)
            for p in parts:
                p = p.strip()
                if p:
                    all_sentences.append(p)

        if len(all_sentences) < 20:
            return issues

        short_count = sum(1 for s in all_sentences if len(s) <= 12)
        short_ratio = short_count / len(all_sentences)

        # Count consecutive isolated short paragraphs (≤15 chars, standalone)
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

    def check_chapter_structure(self, text: str) -> list[str]:
        """Check chapter structure."""
        issues = []
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        if not paragraphs:
            issues.append("正文为空")
            return issues

        # Opening check
        opening = text[:500]
        weather_words = ["天气", "阳光", "微风", "月色", "星空"]
        if any(w in opening[:100] for w in weather_words):
            issues.append("开头从天气/风景开始，缺少钩子")

        # Ending check
        ending = text[-300:]
        summary_patterns = ["终于明白", "这才意识到", "此刻，", "一切", "原来"]
        if any(p in ending for p in summary_patterns):
            issues.append("结尾是总结式收束，应改为动作/悬念收束")

        return issues

    @staticmethod
    def _ngrams(text: str, n: int = SCENE_REPEAT_NGRAM) -> set[str]:
        """取文本的字符级 n-gram 集合（去空白）。"""
        cleaned = re.sub(r"\s+", "", text)
        if len(cleaned) < n:
            return {cleaned} if cleaned else set()
        return {cleaned[i:i + n] for i in range(len(cleaned) - n + 1)}

    def check_scene_repeat(self, text: str, chapter_plan: Any = None) -> list[dict]:
        """检测 beat 间"重新开场"——各段开场指纹高度相似。

        按 chapter_plan.scene_beats 的 budget_chars 把正文切成 N 段（N=beat 数）；
        plan 缺失时退化为按 beat 数等分。对每段前 SCENE_REPEAT_FINGERPRINT_CHARS
        字作开场指纹，与前序各段做 NGRAM-gram Jaccard 相似度，超
        SCENE_REPEAT_THRESHOLD 报 blocking（会进入 quality pipeline 改写循环）。

        这层兜底光靠 prompt 接续指令拦不住的"重新开场"：beat2 用词不同但
        情节重复 beat1 的开场，逐字复读检测抓不到，n-gram 指纹能抓到。
        """
        if not text or not text.strip():
            return []
        # 确定分段数与各段长度
        beats = getattr(chapter_plan, "scene_beats", None) or ()
        seg_count = len(beats) if beats else 0
        if seg_count < 2:
            # 少于 2 段无法比对，跳过
            return []

        total_len = len(text)
        if total_len < 200:
            return []

        budgets = [int(getattr(b, "budget_chars", 0) or 0) for b in beats]
        if sum(budgets) <= 0:
            # 预算全为 0 → 等分
            seg_len = total_len // seg_count
            bounds = [(i * seg_len, (i + 1) * seg_len if i < seg_count - 1 else total_len)
                      for i in range(seg_count)]
        else:
            # 按 budget 比例切
            total_budget = sum(budgets)
            bounds = []
            cursor = 0
            for i, b in enumerate(budgets):
                start = cursor
                end = int(total_len * b / total_budget) + start
                if i == seg_count - 1:
                    end = total_len
                bounds.append((start, min(end, total_len)))
                cursor = end

        # 取各段开场指纹
        fingerprints = []
        for start, end in bounds:
            seg_text = text[start:end].strip()
            if not seg_text:
                fingerprints.append(None)
                continue
            head = seg_text[:SCENE_REPEAT_FINGERPRINT_CHARS]
            fingerprints.append(self._ngrams(head))

        # 与前序段比对
        issues = []
        for i in range(1, len(fingerprints)):
            fp_i = fingerprints[i]
            if not fp_i:
                continue
            for j in range(i):
                fp_j = fingerprints[j]
                if not fp_j:
                    continue
                union = fp_i | fp_j
                if not union:
                    continue
                inter = fp_i & fp_j
                sim = len(inter) / len(union)
                if sim >= SCENE_REPEAT_THRESHOLD:
                    issues.append({
                        "type": "scene_repeat",
                        "severity": "blocking",
                        "detail": f"第{i+1}段开场与第{j+1}段高度相似（Jaccard={sim:.2f}），疑似 beat 间重新开场",
                    })
                    break  # 该段命中一次即可，避免重复报
        return issues

    def normalize_punctuation(self, text: str) -> str:
        """Normalize punctuation."""
        text = text.replace("……", "。")
        text = text.replace("......", "。")
        text = text.replace("——", "，")
        text = text.replace("—", "，")
        text = text.replace("--", "，")
        text = re.sub(r"\n---\n", "\n", text)
        text = re.sub(r"\n---$", "\n", text)
        return text

    def full_check(self, text: str, chapter_plan: Any = None) -> dict:
        """Run all deterministic checks.

        Returns dict with:
        - issues: list of all issues found
        - blocking_count: number of blocking issues
        - normalized_text: text after punctuation normalization
        """
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

    # ── 鼓点段落提取 + LLM 片段改写 ──────────────────────────────────

    _DRUMBEAT_SNIPPET_PROMPT = """你是网文句式润色器。输入是一段文字片段（约100-300字），其中短句过多、节奏像节拍器。

你的任务：把碎片化的短句串成自然流动的叙述。规则：
1. 信息量、情节、对白、人物——都不改，只换句式。
2. 两个短句能连起来就连成一个长句。三个孤立短句可以拆成一个长句+一个短句收尾。
3. 禁止输出"不是A。是B。"、"没有X。只有Y。"等否定对比碎句。
4. 允许一段只有1-2句话，但要保证句子内部的因果、动作、感官是串起来的。
5. 输出只包含改写后的片段文字，不要标签、解释、标记。"""

    def find_drumbeat_regions(
        self, text: str,
        short_threshold: int = 12,
        density_threshold: float = 0.6,
        context_radius: int = 80,
    ) -> list[tuple[int, int, str]]:
        """Scan text paragraph by paragraph, find regions with high short-sentence density.

        Returns list of (start_char, end_char, snippet_text) where each snippet
        includes ~context_radius chars of surrounding context.
        """
        paragraphs = text.split("\n")
        # Build paragraph index: (line_num, text, char_start, char_end)
        para_info = []
        pos = 0
        for i, para in enumerate(paragraphs):
            start = pos
            end = pos + len(para)
            para_info.append((i, para, start, end))
            pos = end + 1  # +1 for the newline

        # Score each paragraph by short-sentence density
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
                # Expand to include context paragraphs
                ctx_start = p_start
                ctx_end = p_end
                # Include prev paragraph if exists
                if idx > 0:
                    ctx_start = para_info[idx - 1][2]
                # Include next paragraph if exists
                if idx < len(para_info) - 1:
                    ctx_end = para_info[idx + 1][3]
                # Further expand to meet ~context_radius
                snippet = text[ctx_start:ctx_end].strip()
                if len(snippet) < 40:
                    continue
                regions.append((ctx_start, ctx_end, snippet))

        # Merge overlapping regions
        if not regions:
            return []
        merged = [regions[0]]
        for r in regions[1:]:
            prev = merged[-1]
            if r[0] <= prev[1] + 50:  # overlap or very close
                # Extend prev
                merged[-1] = (prev[0], max(prev[1], r[1]),
                              text[prev[0]:max(prev[1], r[1])].strip())
            else:
                merged.append(r)
        return merged

    def rewrite_drumbeat_snippets(
        self,
        text: str,
        max_retries: int = 1,
    ) -> str:
        """Find drumbeat regions and rewrite each snippet via flash LLM."""
        regions = self.find_drumbeat_regions(text)
        if not regions:
            return text

        from .novel_llm_factory import NovelLLMFactory
        factory = NovelLLMFactory.get_instance()
        adapter = factory.get_adapter("style_cleaner")
        thinking = factory.get_thinking_config("style_cleaner")
        model = factory.get_model("style_cleaner")

        # Process regions from end to start to preserve positions
        result = text
        for start, end, snippet in reversed(regions):
            snippet_len = len(snippet)
            if snippet_len > 600:
                # Too large, skip
                continue

            user_prompt = (
                "=== 需要改写的片段 ===\n"
                f"{snippet}\n\n"
                "=== 输出 ===\n"
                "改写后的片段（只改句式，不改内容）："
            )

            for attempt in range(max_retries + 1):
                try:
                    out, _ = adapter.generate_text(
                        user_prompt,
                        max_tokens=max(500, int(snippet_len * 1.5)),
                        provider_role="novel_drumbeat_rewriter",
                        model=model,
                        extra_body=thinking,
                        system_prompt=self._DRUMBEAT_SNIPPET_PROMPT,
                    )
                except Exception:
                    continue
                if not out or not out.strip():
                    continue
                cleaned = out.strip()
                # Guard: rewritten must not be drastically different in length
                if len(cleaned) < snippet_len * 0.4 or len(cleaned) > snippet_len * 2.0:
                    continue
                # Splice back
                result = result[:start] + cleaned + result[end:]
                break

        return result

    # ── 定向改写：把质量门查出的问题反馈给 LLM 做去 AI 味改写 ──────────────

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
   - 禁止情绪词 → 用身体细节/动作替代（详见下方替换指引）。
   - 禁用句式（不是A而是B / 仿佛…一般 / 带着一丝…）→ 拆短句或换动作。
   - 工程词/章名泄露（本章/读者/细纲/伏笔 等）→ 直接删除或改为正文语境。
   - 重复复读句 → 删除多余副本，仅保留一次或改写其中一处。
   - 疑似截断 → 末尾补一个完整收束句，落在 。！？」』）】 之一。
3. 保持原有文风、视角、语气、信息密度，不得添加原文没有的新情节或新人物。
4. 输出只有改写后的完整正文，无标签、无 JSON、无解释、无前后说明。
5. 字数与原文相差不超过 ±10%。

=== 替换指引（禁止→替换为）===
- 心痛/心碎 → 手指掐进肉里自己不知道疼
- 悲伤/难过 → 把外套叠了三叠，放回衣柜最里面那一层
- 愤怒/气得发抖 → 手背上的青筋一根根暴起来
- 害怕/恐惧 → 手指碰到门把手又缩回来，碰了三次才握住
- 仿佛/犹如/如同 → 直接写具体画面，不用比喻词
- 缓缓/微微/轻轻/淡淡 → 用具体动作或身体反应替代
- 不禁/不由得 → 删除，直接写动作
- 不由自主 → 直接写动作
- 心中一动/心头一震 → 用身体反应替代
"""

    def rewrite_for_issues(
        self,
        text: str,
        issues: list[dict[str, Any]],
        max_retries: int = 1,
    ) -> str:
        """整章喂给改写 LLM，附问题清单，做定向去 AI 味改写。

        - 整章输入（按用户决策）：LLM 自行在原文中定位问题并修复。
        - 失败时返回原文（不抛异常，避免改写层阻断整章输出）。
        - 改写 LLM 用 deepseek-v4-flash + thinking=low，成本远低于整章 Writer 重写。
        """
        if not text or not text.strip():
            return text
        # 只把 blocking 类问题交给 LLM；warning 留给上层报告但不阻塞改写。
        blocking = [i for i in issues if i.get("severity") == "blocking"]
        if not blocking:
            return text

        # 构造紧凑的问题清单（带类型/词/句式）
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

        from .novel_llm_factory import NovelLLMFactory
        factory = NovelLLMFactory.get_instance()
        adapter = factory.get_adapter("style_cleaner")
        thinking = factory.get_thinking_config("style_cleaner")
        model = factory.get_model("style_cleaner")
        max_tokens = factory.get_max_tokens("style_cleaner")

        # 改写输出预算：按原文长度 + 余量估算，但封顶 8000 避免 flash 模型
        # 输出超长导致 finish_reason=length 截断（之前第7章 37531 字怪物就是
        # 改写器返回截断文本被当成功写回所致）。
        # 中文逐字≈1 token，加改写余量；最少 style_cleaner 配置值。
        max_tokens = max(max_tokens, min(len(text) + 800, 8000))

        for attempt in range(max_retries + 1):
            try:
                out, receipt = adapter.generate_text(
                    user_prompt,
                    max_tokens=max_tokens,
                    provider_role="novel_style_cleaner",
                    model=model,
                    extra_body=thinking,
                    system_prompt=self._REWRITE_SYSTEM_PROMPT,
                )
            except Exception:
                continue
            if not out or not out.strip():
                continue
            cleaned = out.strip()
            # 截断/异常检测：改写器若返回明显比原文膨胀或末尾未收束，视为坏输出。
            if self._looks_truncated_or_broken(cleaned, text):
                continue
            return cleaned
        # 改写 LLM 失败或多次截断：保留原文，由上层决定降级接受或拒收。
        return text

    @staticmethod
    def _looks_truncated_or_broken(out: str, orig: str) -> bool:
        """检测改写产物是否为截断/异常拼接。

        - 长度异常膨胀：> 原文 1.6 倍（改写只换表达，不应显著加长）
        - 末尾未收束：长度 > 100 且末字符不在 。！？」』）】… 之一
        - 大段重复：同一句（≥8 字）出现 ≥3 次
        """
        if not out:
            return True
        # 膨胀
        if len(out) > len(orig) * 1.6 + 200:
            return True
        # 末尾未收束
        if len(out) > 100:
            last = out[-1]
            if last not in "。！？」』）】":
                return True
        # 大段重复
        import re as _re
        from collections import Counter as _Counter
        sents = [s.strip() for s in _re.split(r'[。！？\n]', out) if len(s.strip()) >= 8]
        if sents:
            top = _Counter(sents).most_common(1)[0][1]
            if top >= 3:
                return True
        return False

    # ---- Plan text cleaning (strip drumbeat from architect plans) ----

    @staticmethod
    def clean_drumbeat_text(text):
        """Remove drumbeat sentence patterns from a text snippet.

        Converts:
            "不是X。是Y。" → "不是X，而是Y。"
            "不是X。\n是Y。" → "不是X，而是Y。"
            "不是X。\n\n是Y" → "不是X，而是Y"
        """
        if not text:
            return text
        if not isinstance(text, str):
            return text
        t = re.sub(r'不是([^。；]{1,30})。[\n\s]*是([^。；]{1,30}[。！？\n]?)',
                   r'不是\1，而是\2', text)
        return t

    @staticmethod
    def clean_plan(plan):
        """Clean drumbeat from a ChapterPlan. Returns a new ChapterPlan."""
        from ..contracts.novel_chapter import (
            ChapterPlan, ContentSummary, PlotArrangement,
            CharacterAppearance, BeatDetail, EndingDesign,
        )

        ct = NovelStyleCleaner.clean_drumbeat_text

        cs = plan.content_summary
        new_cs = ContentSummary(
            cause=ct(cs.cause),
            development=ct(cs.development),
            turning_point=ct(cs.turning_point),
            climax=ct(cs.climax),
            ending=ct(cs.ending),
        )

        pa = plan.plot_arrangement
        new_pa = PlotArrangement(
            main_line=ct(pa.main_line),
            sub_line=ct(pa.sub_line),
            event_line=ct(pa.event_line),
            emotion_line=ct(pa.emotion_line),
            logic_line=ct(pa.logic_line),
        )

        ca = plan.character_appearance
        new_ca = CharacterAppearance(
            appearance_order=ca.appearance_order,
            relationship_changes=tuple(ct(r) for r in ca.relationship_changes),
            information_gap=ct(ca.information_gap),
        )

        new_beats = tuple(
            BeatDetail(
                beat_id=b.beat_id,
                description=ct(b.description),
                function_tag=b.function_tag,
                density=b.density,
                budget_chars=b.budget_chars,
            )
            for b in plan.scene_beats
        )

        ed = plan.ending_design
        new_ed = EndingDesign(
            closing_state=ct(ed.closing_state),
            open_questions=tuple(ct(q) for q in ed.open_questions),
            next_chapter_push=ct(ed.next_chapter_push),
            hook_type=ct(ed.hook_type),
            hook_detail=ct(ed.hook_detail),
            hook_strength=ed.hook_strength,
        )

        return ChapterPlan(
            schema_id=plan.schema_id,
            schema_version=plan.schema_version,
            chapter_id=plan.chapter_id,
            project_id=plan.project_id,
            volume_id=plan.volume_id,
            chapter_index=plan.chapter_index,
            title=plan.title,
            target_chars=plan.target_chars,
            chapter_position=plan.chapter_position,
            target_emotion=plan.target_emotion,
            opening_hook=ct(plan.opening_hook),
            main_payoff=ct(plan.main_payoff),
            content_summary=new_cs,
            plot_arrangement=new_pa,
            character_appearance=new_ca,
            scene_beats=new_beats,
            ending_design=new_ed,
            cost_and_reward=ct(plan.cost_and_reward),
        )
