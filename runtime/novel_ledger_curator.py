"""NovelLedgerCurator — Ledger Curator for novel mode.

Uses DeepSeekAdapter with thinking=medium for extracting continuity information
and producing narrative chapter summaries.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from ..contracts.novel_pi_role_protocol import NovelPiRoleTask
from .novel_role_context import get_novel_role_context
from .novel_role_runtime import get_novel_role_runtime


LEDGER_CURATOR_PROMPT = """=== STABLE LEDGER CURATOR CONTRACT ===
你负责维护长篇小说的连续性账本。分析已接受的章节正文，产出叙事级章节总结 + 结构化事实更新。

=== 你的两项产出 ===
A. 【章节总结】(chapter_summary): 叙事级的本章摘要，3-5句，供后续章节的 Architect/Director/Writer 直接阅读。
   必须包含: 本章发生了什么事 / 谁出场做了什么 / 关键互动 / 新揭示的信息 / 结尾悬念。
   示例: "陈默在苏念的催促下起床上学，在教室因迟到被班主任李建国批评。课间陈默在旧图书馆四楼发现一本1998年的旧日记，里面提到一个姓陈的男孩。沈溪来收作业时不小心暴露了她在看言情小说，被王磊起哄，课后走廊警告陈默不许说出去。放学时陈默从日记中掉落一张马尾少女的旧照片，苏念追问照片是谁。"
B. 【事实更新】(ledger_updates): 结构化条目，用于角色状态追踪、伏笔管理、时间线。

=== ledger_updates 每个条目的精确 JSON Schema ===
每个条目必须包含以下固定字段:
{
  "section": "character_state | timeline | foreshadowing | relationship | world_rules | open_threads",
  "entity": "关联角色名或实体名",
  "content": "具体事实描述，一句话",
  "status": "active | resolved | stale",
  "field": "可选，如果是角色状态变化，填写变化的字段名(location/emotion/identity/ability/relationship/public_image等)"
}

section 说明:
- character_state: 角色位置/情绪/身份等变化
- relationship: 角色间关系变化（亲近/疏远/对立/新建立）
- timeline: 时间线事件
- foreshadowing: 新埋设的伏笔
- world_rules: 新设定的规则/背景信息
- open_threads: 新出现的未解决线索/疑问

伏笔状态: planted(新埋) | advanced(推进) | paid_off(回收) | stale(过期)

=== 严禁 ===
- 虚构原文没有的事实
- 把计划当成实际发生
- 使用模糊词（"似乎""可能""大概"）
"""


class NovelLedgerCurator:
    """Ledger Curator for novel mode."""

    def __init__(self, registry, model: str = "deepseek-v4-flash"):
        self._registry = registry
        self._model = model

    def curate(
        self,
        chapter_text: str,
        chapter_plan: Any,
        current_ledger_items: list,
        previous_chapter_summaries: list[str] | None = None,
    ) -> dict:
        """Analyze accepted chapter and produce summary + ledger updates.

        Returns dict with:
        - chapter_summary: 3-5 sentence narrative summary
        - ledger_updates: list of new/modified ledger items (dicts with section/entity/content/status)
        - ledger_resolves: list of item_ids to mark as resolved
        - foreshadowing_changes: list of foreshadowing status changes
        """
        system_prompt, user_prompt = self._build_prompt(
            chapter_text, chapter_plan, current_ledger_items, previous_chapter_summaries
        )
        context = get_novel_role_context()
        result = get_novel_role_runtime().run(
            NovelPiRoleTask(
                role="ledger_curator",
                project_id=context.project_id,
                chapter_index=context.chapter_index,
                revision=context.revision,
                phase="ledger_curate",
                session_key=f"task:{uuid.uuid4().hex}",
                task_contract=system_prompt,
                input_payload={
                    "prompt": user_prompt,
                    "response_format": "ledger_update_json",
                },
            ),
            context=context,
        )
        text = result.text

        try:
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            result = json.loads(text)
            return result
        except (json.JSONDecodeError, IndexError, KeyError):
            return {
                "chapter_summary": text[:200] if text else "",
                "ledger_updates": [],
                "ledger_resolves": [],
                "foreshadowing_changes": [],
            }

    def _build_prompt(
        self, chapter_text, chapter_plan, current_ledger_items,
        previous_chapter_summaries: list[str] | None = None
    ) -> tuple[str, str]:
        parts = []

        if previous_chapter_summaries:
            parts.append("=== PREVIOUS CHAPTER SUMMARIES ===\n")
            for s in previous_chapter_summaries:
                parts.append(f"- {s}")
            parts.append("")

        if chapter_plan:
            parts.append(f"=== CHAPTER PLAN ===\n{chapter_plan.to_dict() if hasattr(chapter_plan, 'to_dict') else chapter_plan}")

        parts.append(f"\n=== CHAPTER TEXT ===\n{chapter_text[:6000]}")

        if current_ledger_items:
            items_text = "\n".join(
                f"- [{i.status}] [{i.section}] {i.entity}: {i.content}"
                for i in current_ledger_items[:30]
            )
            parts.append(f"\n=== CURRENT LEDGER (existing facts) ===\n{items_text}")

        parts.append("\n=== OUTPUT (strict JSON, no markdown wrapping) ===\n"
                     '{\n'
                     '  "chapter_summary": "3-5句叙事级中文总结，见 contract",\n'
                     '  "ledger_updates": [\n'
                     '    {"section": "character_state", "entity": "角色名", "content": "具体事实", "status": "active", "field": "变化的字段"},\n'
                     '    {"section": "relationship", "entity": "角色名A", "content": "与B的关系变化", "status": "active", "field": "relationship"},\n'
                     '    {"section": "foreshadowing", "entity": "伏笔名称", "content": "描述", "status": "planted"},\n'
                     '    {"section": "timeline", "entity": "事件名", "content": "时间线描述", "status": "active"},\n'
                     '    {"section": "open_threads", "entity": "线索名", "content": "未解决的线索", "status": "active"}\n'
                     '  ],\n'
                     '  "ledger_resolves": ["item_id_1", "item_id_2"],\n'
                     '  "foreshadowing_changes": [{"id": "item_id", "new_status": "advanced"}]\n'
                     '}')

        return LEDGER_CURATOR_PROMPT, "\n".join(parts)
