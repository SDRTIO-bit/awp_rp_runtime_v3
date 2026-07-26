#!/usr/bin/env python3
"""AWP Novel TUI — Textual-powered terminal dashboard for novel pipeline.

左右分屏：左侧管线实时进度，右侧为专属写作编辑对话。

用法:
  python scripts/awp_tui.py [novel_dir]
  python scripts/awp_tui.py novels/dragon_king
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

# Session directory: Windows → %LOCALAPPDATA%/awp/sessions, else → ~/.config/awp/sessions
_SESSIONS_ROOT = Path(
    os.environ.get("LOCALAPPDATA", "") or os.environ.get("HOME", "")
) / "awp" / "sessions"
_DEFAULT_SESSION_NAME = "last"

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, RichLog, Input
from textual import events

from awp_rp_runtime_v3.runtime.novel_brain import BrainCallbacks
from awp_rp_runtime_v3.runtime.novel_agent_runtime import create_novel_agent_runtime
from awp_rp_runtime_v3.runtime.novel_llm_factory import NovelLLMFactory
from awp_rp_runtime_v3.runtime.novel_role_runtime import get_novel_role_runtime
from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from awp_rp_runtime_v3.storage.sqlite.database import Database


# ── Terminal color tags ──

GREEN = "\033[92m"
RED = "\033[91m"
DIM = "\033[2m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ── Phase ordering ──

PHASE_ORDER = ["architect", "director", "writer", "quality", "continuity", "ledger"]
PHASE_LABELS = {
    "architect": "Architect  ",
    "director": "Director   ",
    "writer": "Writer     ",
    "quality": "Quality    ",
    "continuity": "Continuity ",
    "ledger": "Ledger     ",
}

# ── Helpers ──

def _find_novel_dirs(base_dir: str) -> list[Path]:
    dirs: list[Path] = []
    novels_root = PROJECT_ROOT / base_dir
    if novels_root.exists():
        for d in novels_root.iterdir():
            if d.is_dir() and (d / ".novel_cli.json").exists():
                dirs.append(d)
    return dirs


def _load_state(novel_dir: Path) -> dict | None:
    state_file = novel_dir / ".novel_cli.json"
    if not state_file.exists():
        return None
    return json.loads(state_file.read_text(encoding="utf-8"))


def _sessions_dir() -> Path:
    d = _SESSIONS_ROOT
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(name: str) -> Path:
    return _sessions_dir() / f"{name}.json"


def _save_session(name: str, data: dict) -> None:
    _session_path(name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_session(name: str) -> dict | None:
    p = _session_path(name)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _list_sessions() -> list[dict]:
    result = []
    for f in sorted(_sessions_dir().glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        data = json.loads(f.read_text(encoding="utf-8"))
        data["_name"] = f.stem
        result.append(data)
    return result


# ── Textual App ──

class NovelTui(App):
    """AWP Novel Pipeline TUI — 左右分屏控制台."""

    CSS = """
    Screen {
        layout: horizontal;
        background: $surface;
    }

    #left-panel {
        width: 40%;
        border: solid $primary-background;
        background: $surface;
    }

    #right-panel {
        width: 60%;
        border: solid $secondary-background;
        background: $surface;
    }

    #project-header {
        height: 3;
        padding: 0 1;
        background: $primary-darken-1;
        color: $text;
        content-align: left middle;
    }

    #phase-status {
        height: 10;
        border: solid $panel-lighten-1;
        margin: 1;
        padding: 0 1;
    }

    #writer-output {
        height: 1fr;
        border: solid $panel-lighten-1;
        margin: 1;
        overflow-x: hidden;
        overflow-y: scroll;
    }

    #chat-history {
        height: 1fr;
        border: solid $panel-lighten-1;
        margin: 1;
        overflow-x: hidden;
        overflow-y: scroll;
    }

    #chat-input {
        height: 3;
        border: solid $accent;
        margin: 1;
        dock: bottom;
    }

    Footer {
        background: $primary-darken-1;
    }
    """

    TITLE = "AWP — Novel Pipeline"
    SUB_TITLE = "Press Ctrl+C to quit"

    BINDINGS = [
        Binding("escape", "focus_input", "Chat"),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+r", "reset_brain", "Reset"),
        Binding("ctrl+s", "toggle_search", "Search"),
        Binding("ctrl+x", "cancel_agent", "Cancel"),
    ]

    def __init__(self, novel_dir: str | None = None):
        super().__init__()
        self._novel_dir_input = novel_dir
        self._novel_dir: Path | None = None
        self._state: dict | None = None
        self._store_registry: SessionRuntimeStoreRegistry | None = None
        self._brain: Any | None = None
        self._brain_callbacks: BrainCallbacks | None = None
        self._phase_data: dict[str, dict[str, str]] = {}
        self._writer_lines: list[str] = []
        self._busy = False
        self._init_phase_data()

    def _init_phase_data(self) -> None:
        self._phase_data = {}
        for p in PHASE_ORDER:
            self._phase_data[p] = {"status": "○", "detail": "", "time": ""}

    # ── Compose ──

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="left-panel"):
                yield Static(id="project-header", content="[b]Novel Pipeline[/b]\n请选择项目...")
                yield Static(id="phase-status", content=self._render_phases())
                yield RichLog(id="writer-output", highlight=True, markup=True, wrap=True)
            with Vertical(id="right-panel"):
                yield RichLog(id="chat-history", highlight=True, markup=True, wrap=True)
                yield Input(id="chat-input", placeholder="与专属写作编辑讨论创作... (Enter 发送)")
        yield Footer()

    def on_mount(self) -> None:
        self._setup_headless()
        self._init_brain()
        self._render_project_header()
        self._try_restore_session()

    def _setup_headless(self) -> None:
        """Find a novel project to connect to."""
        # If a dir was provided on the command line
        if self._novel_dir_input:
            nd = Path(self._novel_dir_input).resolve()
            if not nd.exists():
                nd = (PROJECT_ROOT / "novels" / self._novel_dir_input).resolve()
            if nd.exists():
                state = _load_state(nd)
                if state:
                    self._novel_dir = nd
                    self._state = state
                    self._init_store_registry(state["db_path"])
                    return

        # Scan novels/ directory
        dirs = _find_novel_dirs("novels")
        if len(dirs) == 1:
            nd = dirs[0]
            state = _load_state(nd)
            if state:
                self._novel_dir = nd
                self._state = state
                self._init_store_registry(state["db_path"])
                return

        if dirs:
            chat = self.query_one("#chat-history", RichLog)
            chat.write("[bold yellow]发现多个项目:[/]")
            for d in dirs:
                st = _load_state(d)
                if st:
                    pid = st.get("project_id", "?")
                    chat.write(f"  {d.name} → {pid}")

        chat = self.query_one("#chat-history", RichLog)
        chat.write("[bold yellow]请选择项目:[/]")
        chat.write("  [cyan]/open <项目名>[/]  如: /open dragon_king")
        self.query_one("#chat-input", Input).placeholder = "输入 /open <项目名> 选择项目..."

    def _init_store_registry(self, db_path: str) -> None:
        db = Database(db_path)
        db.initialize()
        self._store_registry = SessionRuntimeStoreRegistry(db)

    def _init_brain(self) -> None:
        if not self._store_registry or not self._state or not self._novel_dir:
            self._brain = None
            return
        self._brain_callbacks = BrainCallbacks(
            on_phase=self._make_phase_callback(),
            on_beat=self._make_beat_callback(),
            on_chunk=self._make_chunk_callback(),
            on_error=self._make_error_callback(),
        )
        self._brain = create_novel_agent_runtime(
            self._store_registry,
            self._brain_callbacks,
            self._novel_dir,
            self._state["project_id"],
        )

    def _render_project_header(self) -> None:
        header = self.query_one("#project-header", Static)
        if not self._state:
            id_text = "未连接"
            mode_text = ""
        else:
            id_text = self._state.get("project_id", "?")
            interactive_runtime = self._brain.runtime_name if self._brain else "?"
            try:
                role_runtime = get_novel_role_runtime().runtime_name
                writer_model = NovelLLMFactory.get_instance().get_pi_role_connection(
                    "writer"
                ).model
            except Exception:
                role_runtime = "?"
                writer_model = "?"
            mode_text = (
                f"| Editor: [bold cyan]{interactive_runtime}[/] "
                f"| Roles: [bold cyan]{role_runtime}[/] "
                f"| Writer: {writer_model}"
            )
        header.update(
            f"[b]Project:[/b] {id_text}  {mode_text}"
        )

    # ── Callback factories (thread-safe) ──

    def _make_phase_callback(self):
        app = self
        def cb(event: str, name: str, payload: dict[str, Any]) -> None:
            app.call_from_thread(app._on_phase, event, name, payload)
        return cb

    def _make_beat_callback(self):
        app = self
        def cb(event: str, beat_idx: int, payload: dict[str, Any]) -> None:
            app.call_from_thread(app._on_beat, event, beat_idx, payload)
        return cb

    def _make_chunk_callback(self):
        app = self
        def cb(text: str) -> None:
            app.call_from_thread(app._on_chunk, text)
        return cb

    def _make_error_callback(self):
        app = self
        def cb(phase: str, msg: str) -> None:
            app.call_from_thread(app._on_error, phase, msg)
        return cb

    # ── UI update methods (called from main thread via call_from_thread) ──

    def _on_phase(self, event: str, name: str, payload: dict[str, Any]) -> None:
        pd = self._phase_data.get(name)
        if not pd:
            return
        if event == "start":
            pd["status"] = "⟳"
            pd["detail"] = ""
            pd["time"] = ""
        elif event == "end":
            pd["status"] = "✓"
            pd["time"] = f"{payload.get('duration_ms', 0) / 1000:.1f}s"
            if name == "director":
                pd["detail"] = payload.get("character_anchor", "")[:50]
            elif name == "writer":
                pd["detail"] = f"总计 {payload.get('total_chars', 0)} 字"
            elif name == "quality":
                pd["detail"] = f"判决: {payload.get('verdict', '?')}"
            elif name == "continuity":
                pd["detail"] = f"问题: {payload.get('issue_count', 0)}"
        elif event == "error":
            pd["status"] = "✗"
            pd["detail"] = payload.get("message", "")[:50]
        self._refresh_phases()

    def _on_beat(self, event: str, beat_idx: int, payload: dict[str, Any]) -> None:
        pd = self._phase_data.get("writer", {})
        if event == "start":
            pd["status"] = "⟳"
            pd["detail"] = f"Beat {beat_idx}/{payload.get('beat_count', '?')} ..."
        elif event == "end":
            pd["detail"] = f"Beat {beat_idx} ✓ · {payload.get('char_count', 0)}字"
        self._refresh_phases()

    def _on_chunk(self, text: str) -> None:
        self._writer_lines.append(text)
        writer = self.query_one("#writer-output", RichLog)
        writer.write(text)

    def _on_error(self, phase: str, msg: str) -> None:
        pd = self._phase_data.get(phase, {})
        pd["status"] = "✗"
        pd["detail"] = msg[:60]
        self._refresh_phases()
        self.query_one("#chat-history", RichLog).write(f"[bold red]Error ({phase}):[/] {msg}")

    def _refresh_phases(self) -> None:
        self.query_one("#phase-status", Static).update(self._render_phases())

    def _render_phases(self) -> str:
        lines = []
        for p in PHASE_ORDER:
            pd = self._phase_data[p]
            status = pd["status"]
            label = PHASE_LABELS.get(p, p)
            detail = pd["detail"]
            time_str = pd["time"]

            if status == "✓":
                icon = "[bold green]✓[/]"
            elif status == "⟳":
                icon = "[bold yellow]⟳[/]"
            elif status == "✗":
                icon = "[bold red]✗[/]"
            else:
                icon = "[dim]○[/]"

            line = f"{icon} [bold]{label}[/]"
            if time_str:
                line += f" [dim]{time_str}[/]"
            if detail:
                line += f"  [dim]{detail[:40]}[/]"
            lines.append(line)
        return "\n".join(lines)

    # ── Input handling ──

    def action_focus_input(self) -> None:
        self.query_one("#chat-input", Input).focus()

    def action_clear_chat(self) -> None:
        self.query_one("#chat-history", RichLog).clear()
        self._writer_lines.clear()
        self.query_one("#writer-output", RichLog).clear()
        self._init_phase_data()
        self._refresh_phases()

    def action_reset_brain(self) -> None:
        if self._brain:
            self._brain.reset()
        self._init_phase_data()
        self._refresh_phases()
        chat = self.query_one("#chat-history", RichLog)
        chat.write("[dim]Brain context reset.[/]")

    def action_toggle_search(self) -> None:
        if not self._brain:
            return
        if not self._brain.supports_legacy_commands:
            self.query_one("#chat-history", RichLog).write("[dim]受限 Pi 小说 Agent 不提供此命令。[/]")
            return
        state = self._brain.toggle_web_search()
        icon = "🔍 开" if state else "🚫 关"
        self._render_project_header()
        chat = self.query_one("#chat-history", RichLog)
        chat.write(f"[dim]Ctrl+S: 网络搜索 → {icon}[/]")

    def action_cancel_agent(self) -> None:
        if not self._brain or not self._busy:
            return
        asyncio.create_task(asyncio.to_thread(self._brain.abort))
        self.query_one("#chat-history", RichLog).write("[dim]正在请求取消当前 Agent 任务...[/]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        msg = event.value.strip()
        if not msg:
            return
        event.input.value = ""

        chat = self.query_one("#chat-history", RichLog)

        # Handle /commands
        if msg.startswith("/"):
            self._handle_command(msg, chat)
            return

        # Regular chat
        chat.write(f"[bold cyan]You:[/] {msg}")

        self._process_message(msg)

    def _handle_command(self, msg: str, chat: RichLog) -> None:
        parts = msg.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        legacy_only = {
            "/search", "/compress", "/mode", "/dl-server", "/dl-search",
            "/downloads", "/dl-dir",
        }
        if cmd in legacy_only and self._brain and not self._brain.supports_legacy_commands:
            chat.write("[dim]受限 Pi 小说 Agent 不提供此命令。[/]")
            return

        if cmd == "/open":
            nd = PROJECT_ROOT / "novels" / arg
            if not nd.exists():
                chat.write(f"[bold red]项目不存在: novels/{arg}[/]")
                return
            state = _load_state(nd)
            if not state:
                chat.write(f"[bold red]项目未初始化: novels/{arg}（请先 seed）[/]")
                return
            self._novel_dir = nd
            self._state = state
            self._init_store_registry(state["db_path"])
            self._init_brain()
            self._render_project_header()
            self._init_phase_data()
            self._refresh_phases()
            chat.write(f"[bold green]已连接: {arg}[/] (project_id={state.get('project_id', '?')})")
            self._auto_save()

        elif cmd == "/new":
            self._handle_new_command(arg, chat)

        elif cmd == "/status":
            if not self._store_registry:
                chat.write("[bold red]请先 /open <项目名>[/]")
            else:
                self._run_status(chat)

        elif cmd == "/list":
            self._run_list_projects(chat)

        elif cmd == "/search":
            if not self._brain:
                chat.write("[bold red]Brain 未初始化[/]")
                return
            state = self._brain.toggle_web_search()
            icon = "🔍" if state else "🚫"
            chat.write(f"[bold]{icon} 网络搜索: {'开' if state else '关'}[/]  {'(DeepSeek 自动决定是否联网)' if state else ''}")
            self._render_project_header()
            self._auto_save()

        elif cmd == "/compress":
            if not self._brain:
                chat.write("[bold red]Brain 未初始化[/]")
                return
            result = self._brain.compress()
            chat.write(f"[bold green]✓ {result}[/]")

        elif cmd == "/mode":
            if not self._brain:
                chat.write("[bold red]Brain 未初始化[/]")
                return
            parts2 = arg.split()
            mode_name = parts2[0] if parts2 else ""
            if not mode_name:
                chat.write(f"[bold]当前模式: {self._brain.mode}[/]  可用: auto / brainstorm / research")
                chat.write("  /mode brainstorm  切换到创意发散模式")
                chat.write("  /mode research    切换到深度调研模式")
                chat.write("  /mode auto        切换回默认模式")
                return
            result = self._brain.set_mode(mode_name)
            chat.write(f"[bold yellow]{result}[/]")
            chat.write(f"[dim]切换模式会重置对话历史。[/]")
            self._render_project_header()
            self._auto_save()

        elif cmd == "/dl-server":
            if not self._brain:
                chat.write("[bold red]Brain 未初始化[/]")
                return
            if arg:
                self._brain.dl_server_url = arg
                chat.write(f"[bold green]下载器服务 URL 已设为: {arg}[/]")
                self._auto_save()
            else:
                chat.write(f"[bold]下载器服务: {self._brain.dl_server_url}[/]")
                chat.write(f"  用法: /dl-server http://127.0.0.1:18423")
                chat.write(f"  在终端启动: TomatoNovelDownloader --server --host 127.0.0.1 --port 18423")

        elif cmd == "/dl-search":
            if not self._brain:
                chat.write("[bold red]Brain 未初始化[/]")
                return
            if not arg:
                chat.write("[bold red]用法: /dl-search <关键词>[/]")
                return
            chat.write(f"[bold dim]搜索: {arg}...[/]")
            result = self._brain._tool_search_novels(arg)
            chat.write(result)

        elif cmd == "/downloads":
            if not self._brain:
                chat.write("[bold red]Brain 未初始化[/]")
                return
            result = self._brain._tool_list_downloads()
            chat.write(result)

        elif cmd == "/dl-dir":
            if not self._brain:
                chat.write("[bold red]Brain 未初始化[/]")
                return
            if arg:
                self._brain.dl_output_dir = arg
                chat.write(f"[bold green]下载目录已设为: {arg}[/]")
                self._auto_save()
            else:
                chat.write(f"[bold]下载目录: {self._brain.dl_output_dir}[/]")

        elif cmd == "/session":
            parts2 = arg.split(maxsplit=1)
            sub = parts2[0].lower() if parts2 else ""
            arg2 = parts2[1] if len(parts2) > 1 else ""

            if sub == "save":
                name = arg2 or (_DEFAULT_SESSION_NAME if arg2 else _DEFAULT_SESSION_NAME)
                data = self._capture_session_data()
                data["created_at"] = data["updated_at"]
                _save_session(name, data)
                chat.write(f"[bold green]✓ 会话已保存: {name}[/] ({_session_path(name)})")
            elif sub == "load":
                name = arg2 or _DEFAULT_SESSION_NAME
                data = _load_session(name)
                if not data:
                    chat.write(f"[bold red]会话不存在: {name}[/]")
                    return
                chat.write(f"[bold yellow]加载会话: {name}[/]")
                self._apply_session(data, chat)
            elif sub == "list":
                sessions = _list_sessions()
                if not sessions:
                    chat.write("[dim]没有已保存的会话[/]")
                else:
                    chat.write("[bold]已保存的会话:[/]")
                    for s in sessions:
                        nm = s.get("_name", "?")
                        pid = s.get("project_id", "?") or "(无项目)"
                        dt = s.get("updated_at", "?")[:16]
                        marker = " [dim](当前)[/]" if nm == _DEFAULT_SESSION_NAME else ""
                        chat.write(f"  [cyan]{nm}[/] → {pid}  {dt}{marker}")
            elif sub == "delete" or sub == "rm":
                name = arg2
                if not name or name == _DEFAULT_SESSION_NAME:
                    chat.write(f"[bold red]不能删除默认会话 '{_DEFAULT_SESSION_NAME}'[/]")
                    return
                p = _session_path(name)
                if not p.exists():
                    chat.write(f"[bold red]会话不存在: {name}[/]")
                    return
                p.unlink()
                chat.write(f"[bold green]✓ 已删除: {name}[/]")
            else:
                data = self._capture_session_data()
                chat.write("[bold]当前会话:[/]")
                chat.write(f"  项目: {data.get('project_id') or '(无)'}")
                chat.write(f"  模式: {data.get('mode', '?')}")
                chat.write(f"  搜索: {'开' if data.get('web_search') else '关'}")
                chat.write(f"  下载服务: {data.get('dl_server_url', '?')}")
                chat.write(f"  压缩次数: {data.get('compress_count', 0)}")
                chat.write(f"  [dim]/session save <名称>  保存   /session load <名称>  恢复[/]")
                chat.write(f"  [dim]/session list          列表   /session delete <名称>  删除[/]")

        elif cmd == "/help":
            chat.write("[bold]命令列表:[/]")
            chat.write("  /open <项目>  连接已有项目")
            chat.write("  /status       查看项目状态")
            chat.write("  /list         列出所有项目")
            chat.write("  /search       切换网络搜索开关")
            chat.write("  /compress     手动压缩对话上下文")
            chat.write("  /mode [mode]  切换模式 (auto/brainstorm/research)")
            chat.write("  /dl-server [url]  设置下载器服务地址")
            chat.write("  /dl-search <关键词>  搜索平台小说")
            chat.write("  /dl-dir [path]  设置/查看下载目录")
            chat.write("  /downloads     查看已下载小说列表")
            chat.write("  /session [save|load|list|delete]  会话管理")
            chat.write("  /help         显示此帮助")
            chat.write("  Ctrl+L        清屏")
            chat.write("  Ctrl+R        重置 Brain 上下文")
            chat.write("  Ctrl+S        切换网络搜索")
            chat.write("")
            chat.write("[bold]会话管理:[/]")
            chat.write("  /session            查看当前会话状态")
            chat.write("  /session save <名>  保存当前会话")
            chat.write("  /session load <名>  恢复已保存会话")
            chat.write("  /session list       列出所有会话")
            chat.write("  /session delete <名> 删除会话")
            chat.write("")
            chat.write("[bold]默认专属编辑流程:[/]")
            chat.write("  直接说剧情、人物或世界观想法，无需输入技能名")
            chat.write("  每条作者消息会先保存到项目本地，再交给编辑")
            chat.write("  编辑会追问、质疑并区分已确定/候选/未决/禁止")
            chat.write("  计划摘要、作者批准和启动写作必须分三个回合完成")

        else:
            chat.write(f"[dim]未知命令: {cmd}。输入 /help 查看帮助。[/]")

    def _run_status(self, chat: RichLog) -> None:
        if not self._store_registry:
            chat.write("[bold red]请先 /open <项目名>[/]")
            return
        pid = self._state["project_id"]
        project = self._store_registry.novel_project_store.load(pid)
        if not project:
            chat.write(f"[red]项目 {pid} 未找到[/]")
            return

        chat.write(f"[bold]{project.title}[/] ({pid}) | {project.genre} | {project.status}")
        plans = self._store_registry.novel_chapter_plan_store.list_by_project(pid)
        for p in plans:
            chapter_id = p.chapter_id or f"ch-{pid}-{p.chapter_index}"
            draft = self._store_registry.novel_chapter_draft_store.load_latest(chapter_id)
            icon = "✓" if (draft and draft.status == "accepted") else "○"
            char_cnt = draft.char_count if draft else 0
            chat.write(f"  [{icon}] Ch{p.chapter_index}: {p.title} ({char_cnt}字)")

    def _handle_new_command(self, arg: str, chat: RichLog) -> None:
        """Create a new project from a concept. Syntax: /new <project_name> <concept>"""
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            chat.write("[bold red]用法: /new <项目名> <一句话思路>[/]")
            chat.write("  例如: /new my_story 修仙少年重生都市，逆天改命")
            return

        name = parts[0].strip()
        concept = parts[1].strip()
        if not name or not concept:
            chat.write("[bold red]项目名和思路不能为空[/]")
            return

        nd = PROJECT_ROOT / "novels" / name
        if nd.exists():
            chat.write(f"[bold red]项目已存在: novels/{name}[/]")
            return

        nd.mkdir(parents=True, exist_ok=True)
        db_path = str((nd / "novel.db").resolve())
        chat.write(f"[bold yellow]创建项目: {name}[/]")
        chat.write(f"[dim]数据库: {db_path}[/]")
        chat.write(f"[dim]正在调用 AI 规划大纲（约 30-60 秒）...[/]")

        db = Database(db_path)
        db.initialize()
        registry = SessionRuntimeStoreRegistry(db)

        try:
            from awp_rp_runtime_v3.runtime.novel_planner_adapter import NovelPlannerAdapter
            planner = NovelPlannerAdapter(registry)
            plan = planner.plan_novel(concept=concept, title=name)
            project_id = f"novel-{plan.title}"

            # Save .novel_cli.json
            state = {"project_id": project_id, "db_path": db_path}
            (nd / ".novel_cli.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

            # Auto-connect
            self._novel_dir = nd
            self._state = state
            self._store_registry = registry
            self._init_brain()
            self._render_project_header()
            self._init_phase_data()
            self._refresh_phases()
            chat.write(f"[bold green]✓ 项目创建完成: {plan.title}[/] ({project_id})")
            chat.write(f"  题材: {plan.genre} | 平台: {plan.target_platform}")
            chat.write(f"  卷数: {len(plan.volumes)} | 核心情感: {plan.core_emotion}")
            chat.write("  [dim]现在可以直接告诉编辑：你想让这一章发生什么，以及绝不能发生什么。[/]")
            self._auto_save()
        except Exception as e:
            import traceback
            chat.write(f"[bold red]创建失败: {e}[/]")
            chat.write(f"[dim]{traceback.format_exc()[-300:]}[/]")

    def _run_list_projects(self, chat: RichLog) -> None:
        dirs = _find_novel_dirs("novels")
        if not dirs:
            chat.write("[dim]novels/ 目录下没有已初始化的项目。请先在 CLI 运行 init + seed。[/]")
            return
        chat.write("[bold]可用项目:[/]")
        for d in dirs:
            st = _load_state(d)
            if st:
                pid = st.get("project_id", "?")
                chat.write(f"  [cyan]{d.name}[/] → {pid}")

    # ── Message processing ──

    def _capture_session_data(self) -> dict:
        """Gather current TUI state into a serializable dict."""
        return {
            "project_id": self._state.get("project_id") if self._state else None,
            "project_dir": str(self._novel_dir) if self._novel_dir else None,
            "db_path": self._state.get("db_path") if self._state else None,
            "mode": self._brain.mode if self._brain else "auto",
            "web_search": self._brain.web_search_enabled if self._brain else True,
            "dl_server_url": self._brain.dl_server_url if self._brain else "http://127.0.0.1:18423",
            "dl_output_dir": self._brain.dl_output_dir if self._brain else "",
            "compress_count": self._brain._compress_count if self._brain else 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _try_restore_session(self) -> None:
        """Auto-restore last session on startup if no project is connected."""
        if self._store_registry:
            return  # Already connected via CLI arg or single project

        data = _load_session(_DEFAULT_SESSION_NAME)
        if not data:
            return

        project_dir = data.get("project_dir")
        if not project_dir:
            return

        nd = Path(project_dir)
        if not nd.exists():
            return

        state = _load_state(nd)
        if not state:
            return

        # Restore project connection
        self._novel_dir = nd
        self._state = state
        self._init_store_registry(state["db_path"])
        self._init_brain()

        # Restore settings
        if self._brain and self._brain.supports_legacy_commands:
            mode = data.get("mode", "auto")
            if mode != "auto":
                self._brain.set_mode(mode)
            ws = data.get("web_search", True)
            if not ws:
                self._brain.disable_web_search()
            dl = data.get("dl_server_url")
            if dl:
                self._brain.dl_server_url = dl
            dl_dir = data.get("dl_output_dir")
            if dl_dir:
                self._brain.dl_output_dir = dl_dir

        self._render_project_header()
        chat = self.query_one("#chat-history", RichLog)
        pid = data.get("project_id", "?")
        last = data.get("updated_at", "?")[:16]
        chat.write(f"[dim]已恢复上次会话: {pid} ({last})[/]")

    def _auto_save(self) -> None:
        """Save current session to 'last'. Also create a named backup."""
        data = self._capture_session_data()
        _save_session(_DEFAULT_SESSION_NAME, data)
        # If a project is connected, also save a named session
        pid = data.get("project_id")
        if pid:
            _save_session(pid, data)

    def _apply_session(self, data: dict, chat: RichLog) -> None:
        """Apply saved session data to current TUI state."""
        project_dir = data.get("project_dir")
        if project_dir:
            nd = Path(project_dir)
            if nd.exists():
                state = _load_state(nd)
                if state:
                    self._novel_dir = nd
                    self._state = state
                    self._init_store_registry(state["db_path"])
                    self._init_brain()
                    self._init_phase_data()
                    self._refresh_phases()
                    chat.write(f"[bold green]✓ 已连接: {data.get('project_id', '?')}[/]")

        if self._brain and self._brain.supports_legacy_commands:
            mode = data.get("mode", "auto")
            if mode != "auto":
                self._brain.set_mode(mode)
            ws = data.get("web_search", True)
            if not ws:
                self._brain.disable_web_search()
            dl = data.get("dl_server_url")
            if dl:
                self._brain.dl_server_url = dl
            dl_dir = data.get("dl_output_dir")
            if dl_dir:
                self._brain.dl_output_dir = dl_dir

        self._render_project_header()
        chat.write(f"[dim]会话设置已应用。[/]")

    def _process_message(self, msg: str) -> None:
        if self._busy:
            self.query_one("#chat-history", RichLog).write("[dim]正在执行上一任务，请稍候...[/]")
            return
        self._busy = True
        asyncio.create_task(self._run_brain(msg))

    async def _run_brain(self, msg: str) -> None:
        chat = self.query_one("#chat-history", RichLog)
        try:
            self._init_phase_data()
            self._refresh_phases()
            self._writer_lines.clear()
            self.query_one("#writer-output", RichLog).clear()

            response = await asyncio.to_thread(self._brain.handle_message, msg)

            chat.write(f"[bold yellow]Brain:[/] {response}")
        except Exception as exc:
            chat.write(f"[bold red]Error:[/] {exc}")
        finally:
            self._busy = False

    # ── On shutdown save ──

    def on_unmount(self) -> None:
        self._auto_save()
        if self._brain:
            self._brain.close()


# ── CLI entry ──

def main():
    novel_dir = sys.argv[1] if len(sys.argv) > 1 else None
    app = NovelTui(novel_dir=novel_dir)
    app.run()


if __name__ == "__main__":
    main()
