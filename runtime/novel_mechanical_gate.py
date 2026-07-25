"""NovelMechanicalGate — Mechanical correctness gate for novel mode.

Deterministic checks + LLM HARD audit + exact patch application.
This is the ONLY module allowed to modify chapter text in the write path.

STYLE, DESIGN, and AI-voice checks moved to novel_style_cleaner.py (offline tools only).
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from ..contracts.novel_pi_role_protocol import NovelPiRoleTask
from .novel_role_context import get_novel_role_context
from .novel_role_runtime import get_novel_role_runtime

# ── 确定性检查常量 ──

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
SCENE_REPEAT_FINGERPRINT_CHARS = 120
SCENE_REPEAT_NGRAM = 3
SCENE_REPEAT_THRESHOLD = 0.5


class NovelMechanicalGate:
    """Mechanical correctness gate — HARD audit + exact patch application.

    Only checks deterministically wrong issues: time, presence, objects,
    knowledge boundaries, rule violations, forgotten tasks, repeats, grammar.
    Can auto-patch. Never makes creative judgments.
    """

    # ═══════════════════════════════════════════════════════════
    # 固定约束
    # ═══════════════════════════════════════════════════════════

    _FOCAL_CHARACTER = "陈默"
    _POV_MODE = "第三人称限知，正文只能直接进入陈默的感知、判断和回忆；其他人物心理只能通过可见行为推测"
    _DEFAULT_PLOT_BEATS: tuple[str, ...] = ()
    _PATCH_BUDGET = 0.08
    _PATCH_BUDGET_STYLE = 0.05  # 保留供旧类使用
    _PATCH_MAX_BEFORE_CHARS = 160
    _PATCH_MAX_BEFORE_CHARS_STYLE = 120
    _PATCH_MAX_AFTER_CHARS = 160
    _PATCH_AFTER_TO_BEFORE_RATIO = 1.35

    def __init__(self, registry, model: str = "deepseek-v4-pro"):
        self._registry = registry
        self._model = model

    # ── 确定性检测 ──────────────────────────────────────────────

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

        # Truncation detection
        if len(text) > 100:
            last_50 = text[-50:].strip()
            if last_50 and last_50[-1] not in "。！？’”』）】":
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

    def check_chapter_structure(self, text: str) -> list[str]:
        """Check chapter structure."""
        issues = []
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        if not paragraphs:
            issues.append("正文为空")
            return issues

        opening = text[:500]
        weather_words = ["天气", "阳光", "微风", "月色", "星空"]
        if any(w in opening[:100] for w in weather_words):
            issues.append("开头从天气/风景开始，缺少钩子")

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
        if not text or not text.strip():
            return []
        beats = getattr(chapter_plan, "scene_beats", None) or ()
        seg_count = len(beats) if beats else 0
        if seg_count < 2:
            return []

        total_len = len(text)
        if total_len < 200:
            return []

        budgets = [int(getattr(b, "budget_chars", 0) or 0) for b in beats]
        if sum(budgets) <= 0:
            seg_len = total_len // seg_count
            bounds = [(i * seg_len, (i + 1) * seg_len if i < seg_count - 1 else total_len)
                      for i in range(seg_count)]
        else:
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

        fingerprints = []
        for start, end in bounds:
            seg_text = text[start:end].strip()
            if not seg_text:
                fingerprints.append(None)
                continue
            head = seg_text[:SCENE_REPEAT_FINGERPRINT_CHARS]
            fingerprints.append(self._ngrams(head))

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
                    break
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

    # ── 确定性预处理 ──────────────────────────────────────────────

    @staticmethod
    def _strip_boilerplate(text: str) -> str:
        """Remove COT blocks, model preambles, and markdown wrappers before audit."""
        text = re.sub(r'<!--\s*COT-PersonalityReshaping.*?-->', '', text, flags=re.DOTALL)
        text = re.sub(r'```json\s*\n\s*\{\s*"COT-PersonalityReshaping".*?\}\s*\n\s*```', '', text, flags=re.DOTALL)
        text = re.sub(r'\{\{setvar::COT-PersonalityReshaping::.*?\}\}', '', text, flags=re.DOTALL)
        text = re.sub(r'###\s+COT-PersonalityReshaping.*?(?=\*\*\*\s*\n|###\s*正文)', '', text, flags=re.DOTALL)
        text = re.sub(r'<PersonalityReshaping>.*?</PersonalityReshaping>', '', text, flags=re.DOTALL)
        text = re.sub(r'<内部状态表>.*?</内部状态表>', '', text, flags=re.DOTALL)
        text = re.sub(r'\A.*?\n\*{3,4}\s*\n', '', text, count=1, flags=re.DOTALL)
        text = re.sub(r'^(根据设定与任务约束.*?正文内容[：:]?\s*)$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^(【COT-PersonalityReshaping】[\s\S]*?)(?=\*\*\*\s*\n)', '', text, flags=re.DOTALL)
        text = re.sub(r'\n\*\*\*\s*\n', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip() + "\n"

    @staticmethod
    def _looks_truncated_or_broken(out: str, orig: str) -> bool:
        if not out:
            return True
        if len(out) > len(orig) * 1.6 + 200:
            return True
        if len(out) > 100:
            last = out[-1]
            if last not in "。！？’”』）】":
                return True
        from collections import Counter
        sents = [s.strip() for s in re.split(r'[。！？\n]', out) if len(s.strip()) >= 8]
        if sents:
            top = Counter(sents).most_common(1)[0][1]
            if top >= 3:
                return True
        return False

    # ── LLM 调用基础设施 ──────────────────────────────────────────

    def _call_llm_json(self, system_prompt: str, user_prompt: str, *,
                        role: str = "style_cleaner", max_tokens: int = 8000,
                        temperature: float = 0.0) -> dict[str, Any] | None:
        from .novel_llm_factory import NovelLLMFactory
        factory = NovelLLMFactory.get_instance()
        adapter = factory.get_adapter(role)
        if not adapter or not adapter.is_available:
            return None
        try:
            thinking_config = factory.get_thinking_config(role)
            extra_body = None
            if thinking_config.get("thinking", {}).get("type") != "disabled":
                extra_body = thinking_config
            out_text, _ = adapter.generate_text(
                prompt=user_prompt, system_prompt=system_prompt,
                max_tokens=max_tokens, model=factory.get_model(role),
                extra_body=extra_body,
            )
            content = out_text.strip()
            if not content:
                return None
            if content.startswith("```"):
                parts = content.split("```", 2)
                if len(parts) >= 2:
                    content = parts[1]
                    if content.startswith("json"):
                        content = content[4:]
                content = content.strip()
            return json.loads(content)
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════
    # 审计器 V2：支持 HARD/STYLE 双模式，事实账本驱动
    # ═══════════════════════════════════════════════════════════

    _AUDIT_SYSTEM_PROMPT = """你是小说证据审计器。不润色、不续写、不重写。

【运行模式】AUDIT_MODE={{AUDIT_MODE}}

HARD：只查时间、位置、人数、物体、规则、人物知识、因果、视角、人物边界、场景衔接。硬问题不设数量上限。
STYLE：只查作者总结、人物标签、段子密度、过强反应、模板化心理说明、过度设计句。最多10个。

【第一步：建立事实账本】逐场景提取：时间日期、位置、在场人物及进出、关键物体归属状态、已建立的制度规则、每人已知信息、每人直接目标、场景新增信息/选择/后果。不确定的标unknown。

【HARD检查项】
H1_TIME 时间/铃声/日期/课程/今天明天周末互不矛盾
H2_PRESENCE 人数在场状态前后一致
H3_SPACE 位置/方向/遮挡/受力成立
H4_OBJECT 纸张/钥匙/衣服等物体位置数量归属状态连续
H5_KNOWLEDGE 人物不知道没有途径获知的信息
H6_RULE 不依赖未建立的制度/班规/权限
H7_CAUSALITY 行为有当时成立的直接理由
H8_POV 限知视角不把观察猜测写成确定事实，不进入他人内心
H9_BOUNDARY 不扣押私人信息/胁迫/替人决定并当作魅力行为
H10_SCENE_VALUE 后一场景不重复已有信息，新增选择/后果/信息/关系变化

【STYLE检查项】
S1_SUMMARY 动作已表达后不应再有阅读理解总结
S2_LABEL 不用人物卡标签代替现场表现
S3_MEME_DENSITY 相邻段落网络梗/金句不连续出现
S4_MAX_REACTION 不过度用猛地/瞬间/死死/炸开/极其
S5_OVERDESIGNED 句子不为对称/象征/宣传存在
S6_EXPLANATION 刚发生动作旁白不立即解释原因
S7_GENERIC_ENDING 章末不用概括句

【证据】每个问题必须有原文准确短句、被违反事实、为何可确定。HARD不设数量上限。
【修复权限】只提操作类型：DELETE/REPLACE_LOCAL/ADJUST_SETUP/AUTHOR_DECISION。ADJUST_SETUP最多两句。场景无推进且需新增剧情→AUTHOR_DECISION。

只输出JSON：{"ledger":{"scenes":[{"scene_id":"S1","time":"","location":"","present_characters":[],"entries_and_exits":[],"objects":[{"name":"","owner":"","location":"","state":""}],"established_rules":[],"knowledge":[{"character":"","knows":[],"does_not_know":[]}],"scene_new_value":[],"visible_consequence":[]}]},"issues":[{"id":"","category":"","severity":"hard|medium|soft","confidence":0.0,"quote":"","related_quote":"","violated_fact":"","diagnosis":"","repair_operation":"DELETE|REPLACE_LOCAL|ADJUST_SETUP|AUTHOR_DECISION","repair_constraint":"","forbidden_change":""}]}"""

    # ═══════════════════════════════════════════════════════════
    # 精确补丁生成器 V2
    # ═══════════════════════════════════════════════════════════

    _PATCH_SYSTEM_PROMPT = """你是小说精确补丁生成器。不得输出完整正文，只输出能被程序应用的文本补丁。

【输入原则】每个补丁的before必须逐字出现在原文且只出现一次。找不到唯一文本→UNPATCHABLE。

【可自动处理】DELETE/REPLACE_LOCAL/ADJUST_SETUP(≤两句)。禁止处理AUTHOR_DECISION/需新增剧情/需改变人物动机/需重写场景/需新增人物秘密回忆伏笔。

【最小修改】1.每补丁只解一个issue 2.优先删不优先写 3.能改一词不改整句 4.能改一句不改整段 5.不改审计未覆盖内容 6.不统一语气 7.不新增比喻梗描写总结 8.不把模糊判断变确定事实 9.不以扣押胁迫修复关系 10.不用正好恰好原来临时解释制度漏洞。

【预算】普通补丁before≤160字after≤160字且after≤1.35×before。ADJUST_SETUP最多两句放规则首次相关位置。整章修改≤8%。超预算只处理hard其余deferred。

【补丁类型】replace/delete/insert_before/insert_after。

只输出JSON：{"patches":[{"patch_id":"P001","issue_id":"","operation":"replace|delete|insert_before|insert_after","before":"","after":"","context_before":"","context_after":"","expected_occurrences":1,"reason":""}],"unpatchable":[{"issue_id":"","status":"UNPATCHABLE|AUTHOR_DECISION","reason":"","required_decision":""}],"deferred":[],"estimated_changed_ratio":0.0}

禁止输出revised_text。禁止输出完整章节。禁止修改未被issue引用的段落。"""

    # ═══════════════════════════════════════════════════════════
    # 验收器 V2
    # ═══════════════════════════════════════════════════════════

    _VERIFY_SYSTEM_PROMPT = """你是小说修复的对抗性验收器。不修改正文，主动寻找未解决问题和新增回归。

【第一步】独立阅读修复稿，重新建立事实账本：时间线/位置/每场在场人物/进出/关键物体归属状态/已建立制度/人物已知信息/每场新增信息选择后果。不复制原审计，依据修复稿重新提取。

【第二步：逐问题验收】RESOLVED/UNRESOLVED/PARTIAL/REGRESSED。不根据文字是否流畅判定解决。

【第三步：新增回归检查】新时间矛盾/新人数在场矛盾/新物体状态错误/人物知道不该知道的信息/新制度无铺垫/焦点视角越界/人物边界受损/为解释修复新增总结/未标记段落被大幅改写/剧情节点丢失。

【硬性通过】所有hard→RESOLVED；无新增hard；无新增人物设定秘密剧情事件；补丁修改≤8%；补丁只改对应issue附近文本；人物私人物品和行动权未被无理由剥夺；视角稳定。任一未解决或新增hard→REJECT。

只输出JSON：{"verdict":"PASS|PASS_WITH_WARNINGS|REJECT","reconstructed_ledger":{"scenes":[]},"issue_results":[{"issue_id":"","status":"RESOLVED|UNRESOLVED|PARTIAL|REGRESSED","evidence_quote":"","explanation":""}],"new_regressions":[{"category":"","severity":"hard|medium|soft","quote":"","diagnosis":""}],"patch_results":[{"patch_id":"","valid":true,"unnecessary_change":false,"reason":""}],"rollback_patch_ids":[],"summary":""}"""

    # ═══════════════════════════════════════════════════════════
    # 编排入口
    # ═══════════════════════════════════════════════════════════

    def polish_chapter_text(self, text: str, *,
                            revision: int = 1,
                            plot_beats: tuple[str, ...] = (),
                            write_guidance: str = "") -> str:
        """V4：仅 HARD 连续性审计 + 局部补丁。

        DESIGN 和 STYLE 移出热路径，改为 CLI 旁路报告工具。
        """
        if not text or not text.strip():
            return text
        text = self._strip_boilerplate(text)
        orig_len = len(text)
        text = self._run_hard_loop(text, orig_len, plot_beats=plot_beats)
        return text.strip()

    # ═══════════════════════════════════════════════════════════
    # 回路实现
    # ═══════════════════════════════════════════════════════════

    def _run_hard_loop(self, text: str, orig_len: int, *,
                       plot_beats: tuple[str, ...] = ()) -> str:
        """HARD audit → patch generation → code apply → verify."""
        audit = self._run_audit(text, audit_mode="HARD", plot_beats=plot_beats)
        if not audit:
            return text
        hard_issues = [i for i in audit.get("issues", []) if i.get("severity") == "hard"]
        if not hard_issues:
            return text

        patches_json = self._run_patch_gen(text, hard_issues, plot_beats=plot_beats)
        if not patches_json:
            return text

        patched, applied_count = self._apply_patches(text, patches_json.get("patches", []), budget=orig_len)
        if applied_count == 0:
            return text

        patches_for_verify = patches_json.get("patches", [])
        verdict_json = self._run_verify(text, audit, patched, patches_for_verify, plot_beats=plot_beats)
        verdict = verdict_json.get("verdict", "REJECT") if verdict_json else "REJECT"

        if verdict == "REJECT":
            return text
        return patched

    # ═══════════════════════════════════════════════════════════
    # 确定性补丁应用
    # ═══════════════════════════════════════════════════════════

    @classmethod
    def _apply_patches(cls, text: str, patches: list[dict[str, Any]], *,
                        budget: int = 0,
                        budget_ratio: float | None = None) -> tuple[str, int]:
        if not patches:
            return text, 0
        total_changed = 0
        applied = 0
        result = text
        ratio = budget_ratio if budget_ratio is not None else cls._PATCH_BUDGET
        budget_limit = int(budget * ratio)

        for p in patches:
            before = p.get("before", "")
            after = p.get("after", "")
            op = p.get("operation", "replace")

            before_count = result.count(before)
            if before_count != 1:
                continue
            if len(after) > cls._PATCH_MAX_AFTER_CHARS:
                continue
            if before and len(after) > len(before) * cls._PATCH_AFTER_TO_BEFORE_RATIO:
                continue
            change_size = abs(len(after) - len(before))
            if total_changed + change_size > budget_limit:
                continue

            if op == "delete":
                result = result.replace(before, "", 1)
            elif op == "replace":
                result = result.replace(before, after, 1)
            elif op == "insert_before":
                result = result.replace(before, after + before, 1)
            elif op == "insert_after":
                result = result.replace(before, before + after, 1)
            else:
                continue

            total_changed += change_size
            applied += 1

        return result, applied

    # ═══════════════════════════════════════════════════════════
    # 审计 / 补丁生成 / 验收 — 各阶段 LLM 调用
    # ═══════════════════════════════════════════════════════════

    def _run_audit(self, text: str, *,
                   audit_mode: str = "HARD",
                   plot_beats: tuple[str, ...] = ()) -> dict[str, Any] | None:
        """审计：HARD 或 STYLE 模式。"""
        prompt = self._build_constraint_prompt(plot_beats=plot_beats)
        user_prompt = prompt + f"\n\nAUDIT_MODE：{audit_mode}\n\n正文：\n{text}"
        sys_prompt = self._AUDIT_SYSTEM_PROMPT.replace("{{AUDIT_MODE}}", audit_mode)
        role = "polish_audit" if audit_mode == "HARD" else "polish_repair"
        return self._call_llm_json(sys_prompt, user_prompt, role=role, max_tokens=8000)

    def _run_patch_gen(self, text: str, issues: list[dict[str, Any]], *,
                       plot_beats: tuple[str, ...] = ()) -> dict[str, Any] | None:
        approved = [i for i in issues if i.get("repair_operation") != "AUTHOR_DECISION"]
        if not approved:
            return None
        prompt = self._build_constraint_prompt(plot_beats=plot_beats)
        user_prompt = (
            prompt
            + f"\n\n原始正文：\n{text}"
            + f"\n\n已批准问题：\n{json.dumps(approved, ensure_ascii=False, indent=2)}"
        )
        return self._call_llm_json(
            self._PATCH_SYSTEM_PROMPT, user_prompt,
            role="mechanical_patch", max_tokens=4000, temperature=0.1,
        )

    def _run_verify(self, original: str, audit: dict[str, Any],
                    patched: str, patches: list[dict[str, Any]], *,
                    plot_beats: tuple[str, ...] = ()) -> dict[str, Any] | None:
        prompt = self._build_constraint_prompt(plot_beats=plot_beats)
        user_prompt = (
            prompt
            + f"\n\n原始正文：\n{original}"
            + f"\n\n原审计报告：\n{json.dumps(audit, ensure_ascii=False, indent=2)}"
            + f"\n\n实际应用的补丁：\n{json.dumps(patches, ensure_ascii=False, indent=2)}"
            + f"\n\n修复后正文：\n{patched}"
        )
        return self._call_llm_json(
            self._VERIFY_SYSTEM_PROMPT, user_prompt,
            role="polish_audit", max_tokens=8000,
        )

    @classmethod
    def _build_constraint_prompt(cls, *, plot_beats: tuple[str, ...] = ()) -> str:
        """Build constraint preamble for all stages."""
        parts = [
            f"焦点人物：{cls._FOCAL_CHARACTER}",
            f"视角规则：{cls._POV_MODE}",
        ]
        if plot_beats:
            parts.append("必须保留的剧情节点：\n" + "\n".join(f"  - {b}" for b in plot_beats))
        return "\n\n".join(parts)

    # ── Plan text cleaning ──────────────────────────────────────

    @staticmethod
    def clean_drumbeat_text(text):
        """Remove drumbeat sentence patterns from a text snippet."""
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
        ct = NovelMechanicalGate.clean_drumbeat_text

        cs = plan.content_summary
        new_cs = ContentSummary(
            cause=ct(cs.cause), development=ct(cs.development),
            turning_point=ct(cs.turning_point), climax=ct(cs.climax),
            ending=ct(cs.ending),
        )

        pa = plan.plot_arrangement
        new_pa = PlotArrangement(
            main_line=ct(pa.main_line), sub_line=ct(pa.sub_line),
            event_line=ct(pa.event_line), emotion_line=ct(pa.emotion_line),
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
                beat_id=b.beat_id, description=ct(b.description),
                function_tag=b.function_tag, density=b.density,
                budget_chars=b.budget_chars,
            )
            for b in plan.scene_beats
        )

        ed = plan.ending_design
        new_ed = EndingDesign(
            closing_state=ct(ed.closing_state),
            open_questions=tuple(ct(q) for q in ed.open_questions),
            next_chapter_push=ct(ed.next_chapter_push),
            hook_type=ct(ed.hook_type), hook_detail=ct(ed.hook_detail),
            hook_strength=ed.hook_strength,
        )

        return ChapterPlan(
            schema_id=plan.schema_id, schema_version=plan.schema_version,
            chapter_id=plan.chapter_id, project_id=plan.project_id,
            volume_id=plan.volume_id, chapter_index=plan.chapter_index,
            title=plan.title, target_chars=plan.target_chars,
            chapter_position=plan.chapter_position,
            target_emotion=plan.target_emotion,
            opening_hook=ct(plan.opening_hook),
            main_payoff=ct(plan.main_payoff),
            content_summary=new_cs, plot_arrangement=new_pa,
            character_appearance=new_ca, scene_beats=new_beats,
            ending_design=new_ed,
            cost_and_reward=ct(plan.cost_and_reward),
        )
