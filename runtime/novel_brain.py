"""NovelBrain — LLM agent that controls the novel pipeline via natural language.

The brain is a ReAct-style agent: user says what they want in natural language,
the brain calls tool functions (list projects, check status, write chapters, etc.),
and reports results back in cc-style dialogue.

Architecture:
- NovelBrain: stateless agent, one message → one or more tool calls → one response
- TUI layer: manages conversation flow, auto-continue loops, streaming display
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable


# ── Brain-specific callbacks (extend NovelStreamCallbacks with thread-safety) ──

@dataclass
class BrainCallbacks:
    """Callbacks that the brain passes to the engine during tool execution.
    The TUI wires these to Textual widgets via call_from_thread."""
    on_phase: Callable[[str, str, dict[str, Any]], None] = field(default=lambda e, n, p: None)
    on_beat: Callable[[str, int, dict[str, Any]], None] = field(default=lambda e, i, p: None)
    on_chunk: Callable[[str], None] = field(default=lambda t: None)
    on_error: Callable[[str, str], None] = field(default=lambda ph, msg: None)
    on_chat: Callable[[str], None] = field(default=lambda msg: None)


# ── Tool definitions (OpenAI function-calling format) ──

BRAIN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_project",
            "description": "创建一个新的小说项目。传入一个一句话思路，AI 会自动生成完整大纲（角色、分卷、世界观）。创建完成后 project_id 自动设为项目名。需要 30-60 秒。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "项目目录名（英文/拼音）"},
                    "concept": {"type": "string", "description": "一句话故事思路"},
                },
                "required": ["name", "concept"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": "列出所有小说项目。返回每个项目的 ID、标题、类型、状态。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "获取指定小说项目的详细状态：当前进度、章节列表、角色状态、账本概览。",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID（如 dragon_king）"},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_chapter",
            "description": "生成指定项目的某一章正文。会自动调用 Director→Writer→Quality→Ledger 完整管线。生成过程可能需要 30-120 秒。返回章节状态、字数、质量判决。",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID"},
                    "chapter": {"type": "integer", "description": "章节编号"},
                },
                "required": ["project_id", "chapter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_chapter",
            "description": "规划指定项目的某一章（Architect Agent）。生成章节定位、场景节拍、情绪弧线、字数预算。写入数据库供后续 write_chapter 使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID"},
                    "chapter": {"type": "integer", "description": "章节编号"},
                    "task_description": {"type": "string", "description": "本章任务描述（可选）"},
                },
                "required": ["project_id", "chapter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_chapter",
            "description": "读取已生成章节的正文内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID"},
                    "chapter": {"type": "integer", "description": "章节编号"},
                },
                "required": ["project_id", "chapter"],
            },
        },
    },
]

BRAIN_SYSTEM_PROMPT = """你是 **小说创作工坊的管家**—— 一个专业的小说管线协作者。你不是写手，而是调度中枢：通过工具驱动 Architect→Director→Writer→Quality→Ledger 完整管线来产出小说章节。

## 你的工具箱

| 工具 | 用途 | 耗时 |
|------|------|------|
| list_projects | 查看所有项目列表 | 即时 |
| get_status | 查看项目进度、角色、分卷、已写章节 | 即时 |
| create_project | 用一句话思路创建新项目（自动生成大纲+角色+分卷） | 30-60s |
| plan_chapter | 为指定章节生成细纲（节拍、情绪弧、角色动向） | 10-20s |
| write_chapter | 执行完整管线生成章节正文 | 30-120s |
| read_chapter | 读取已生成章节的正文内容 | 即时 |

## 工作流原则

1. **先看后动**：别猜。用户说"继续写下一章"之前，先用 get_status 确认当前进度、下一章是哪一章、有没有 plan。
2. **一章一事**：完成当前操作并报告结果后，再进行下一步。不要一口气连续调用多个工具。
3. **写后汇报**：write_chapter 完成后必须告知用户：章节号、字数、是否通过质量门（accepted/rejected）、如有 rejection 要说明原因。
4. **自动接力**：如果用户说"继续"或"一直写到X章"，每写完一章后：
   - 若 accepted → 报告进度，立即 plan 下一章，然后 write，无需等待用户确认。
   - 若 rejected → 报告拒稿原因，询问用户是否重试或修改。
   - 达到目标章节后 → 总结已完成的所有章节。
5. **无纲不写**：如果用户要求 write 一个还没有 plan 的章节，先提醒并用 plan_chapter 生成细纲，再 write。
6. **创建即连接**：create_project 成功后自动连接到新项目，然后汇报项目概况（标题、类型、分卷数、角色数）。

## 对话风格
- 用中文回复。像一位经验丰富的编辑在和你聊项目进度。
- 简洁。不废话。用数据说话（"第3章 2460字 accepted ✓"）。
- 发现异常要主动提示，不是默默失败。
- 如果不知道用户在说什么，直接问。

## 当前模式
{work_mode}
{project_hint}
"""


class NovelBrain:
    """LLM agent for controlling the novel pipeline via natural language.

    registry can be None when no project is connected — list_projects and
    create_project still work (filesystem-based), other tools will prompt
    the user to connect first.
    """

    def __init__(self, registry=None, callbacks: BrainCallbacks | None = None,
                 chat_model: str = "deepseek-v4-pro",
                 db_path: str = "",
                 novels_root: str = ""):
        self._registry = registry
        self._callbacks = callbacks or BrainCallbacks()
        self._chat_model = chat_model
        self._db_path = db_path
        self._novels_root = novels_root
        self._messages: list[dict[str, Any]] = []

    # ── Build engine ──

    def _make_engine(self):
        from .novel_engine import NovelEngine
        from .novel_trace import NovelStreamCallbacks

        cb = self._callbacks
        stream_cb = NovelStreamCallbacks(
            on_phase=cb.on_phase,
            on_beat=cb.on_beat,
            on_chunk=cb.on_chunk,
            on_error=cb.on_error,
        )
        return NovelEngine(self._registry, callbacks=stream_cb)

    def _require_registry(self) -> str | None:
        """Returns an error message if no project is connected, else None."""
        if self._registry is not None:
            return None
        return "请先连接到项目。使用 /open <项目名> 选择已有项目，或 /new <项目名> <思路> 创建新项目。"

    def _make_chat_adapter(self):
        from .novel_llm_factory import NovelLLMFactory
        factory = NovelLLMFactory.get_instance()
        return factory.get_adapter("brain")

    # ── Public API ──

    def handle_message(self, user_message: str) -> str:
        """Process one user message. Returns the brain's response text.
        Side effect: may call tools (write chapters, etc.) which trigger
        the TUI callbacks for streaming progress display.
        """
        if not self._messages:
            project_hint = ""
            if self._registry is None:
                project_hint = (
                    "\n## 注意\n"
                    "当前未连接到任何项目。你可以用 list_projects 查看已有项目，"
                    "也可以用 create_project 创建新项目。"
                    "要读写章节内容需要先让用户打开一个项目。"
                )
            self._messages.append({
                "role": "system", "content": BRAIN_SYSTEM_PROMPT.format(
                    work_mode="单次对话模式：响应用户指令后即可等待下一条消息。",
                    project_hint=project_hint,
                ),
            })

        self._messages.append({"role": "user", "content": user_message})
        adapter = self._make_chat_adapter()

        # ReAct loop: try calling tools until the LLM responds without a tool_call
        for _round in range(10):
            try:
                msg, _usage = adapter.call_with_tools(
                    messages=self._messages,
                    tools=BRAIN_TOOLS,
                    model=self._chat_model,
                    max_tokens=1000,
                    temperature=0.3,
                )
            except Exception as exc:
                return f"LLM 调用失败: {exc}"

            if msg is None:
                return "（LLM 返回为空）"

            # Append assistant message
            assistant_msg = {"role": "assistant"}
            if msg.content:
                assistant_msg["content"] = msg.content
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
            self._messages.append(assistant_msg)

            # If no tool calls, this is the final response
            if not msg.tool_calls:
                return msg.content or ""

            # Execute tools
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                result = self._execute_tool(tool_name, tool_args)
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        return "（达到最大对话轮次，请重新提问）"

    def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """Execute a tool and return result string for LLM consumption."""
        try:
            if name == "create_project":
                return self._tool_create_project(args["name"], args["concept"])
            elif name == "list_projects":
                return self._tool_list_projects()
            elif name == "get_status":
                return self._tool_get_status(args["project_id"])
            elif name == "write_chapter":
                return self._tool_write_chapter(args["project_id"], int(args["chapter"]))
            elif name == "plan_chapter":
                return self._tool_plan_chapter(
                    args["project_id"], int(args["chapter"]),
                    args.get("task_description", ""),
                )
            elif name == "read_chapter":
                return self._tool_read_chapter(args["project_id"], int(args["chapter"]))
            else:
                return f"未知工具: {name}"
        except Exception as exc:
            return f"工具执行失败 ({name}): {exc}"

    # ── Tool implementations ──

    def _tool_create_project(self, name: str, concept: str) -> str:
        import json
        from pathlib import Path
        from .novel_planner_adapter import NovelPlannerAdapter
        from ..storage.sqlite.database import Database

        novels_root = Path(self._db_path).resolve().parent if self._db_path else Path(__file__).resolve().parent.parent / "novels"
        nd = novels_root / name
        if nd.exists():
            return f"项目 {name} 已存在。可直接 /open {name}。"

        nd.mkdir(parents=True, exist_ok=True)
        db_path = str((nd / "novel.db").resolve())
        db = Database(db_path)
        db.initialize()
        from .session_runtime_registry import SessionRuntimeStoreRegistry
        reg = SessionRuntimeStoreRegistry(db)

        plan = NovelPlannerAdapter(reg).plan_novel(concept=concept, title=name)
        project_id = f"novel-{plan.title}"
        state = {"project_id": project_id, "db_path": db_path}
        (nd / ".novel_cli.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        return (
            f"项目创建成功！\n"
            f"- 书名: 《{plan.title}》\n"
            f"- 题材: {plan.genre}\n"
            f"- 卷数: {len(plan.volumes)}\n"
            f"- 核心情感: {plan.core_emotion}\n"
            f"- project_id: {project_id}\n"
            f"\n现在可以用 plan_chapter 和 write_chapter 生成内容。"
        )

    def _tool_list_projects(self) -> str:
        # Try registry first, fall back to filesystem scan
        if self._registry is not None:
            try:
                projects = self._registry.novel_project_store.list_all()
                if projects:
                    lines = []
                    for p in projects:
                        lines.append(
                            f"- {p.project_id}: 《{p.title}》({p.genre}) 状态={p.status}"
                        )
                    return "\n".join(lines)
            except AttributeError:
                pass

        # Filesystem fallback
        import json
        from pathlib import Path
        root = Path(self._novels_root) if self._novels_root else Path(__file__).resolve().parent.parent / "novels"
        if not root.exists():
            return "novels/ 目录不存在，且没有连接到任何项目。"

        found = []
        for d in root.iterdir():
            state_file = d / ".novel_cli.json"
            if d.is_dir() and state_file.exists():
                try:
                    st = json.loads(state_file.read_text(encoding="utf-8"))
                    pid = st.get("project_id", d.name)
                    found.append(f"- {d.name} → {pid}")
                except Exception:
                    found.append(f"- {d.name}")

        if not found:
            return "当前没有小说项目。在聊天中说'创建一个XX项目'即可开始。"
        return "可用项目:\n" + "\n".join(found)

    def _tool_get_status(self, project_id: str) -> str:
        if err := self._require_registry():
            return err
        project = self._registry.novel_project_store.load(project_id)
        if not project:
            return f"项目 {project_id} 不存在。"

        lines = [f"项目: 《{project.title}》({project_id}) | {project.genre} | {project.status}"]

        characters = self._registry.novel_character_store.list_by_project(project_id)
        lines.append(f"\n角色 ({len(characters)}):")
        for c in characters:
            lines.append(f"  [{c.role}] {c.name} | arc={c.arc_phase}")

        plans = self._registry.novel_chapter_plan_store.list_by_project(project_id)
        draft_store = self._registry.novel_chapter_draft_store
        lines.append(f"\n章节状态 ({len(plans)}):")
        for p in plans:
            chapter_id = p.chapter_id or f"ch-{project_id}-{p.chapter_index}"
            draft = draft_store.load_latest(chapter_id)
            if draft:
                status_icon = "✓" if draft.status == "accepted" else "⚠"
                lines.append(
                    f"  [{status_icon}] 第{p.chapter_index}章 {p.title} | "
                    f"{p.chapter_position} | {draft.char_count}字 | {draft.status}"
                )
            else:
                lines.append(f"  [○] 第{p.chapter_index}章 {p.title} | {p.chapter_position} | 未生成")

        ledger = self._registry.novel_ledger_store.list_by_project(project_id)
        sections = {}
        for li in ledger:
            sections.setdefault(li.section, 0)
            sections[li.section] += 1
        lines.append(f"\n账本 ({len(ledger)} 条):")
        for s, cnt in sections.items():
            lines.append(f"  {s}: {cnt}条")

        return "\n".join(lines)

    def _tool_plan_chapter(self, project_id: str, chapter: int, task: str) -> str:
        if err := self._require_registry():
            return err
        engine = self._make_engine()
        plan = engine.plan_chapter(
            project_id=project_id,
            chapter_index=chapter,
            task_description=task or f"第{chapter}章",
        )
        return (
            f"第{chapter}章规划完成。\n"
            f"  标题: {plan.title}\n"
            f"  定位: {plan.chapter_position}\n"
            f"  目标情绪: {plan.target_emotion}\n"
            f"  目标字数: {plan.target_chars}\n"
            f"  场景节拍: {len(plan.scene_beats)} 个"
        )

    def _tool_write_chapter(self, project_id: str, chapter: int) -> str:
        if err := self._require_registry():
            return err
        plan = self._registry.novel_chapter_plan_store.load_by_index(project_id, chapter)
        if not plan:
            return (
                f"第{chapter}章尚未规划。请先运行 plan，或告诉我 '规划第{chapter}章'。"
            )

        engine = self._make_engine()
        draft = engine.write_chapter_stream(
            project_id=project_id,
            chapter_index=chapter,
        )
        return (
            f"第{chapter}章生成完成。\n"
            f"  标题: {plan.title}\n"
            f"  字数: {draft.char_count}\n"
            f"  状态: {draft.status}\n"
            f"  正文预览: {draft.text[:200]}..."
        )

    def _tool_read_chapter(self, project_id: str, chapter: int) -> str:
        if err := self._require_registry():
            return err
        plan = self._registry.novel_chapter_plan_store.load_by_index(project_id, chapter)
        if not plan:
            return f"第{chapter}章不存在。"

        draft = self._registry.novel_chapter_draft_store.load_latest(
            plan.chapter_id or f"ch-{project_id}-{chapter}"
        )
        if not draft or not draft.text:
            return f"第{chapter}章尚未生成。"

        # Return summary + full text
        preview_len = min(2000, len(draft.text))
        return (
            f"第{chapter}章《{plan.title}》\n"
            f"字数: {draft.char_count} | 状态: {draft.status}\n\n"
            f"{draft.text[:preview_len]}\n\n"
            f"... (共 {draft.char_count} 字)"
        )

    # ── Utility ──

    def reset(self) -> None:
        self._messages.clear()
