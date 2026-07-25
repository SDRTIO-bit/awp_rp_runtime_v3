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
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "抓取指定网页内容并提取正文。适用于查看参考资料、排行榜、新闻等。返回去噪后的纯文本（最多 8000 字）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要抓取的网页 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_novels",
            "description": "在番茄小说/起点等平台搜索小说。返回书名、作者、book_id。需要网络小说下载器服务在后台运行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "preview_novel",
            "description": "预览一本平台小说的详细信息：简介、章节数、字数等。需要先在平台上找到 book_id。",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_id": {"type": "string", "description": "平台小说 ID"},
                },
                "required": ["book_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_novel",
            "description": "下载一本平台小说到本地。下载通常需要 1-5 分钟，后台进行。需要先在平台上找到 book_id。",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_id": {"type": "string", "description": "平台小说 ID"},
                },
                "required": ["book_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_downloads",
            "description": "列出所有已下载到本地的平台小说。显示书名、章节数、文件大小、下载时间。下载文件保存在项目 downloads/ 目录。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
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
| fetch_url | 抓取网页内容并提取正文（查资料、看排行榜） | 3-10s |
| search_novels | 在番茄小说等平台搜索小说（需下载器后台运行） | 2-5s |
| preview_novel | 预览平台小说的详细信息（简介、章节等） | 2-5s |
| download_novel | 下载平台小说到本地 downloads/ 目录 | 1-5min |
| list_downloads | 列出已下载到本地的平台小说 | 即时 |

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
7. **网页抓取**：用户发 URL 时用 fetch_url 直接抓取。需要泛搜时打开网络查询。
8. **下载阅卷**：download_novel 提交后下载在后台进行，文件保存到 `downloads/<book_id>/` 目录。用户要查看下载进度或结果时用 list_downloads 查询。

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
    COMPRESS_MAX_TOKENS = 200_000

    KEEP_TOKEN_BUDGET = 40_000

    MODE_PROMPTS = {
        "auto": "默认工作模式：理解用户指令 → 调用工具 → 汇报结果。一章一事，写后汇报。",
        "brainstorm": (
            "创意发散模式：你是小说创意顾问。\n"
            "规则：\n"
            "1. 不要直接调工具生成内容。先提问、先探索、先给方案。\n"
            "2. 每个回答只问一个问题或给一个方案，等待用户反馈。\n"
            "3. 提出至少 2-3 个创作方向，对比利弊。\n"
            "4. 只有用户明确说'开始写'、'就这样'、'执行'之后，才调用 write_chapter 或 plan_chapter。\n"
            "5. 风格：像一位经验丰富的编剧在和你聊故事可能性。"
        ),
        "research": (
            "深度调研模式：你是研究助手，通过联网搜索和网页抓取帮助验证世界观、查证设定。\n"
            "规则：\n"
            "1. 优先使用 fetch_url 抓取用户指定的 URL 或知名参考网站。\n"
            "2. 需要泛搜时依赖 DeepSeek 联网能力。\n"
            "3. 输出结构化报告：关键发现、验证结论、建议方向。\n"
            "4. 标注信息来源可信度。\n"
            "5. 可以调用 get_status、read_chapter 了解当前项目设定，与搜索结果对比。\n"
            "6. 报告完调查结果后，询问用户下一步行动。"
        ),
    }

    def __init__(self, registry=None, callbacks: BrainCallbacks | None = None,
                 chat_model: str = "deepseek-v4-pro",
                 db_path: str = "",
                 novels_root: str = "",
                 dl_server_url: str = "http://127.0.0.1:18423",
                 dl_output_dir: str = ""):
        self._registry = registry
        self._callbacks = callbacks or BrainCallbacks()
        self._chat_model = chat_model
        self._db_path = db_path
        self._novels_root = novels_root
        self._messages: list[dict[str, Any]] = []
        self._web_search = True
        self._mode = "auto"
        self._compress_count = 0
        self._dl_server_url = dl_server_url
        self._dl_output_dir = dl_output_dir

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
            mode_desc = self.MODE_PROMPTS.get(self._mode, self.MODE_PROMPTS["auto"])
            work_mode = f"## 当前模式: {self._mode}\n{mode_desc}"
            self._messages.append({
                "role": "system", "content": BRAIN_SYSTEM_PROMPT.format(
                    work_mode=work_mode,
                    project_hint=project_hint,
                ),
            })

        self._messages.append({"role": "user", "content": user_message})
        adapter = self._make_chat_adapter()
        result = ""

        # ReAct loop: try calling tools until the LLM responds without a tool_call
        for _round in range(10):
            try:
                msg, _usage = adapter.call_with_tools(
                    messages=self._messages,
                    tools=BRAIN_TOOLS,
                    model=self._chat_model,
                    max_tokens=1000,
                    temperature=0.3,
                    extra_body={"enable_search": True} if self._web_search else None,
                )
            except Exception as exc:
                result = f"LLM 调用失败: {exc}"
                break

            if msg is None:
                result = "（LLM 返回为空）"
                break

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
                result = msg.content or ""
                break

            # Execute tools
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                tool_result = self._execute_tool(tool_name, tool_args)
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })
        else:
            result = "（达到最大对话轮次，请重新提问）"

        self._maybe_compress()
        return result

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
            elif name == "fetch_url":
                return self._tool_fetch_url(args["url"])
            elif name == "search_novels":
                return self._tool_search_novels(args["query"])
            elif name == "preview_novel":
                return self._tool_preview_novel(args["book_id"])
            elif name == "download_novel":
                return self._tool_download_novel(args["book_id"])
            elif name == "list_downloads":
                return self._tool_list_downloads()
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

    def _tool_fetch_url(self, url: str) -> str:
        """Fetch a URL and extract readable text content."""
        import re
        try:
            import httpx
        except ImportError:
            # Fallback to urllib
            from urllib.request import urlopen, Request
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(req, timeout=15) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
            except Exception as e:
                return f"抓取失败: {e}"
        else:
            try:
                resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, follow_redirects=True)
                resp.raise_for_status()
                raw = resp.text
            except Exception as e:
                return f"抓取失败: {e}"

        # Extract text from HTML
        # Remove script/style/noscript/iframe
        raw = re.sub(r'<(script|style|noscript|iframe|svg)[^>]*>.*?</\1>', ' ', raw, flags=re.DOTALL | re.IGNORECASE)
        raw = re.sub(r'<(script|style|noscript|iframe|svg)[^>]*/>', ' ', raw, flags=re.IGNORECASE)

        # Remove HTML comments
        raw = re.sub(r'<!--.*?-->', ' ', raw, flags=re.DOTALL)

        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', ' ', raw)

        # Decode HTML entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
        text = re.sub(r'&#\d+;', ' ', text)
        text = re.sub(r'&#x[0-9a-fA-F]+;', ' ', text)

        # Collapse whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        text = text.strip()

        if not text:
            return f"网页内容为空（可能需 JavaScript 渲染）: {url}"

        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... (已截断，原文共 {len(text)} 字符)"

        return f"来源: {url}\n\n{text}"

    # ── Downloader tools ──

    def _call_dl_api(self, method: str, path: str, json_data: dict | None = None) -> str:
        """Call the Tomato Novel Downloader REST API. Returns body text or error."""
        import json
        url = f"{self._dl_server_url}{path}"
        try:
            import httpx
        except ImportError:
            from urllib.request import urlopen, Request
            try:
                body_bytes = json.dumps(json_data).encode() if json_data else None
                req = Request(url, data=body_bytes, method=method,
                              headers={"Content-Type": "application/json"})
                with urlopen(req, timeout=10) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except Exception as e:
                return f"下载器 API 调用失败: {e}\n请确认番茄小说下载器已启动（运行 --server 模式侦听 {self._dl_server_url}）"
        else:
            try:
                if method == "GET":
                    resp = httpx.get(url, timeout=10)
                elif method == "POST":
                    resp = httpx.post(url, json=json_data or {}, timeout=10)
                else:
                    return f"不支持的 HTTP 方法: {method}"
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                return f"下载器 API 调用失败: {e}\n请确认番茄小说下载器已启动（运行 --server 模式侦听 {self._dl_server_url}）"

    def _tool_search_novels(self, query: str) -> str:
        import json
        raw = self._call_dl_api("GET", f"/api/search?q={query}")
        if raw.startswith("下载器 API"):
            return raw
        try:
            data = json.loads(raw)
            items = data.get("items", [])
            if not items:
                return f"未搜到与「{query}」相关的小说。"
            lines = [f"搜索「{query}」的结果 ({len(items)} 条):"]
            for i, item in enumerate(items[:10], 1):
                lines.append(
                    f"  {i}. 《{item.get('title', '?')}》"
                    f" — {item.get('author', '?')}"
                    f" | book_id={item.get('book_id', '?')}"
                )
            return "\n".join(lines)
        except json.JSONDecodeError:
            return f"下载器返回格式异常: {raw[:500]}"

    def _tool_preview_novel(self, book_id: str) -> str:
        import json
        raw = self._call_dl_api("GET", f"/api/preview/{book_id}")
        if raw.startswith("下载器 API"):
            return raw
        try:
            data = json.loads(raw)
            return (
                f"书名: 《{data.get('book_name', data.get('title', '?'))}》\n"
                f"作者: {data.get('author', '?')}\n"
                f"简介: {str(data.get('description', data.get('intro', '')))[:500]}\n"
                f"总章节: {data.get('chapter_count', '?')}\n"
                f"总字数: {data.get('word_count', '?')}\n"
                f"状态: {'已完成' if data.get('finished') else '连载中'}\n"
                f"评分: {data.get('score', '?')}\n"
                f"分类: {', '.join(data.get('tags', []))[:200]}\n"
                f"book_id: {book_id}"
            )
        except json.JSONDecodeError:
            return f"下载器返回格式异常: {raw[:500]}"

    def _tool_download_novel(self, book_id: str) -> str:
        raw = self._call_dl_api("POST", "/api/jobs", {"book_id": book_id})
        if raw.startswith("下载器 API"):
            return raw
        out_dir = self._dl_output_dir or "downloads/"
        return (
            f"下载任务已提交 (book_id={book_id})。\n"
            f"文件将保存到 `{out_dir}{book_id}/`，通常需 1-5 分钟。\n"
            f"下载完成后用 list_downloads 查看结果。"
        )

    def _tool_list_downloads(self) -> str:
        """Scan download output directory and list downloaded novels."""
        import os as _os
        dir_path = self._dl_output_dir
        if not dir_path or not _os.path.isdir(dir_path):
            return "下载目录不存在。请先用 /dl-dir 设置下载目录。"

        entries = []
        for entry in sorted(_os.scandir(dir_path), key=lambda e: e.name):
            if entry.is_dir():
                size = _sum_dir_size(entry.path)
                # look for metadata
                mtime = _os.path.getmtime(entry.path)
                import datetime as _dt
                ts = _dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                entries.append(f"  📁 {entry.name}  ({_fmt_size(size)}, {ts})")
        if not entries:
            return f"下载目录 `{dir_path}` 为空。"
        return f"已下载小说 ({dir_path}):\n" + "\n".join(entries)

    # ── Context compression ──

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token count for mixed CN/EN text. ~2 chars per token."""
        if not text:
            return 0
        return max(1, len(text) // 2)

    def _message_tokens(self, msg: dict) -> int:
        """Estimate tokens for a single message including role overhead."""
        content = msg.get("content", "")
        if isinstance(content, list):
            text = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
        else:
            text = str(content) if content else ""
        return self._estimate_tokens(text) + 4

    def _count_context_tokens(self) -> int:
        """Estimate total tokens across all messages."""
        return sum(self._message_tokens(m) for m in self._messages)

    def _safe_cut(self, raw_cut: int) -> int:
        """Adjust cut point so it never splits a tool_call / tool result pair.

        Ensures the recent section (messages from cut onward) is valid:
        - No orphaned tool msgs (tool without preceding assistant(tool_calls))
        - No assistant(tool_calls) split from its tool replies
        """
        cut = raw_cut
        while cut < len(self._messages):
            msg = self._messages[cut]
            if msg.get("role") == "tool":
                cut += 1
            elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                cut += 1
                while cut < len(self._messages) and self._messages[cut].get("role") == "tool":
                    cut += 1
            else:
                break
        return cut

    def _maybe_compress(self) -> bool:
        if self._count_context_tokens() < self.COMPRESS_MAX_TOKENS:
            return False
        self._compress_context()
        return True

    def _compress_context(self) -> None:
        if len(self._messages) <= 2:
            return

        total = self._count_context_tokens()
        if total < self.COMPRESS_MAX_TOKENS:
            return

        system_msg = self._messages[0]

        # Walk backward from end, accumulating tokens until budget exhausted
        acc = 0
        cut = len(self._messages)
        for i in range(len(self._messages) - 1, 0, -1):
            msg = self._messages[i]
            role = msg.get("role", "")
            tokens = self._message_tokens(msg)

            # Keep assistant(tool_calls) + its tool replies as a unit
            if role == "tool":
                tokens = self._message_tokens(msg)
                # Walk back to include assistant(tool_calls) too
                for j in range(i - 1, 0, -1):
                    prev = self._messages[j]
                    if prev.get("role") == "assistant" and prev.get("tool_calls"):
                        tokens += self._message_tokens(prev)
                        i = j
                        break

            acc += tokens
            cut = i

            if acc >= self.KEEP_TOKEN_BUDGET:
                break

        # Adjust cut to a safe pair boundary
        cut = self._safe_cut(cut)
        if cut <= 1 or cut >= len(self._messages):
            return

        middle = self._messages[1:cut]
        recent = self._messages[cut:]
        if not middle:
            return

        self._compress_count += 1
        summary = self._summarize_messages(middle)
        self._messages = [system_msg] + [{
            "role": "system",
            "content": (
                f"## 对话历史摘要 (第{self._compress_count}次压缩, "
                f"原始{len(middle)}条消息)\n{summary}"
            ),
        }] + recent

    def _summarize_messages(self, messages: list[dict[str, Any]]) -> str:
        transcript = []
        for m in messages:
            role = m.get("role", "?")
            content = m.get("content", "")
            if role == "tool":
                transcript.append(f"[工具返回] {content[:300]}")
            elif role == "assistant" and content:
                transcript.append(f"[助手] {content[:400]}")
            elif role == "user" and content:
                transcript.append(f"[用户] {content[:400]}")
            elif role == "system":
                transcript.append(f"[系统] {content[:200]}")

        if not transcript:
            return "无内容"

        prompt = (
            "请用 200 字以内的中文总结以下对话记录的关键信息，"
            "包括：用户的要求、做出的决策、完成的操作和结果。\n\n"
            + "\n".join(transcript)
        )

        try:
            adapter = self._make_chat_adapter()
            summary_text, _receipt = adapter.generate_text(
                prompt,
                max_tokens=300,
                provider_role="continuity_checker",
                model="deepseek-v4-pro",
            )
            if summary_text and summary_text.strip():
                return summary_text.strip()
        except Exception:
            pass
        return "（摘要生成失败）"

    def compress(self) -> str:
        old_count = len(self._messages)
        old_tokens = self._count_context_tokens()
        self._compress_context()
        new_count = len(self._messages)
        new_tokens = self._count_context_tokens()
        return (
            f"上下文压缩完成: {old_count} → {new_count} 条消息, "
            f"~{old_tokens} → ~{new_tokens} tokens "
            f"(第{self._compress_count}次压缩)"
        )

    # ── Web search ──

    def enable_web_search(self) -> None:
        self._web_search = True

    def disable_web_search(self) -> None:
        self._web_search = False

    def toggle_web_search(self) -> bool:
        self._web_search = not self._web_search
        return self._web_search

    @property
    def web_search_enabled(self) -> bool:
        return self._web_search

    # ── Mode ──

    def set_mode(self, mode: str) -> str:
        if mode not in self.MODE_PROMPTS:
            return f"未知模式: {mode}。可用: {', '.join(self.MODE_PROMPTS)}"
        old = self._mode
        self._mode = mode
        if old != mode:
            self._messages = []  # reset context for mode switch
        return f"模式已切换: {old} → {mode}"

    @property
    def mode(self) -> str:
        return self._mode

    # ── Utility ──

    @property
    def dl_server_url(self) -> str:
        return self._dl_server_url

    @dl_server_url.setter
    def dl_server_url(self, url: str) -> None:
        self._dl_server_url = url

    @property
    def dl_output_dir(self) -> str:
        return self._dl_output_dir

    @dl_output_dir.setter
    def dl_output_dir(self, path: str) -> None:
        self._dl_output_dir = path

    def reset(self) -> None:
        self._messages.clear()
        self._compress_count = 0


# ── Module-level helpers ──

def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes / (1024 * 1024):.1f}MB"


def _sum_dir_size(dir_path: str) -> int:
    import os as _os
    total = 0
    for root, _dirs, files in _os.walk(dir_path):
        for f in files:
            fp = _os.path.join(root, f)
            try:
                total += _os.path.getsize(fp)
            except OSError:
                pass
    return total
