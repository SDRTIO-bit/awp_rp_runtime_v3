#!/usr/bin/env python3
"""AWP Novel TUI — Textual-powered terminal dashboard for novel pipeline.

左右分屏：左侧管线实时进度，右侧 cc 风格聊天面板（NovelBrain）。

用法:
  python scripts/awp_tui.py [novel_dir]
  python scripts/awp_tui.py novels/dragon_king
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, RichLog, Input
from textual import events

from awp_rp_runtime_v3.runtime.novel_brain import NovelBrain, BrainCallbacks
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
        overflow-y: scroll;
    }

    #chat-history {
        height: 1fr;
        border: solid $panel-lighten-1;
        margin: 1;
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
    ]

    def __init__(self, novel_dir: str | None = None):
        super().__init__()
        self._novel_dir_input = novel_dir
        self._novel_dir: Path | None = None
        self._state: dict | None = None
        self._store_registry: SessionRuntimeStoreRegistry | None = None
        self._brain: NovelBrain | None = None
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
                yield RichLog(id="writer-output", highlight=True, markup=True)
            with Vertical(id="right-panel"):
                yield RichLog(id="chat-history", highlight=True, markup=True)
                yield Input(id="chat-input", placeholder="输入指令... (Enter 发送, Esc 切换焦点)")
        yield Footer()

    def on_mount(self) -> None:
        self._setup_headless()
        self._init_brain()
        if self._state:
            self._render_project_header()

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
        novels_root = str(PROJECT_ROOT / "novels")
        self._brain_callbacks = BrainCallbacks(
            on_phase=self._make_phase_callback(),
            on_beat=self._make_beat_callback(),
            on_chunk=self._make_chunk_callback(),
            on_error=self._make_error_callback(),
        )
        self._brain = NovelBrain(
            self._store_registry,
            callbacks=self._brain_callbacks,
            db_path=self._state.get("db_path", "") if self._state else "",
            novels_root=novels_root,
        )

    def _render_project_header(self) -> None:
        header = self.query_one("#project-header", Static)
        pid = self._state.get("project_id", "?")
        header.update(f"[b]Project:[/b] {pid}\n[dim]{self._novel_dir}[/]")

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

        elif cmd == "/new":
            self._handle_new_command(arg, chat)

        elif cmd == "/status":
            if not self._store_registry:
                chat.write("[bold red]请先 /open <项目名>[/]")
            else:
                self._run_status(chat)

        elif cmd == "/list":
            self._run_list_projects(chat)

        elif cmd == "/help":
            chat.write("[bold]命令列表:[/]")
            chat.write("  /new <项目名> <思路>  新建项目（AI 自动大纲）")
            chat.write("  /open <项目>  连接已有项目")
            chat.write("  /status      查看项目状态")
            chat.write("  /list        列出所有项目")
            chat.write("  /help        显示此帮助")
            chat.write("  Ctrl+L       清屏")
            chat.write("  Ctrl+R       重置 Brain 上下文")
            chat.write("")
            chat.write("[bold]对话示例:[/]")
            chat.write("  帮我把第3章写了")
            chat.write("  第3章质量怎么样？")
            chat.write("  继续写第4-6章")
            chat.write("  帮我读一下第5章")

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
            chat.write(f"  [dim]现在可以对话：帮我把第1章写了[/]")
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
        pass


# ── CLI entry ──

def main():
    novel_dir = sys.argv[1] if len(sys.argv) > 1 else None
    app = NovelTui(novel_dir=novel_dir)
    app.run()


if __name__ == "__main__":
    main()
