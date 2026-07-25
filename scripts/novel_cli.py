"""Novel CLI — 文件驱动的小说管线命令行工具.

通过文件目录定义小说项目，CLI 读取后注入管线，全程数据可提取。

用法:
  python scripts/novel_cli.py init <dir>                      # 初始化小说目录（生成模板文件）
  python scripts/novel_cli.py seed <dir>                      # 读取文件 → 写入DB（project, chars, volume, ledger）
  python scripts/novel_cli.py plan <dir> <chapter> [--task]   # 规划章节（Architect）
  python scripts/novel_cli.py write <dir> <chapter>           # 生成章节（Director + Writer + Quality）
  python scripts/novel_cli.py batch <dir> <start> <end>       # 批量生成
  python scripts/novel_cli.py export <dir>                    # 导出全部数据（章节、账本、角色状态）
  python scripts/novel_cli.py status <dir>                    # 查看项目状态
  python scripts/novel_cli.py promote-state <dir> <character_id> --source <item_id> --patch '{"injured": true}'  # 人工提升角色状态
  python scripts/novel_cli.py run <dir> <start> <end>         # 一键 seed → plan → batch → export
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from awp_rp_runtime_v3.storage.sqlite.database import Database
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter, CharacterRelationship
from awp_rp_runtime_v3.contracts.novel_volume import VolumePlan
from awp_rp_runtime_v3.contracts.novel_ledger import LedgerItem
from awp_rp_runtime_v3.contracts.novel_profile import (
    PROFILE_CONFIG_KEY,
    default_autonomous_profile,
    load_autonomous_profile,
)
from awp_rp_runtime_v3.runtime.novel_trace import NovelStreamCallbacks
from awp_rp_runtime_v3.runtime.novel_llm_factory import NovelLLMFactory
from awp_rp_runtime_v3.runtime.novel_role_runtime import get_novel_role_runtime

GREEN = "\033[92m"
RED = "\033[91m"
DIM = "\033[2m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR_LINE = "\033[2K"
CURSOR_UP = "\033[1A"

_RICH_AVAILABLE = False
try:
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.layout import Layout
    from rich.console import Console
    from rich import box
    _RICH_AVAILABLE = True
except ImportError:
    pass


def assert_pi_role_runtime_ready(project_root: Path = PROJECT_ROOT) -> None:
    """Fail before generation when the embedded Pi role host is incomplete."""

    if os.environ.get("NOVEL_AGENT_RUNTIME", "pi").lower() != "pi":
        return
    harness_root = Path(project_root) / "agent_harness"
    dependency = (
        harness_root
        / "node_modules"
        / "@earendil-works"
        / "pi-coding-agent"
        / "package.json"
    )
    if not dependency.exists():
        raise RuntimeError(
            "Pi novel role dependencies are missing. Run: "
            f"cd {harness_root} && npm ci"
        )
    if not shutil.which("node"):
        raise RuntimeError("Node.js >=22.19 is required for Pi novel role agents")
    host = harness_root / "src" / "novel_role_host.mjs"
    if not host.exists():
        raise RuntimeError(f"Pi novel role host is missing: {host}")


def _writer_role_connection():
    return NovelLLMFactory.get_instance().get_pi_role_connection("writer")


def _print_agent_runtime_banner() -> None:
    runtime = get_novel_role_runtime()
    connection = _writer_role_connection()
    label = "Pi role agents" if runtime.runtime_name == "PiRoles" else runtime.runtime_name
    print(f"Agent Runtime: {label}")
    print(f"Provider/Model: {connection.provider} / {connection.model}")


def _prepare_agent_runtime() -> None:
    assert_pi_role_runtime_ready(PROJECT_ROOT)
    _print_agent_runtime_banner()

TEMPLATE_NOVEL_JSON = """{
  "project": {
    "id": "my-novel",
    "title": "我的小说",
    "genre": "都市悬疑",
    "core_emotion": "压抑→怀疑→执着→释然",
    "one_sentence_pitch": "一句话简介",
    "target_reader": "22-35岁悬疑爱好者",
    "target_platform": "番茄长篇",
    "config": {
      "autonomous_profile": {
        "schema_id": "awp.novel.writing-profile.v1",
        "schema_version": 1,
        "mode": "novel",
        "name": "default-novel-autonomy",
        "narrative": {},
        "world": {},
        "history": {},
        "scene": {},
        "agent_contracts": {}
      }
    }
  },
  "volume": {
    "index": 1,
    "title": "第一卷",
    "chapter_start": 1,
    "chapter_end": 10,
    "objective": "本卷读者应该感受到什么",
    "key_results": ["指标1", "指标2"],
    "core_conflict": "核心冲突",
    "emotional_arc": "情绪弧线",
    "major_payoffs": ["高潮1", "高潮2"]
  },
  "characters": [
    {
      "character_id": "char-01",
      "name": "主角名",
      "aliases": [],
      "role": "protagonist",
      "personality": "性格描述",
      "voice_style": "语言风格",
      "pov_eligible": true,
      "core_motivation": "核心动机",
      "weakness": "性格弱点",
      "current_state": {"location": "某地", "emotion": "平静"},
      "arc_phase": "setup",
      "first_appearance": 1,
      "relationships": []
    }
  ]
}
"""

TEMPLATE_WORLD_MD = """# 世界观设定

## 时代背景
（请在此处描述故事的时代、地点、社会背景）

## 核心设定
（请在此处写世界规则、特殊设定、力量体系等）

## 关键地点
- 地点A: 描述
- 地点B: 描述

## 势力/组织
- 势力A: 描述
"""

TEMPLATE_OUTLINE_MD = """# 章节大纲

## 第1章
- 定位: setup
- 目标情绪: 好奇心
- 开篇钩子: （一句话）
- 内容概要: （3-5句话）
- 结尾钩子: （留给下一章的悬念）
- 任务描述: （本章要完成的故事推进）

## 第2章
- 定位: progression
- 目标情绪: 紧张感
- 开篇钩子:
- 内容概要:
- 结尾钩子:
- 任务描述:

## 第3章
- 定位: progression
- 目标情绪: 怀疑
- 开篇钩子:
- 内容概要:
- 结尾钩子:
- 任务描述:
"""


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_quality_report(output_dir: Path, chapter: int, draft) -> Path:
    """Persist non-blocking quality annotations beside a generated chapter."""
    report_file = output_dir / f"chapter_{chapter:02d}.quality.json"
    report_file.write_text(
        json.dumps(
            {
                "draft_id": draft.draft_id,
                "chapter_id": draft.chapter_id,
                "revision": draft.revision,
                "status": draft.status,
                "quality_decision_id": draft.quality_decision_id,
                "annotations": list(draft.quality_annotations),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_file


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_plan_guidance(novel_dir: Path, chapter: int, cli_guidance: str = "") -> str:
    """Load broad project guidance for the context-heavy Plan Agent."""
    parts = []
    story_bible = _read_text(novel_dir / "story_bible.md")
    if story_bible:
        parts.append("【项目故事圣经 — 优先于旧角色设定】\n" + story_bible.strip())
    guidance_file = novel_dir / "guidance" / f"chapter_{chapter:02d}.md"
    file_content = _read_text(guidance_file)
    if file_content:
        parts.append(file_content.strip())
    if cli_guidance:
        parts.append(cli_guidance.strip())
    return "\n\n".join(parts)


def _load_writer_guidance(novel_dir: Path, chapter: int, cli_guidance: str = "") -> str:
    """Load only chapter-local guidance for the context-light Writer Agent."""
    parts = []
    guidance_file = novel_dir / "guidance" / f"chapter_{chapter:02d}.md"
    file_content = _read_text(guidance_file)
    if file_content:
        parts.append(file_content.strip())
    if cli_guidance:
        parts.append(cli_guidance.strip())
    return "\n\n".join(parts)


# Backward-compatible alias for integrations that imported the old helper.
_load_guidance = _load_plan_guidance


def _parse_outline(md_text: str) -> list[dict]:
    """Parse outline.md into list of chapter briefs."""
    chapters = []
    current = None
    for line in md_text.split("\n"):
        line = line.strip()
        if line.startswith("## 第") and "章" in line:
            if current:
                chapters.append(current)
            current = {"title": line.lstrip("#").strip(), "info": {}}
        elif line.startswith("- ") and current is not None:
            parts = line[2:].split(":", 1)
            if len(parts) == 2:
                current["info"][parts[0].strip()] = parts[1].strip()
    if current:
        chapters.append(current)
    return chapters


def _get_engine(db_path: str, callbacks=None) -> NovelEngine:
    db = Database(db_path)
    db.initialize()
    reg = SessionRuntimeStoreRegistry(db)
    return NovelEngine(reg, callbacks=callbacks)


def _create_stream_callbacks_rich(live_refresh=None):
    console = Console()

    phases_data: dict[str, dict] = {
        "director": {"status": "○", "detail": "", "time": ""},
        "writer": {"status": "○", "detail": "", "time": ""},
        "quality": {"status": "○", "detail": "", "time": ""},
        "continuity": {"status": "○", "detail": "", "time": ""},
        "ledger": {"status": "○", "detail": "", "time": ""},
    }
    phase_order = ["director", "writer", "quality", "continuity", "ledger"]
    writer_text_parts: list[str] = []
    current_chapter = 0
    project_title = ""

    def _mk_layout() -> Layout:
        phase_table = Table(box=box.SIMPLE, show_header=False, expand=True)
        phase_table.add_column("status", width=1)
        phase_table.add_column("phase", width=18)
        phase_table.add_column("time", width=8)
        phase_table.add_column("detail")

        for p in phase_order:
            ph = phases_data[p]
            style = ""
            if ph["status"] == "✓":
                style = "green"
            elif ph["status"] == "⟳":
                style = "bold yellow"
            elif ph["status"] == "✗":
                style = "red"
            phase_table.add_row(
                f"[{style}]{ph['status']}[/{style}]" if style else ph["status"],
                f"[{style}]{p}[/{style}]" if style else p,
                ph["time"],
                Text(ph["detail"][:60], style="dim"),
            )

        header = Panel(
            f"[bold]Novel CLI[/bold] — {project_title} · Chapter {current_chapter}",
            box=box.SIMPLE,
        )
        out_text = Text("".join(writer_text_parts[-2000:]) if writer_text_parts else "")
        layout = Layout()
        layout.split_column(
            Layout(header, name="header", size=3),
            Layout(Panel(phase_table, title="Pipeline", box=box.SIMPLE), name="phases", size=11),
            Layout(Panel(out_text, title="Writer Output", box=box.SIMPLE), name="output"),
        )
        return layout

    layout = _mk_layout()

    def _refresh():
        nonlocal layout
        layout = _mk_layout()

    def on_phase(event: str, name: str, payload: dict):
        nonlocal current_chapter, project_title
        if "ch" in payload:
            current_chapter = payload["ch"]
        if event == "start":
            phases_data[name]["status"] = "⟳"
            phases_data[name]["detail"] = ""
            phases_data[name]["time"] = ""
        elif event == "end":
            phases_data[name]["status"] = "✓"
            phases_data[name]["time"] = f"{payload.get('duration_ms', 0) / 1000:.1f}s"
            if name == "director":
                anchor = payload.get("character_anchor", "")
                beats = payload.get("beat_details", [])
                phases_data[name]["detail"] = f"角色锚: {anchor[:30]}" if anchor else f"Beats: {len(beats)}"
            elif name == "writer":
                phases_data[name]["detail"] = f"总计 {payload.get('total_chars', 0)}字"
            elif name == "quality":
                phases_data[name]["detail"] = f"判决: {payload.get('verdict', '?')}"
            elif name == "continuity":
                phases_data[name]["detail"] = f"问题: {payload.get('issue_count', 0)}"
        elif event == "error":
            phases_data[name]["status"] = "✗"
            phases_data[name]["detail"] = payload.get("message", "")[:60]
        _refresh()
        if live_refresh:
            live_refresh(layout)

    def on_beat(event: str, beat_index: int, payload: dict):
        phases_data["writer"]["status"] = "⟳"
        if event == "start":
            bc = payload.get("beat_count", "?")
            phases_data["writer"]["detail"] = f"Beat {beat_index}/{bc} ..."
        elif event == "end":
            chars = payload.get("char_count", 0)
            dur = payload.get("duration_ms", 0) / 1000
            phases_data["writer"]["detail"] = f"Beat {beat_index} 完成 · {chars}字 · {dur:.1f}s"
        _refresh()
        if live_refresh:
            live_refresh(layout)

    def on_chunk(text: str):
        writer_text_parts.append(text)
        _refresh()
        if live_refresh:
            live_refresh(layout)

    def on_error(phase: str, message: str):
        phases_data[phase]["status"] = "✗"
        phases_data[phase]["detail"] = message[:60]
        _refresh()
        if live_refresh:
            live_refresh(layout)

    return NovelStreamCallbacks(on_phase=on_phase, on_beat=on_beat,
                                on_chunk=on_chunk, on_error=on_error), layout


def _create_stream_callbacks_basic():
    """Fallback when Rich is not installed — prints to stdout."""
    chapter = 0

    def on_phase(event: str, name: str, payload: dict):
        nonlocal chapter
        if "ch" in payload:
            chapter = payload["ch"]
        if event == "start":
            thinking = payload.get("thinking", "")
            t_tag = f" ({thinking})" if thinking else ""
            print(f"{BOLD}[{name}]{RESET}{t_tag} {DIM}...{RESET}", flush=True)
        elif event == "end":
            ms = payload.get("duration_ms", 0)
            dur = f"{ms / 1000:.1f}s"
            print(f"{CLEAR_LINE}{GREEN}✓{RESET} {name}  {dur}")
            if name == "director":
                anchor = payload.get("character_anchor", "")
                if anchor:
                    print(f"  {DIM}角色锚: {anchor[:80]}{RESET}")
                for b in payload.get("beat_details", []):
                    print(f"  {DIM}├ Beat: {b.get('name', '?')}{RESET}")
            elif name == "quality":
                v = payload.get("verdict", "?")
                c = GREEN if v == "accept" else RED
                print(f"  {c}判决: {v}{RESET}")
            elif name == "writer":
                print(f"  {DIM}总字数: {payload.get('total_chars', 0)}{RESET}")

    def on_beat(event: str, beat_index: int, payload: dict):
        if event == "start":
            bc = payload.get("beat_count", "?")
            desc = payload.get("description", "")[:60]
            print(f"\n{CYAN}▸ Beat {beat_index}/{bc}{RESET} {DIM}{desc}{RESET}", flush=True)
        elif event == "end":
            dur = payload.get("duration_ms", 0) / 1000
            chars = payload.get("char_count", 0)
            print(f"  {GREEN}✓{RESET} {chars}字 · {dur:.1f}s")

    def on_chunk(text: str):
        sys.stdout.write(text)
        sys.stdout.flush()

    def on_error(phase: str, message: str):
        print(f"{RED}✗ {phase}: {message}{RESET}")

    return NovelStreamCallbacks(
        on_phase=on_phase,
        on_beat=on_beat,
        on_chunk=on_chunk,
        on_error=on_error,
    )


# ============================================================
# Commands
# ============================================================

def cmd_init(args: argparse.Namespace) -> None:
    """Scaffold a novel directory with template files."""
    novel_dir = Path(args.dir).resolve()

    if novel_dir.exists() and any(novel_dir.iterdir()):
        print(f"{RED}目录非空: {novel_dir}{RESET}")
        return

    _ensure_dir(novel_dir)
    _ensure_dir(novel_dir / "output")

    project_template = json.loads(TEMPLATE_NOVEL_JSON)
    project_template["project"]["config"][PROFILE_CONFIG_KEY] = (
        default_autonomous_profile().model_dump(mode="json")
    )
    (novel_dir / "project.json").write_text(
        json.dumps(project_template, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (novel_dir / "world.md").write_text(TEMPLATE_WORLD_MD.strip(), encoding="utf-8")
    (novel_dir / "outline.md").write_text(TEMPLATE_OUTLINE_MD.strip(), encoding="utf-8")

    print(f"{GREEN}小说目录已初始化: {novel_dir}{RESET}")
    print(f"  project.json  — 项目元数据 + 人物设定 + 卷计划")
    print(f"  world.md      — 世界观设定")
    print(f"  outline.md    — 章节大纲")
    print(f"  output/       — 生成章节输出目录")
    print(f"\n{YELLOW}请编辑以上文件后运行: python scripts/novel_cli.py seed {novel_dir}{RESET}")


def cmd_seed(args: argparse.Namespace) -> None:
    """Read novel files and seed into the database."""
    novel_dir = Path(args.dir).resolve()
    meta = _read_json(novel_dir / "project.json")

    db_path = str(novel_dir / "novel.db")
    if getattr(args, "db", None):
        db_path = args.db

    engine = _get_engine(db_path)
    project = meta["project"]
    pid = project["id"]
    project_config = dict(project.get("config", {}) or {})
    profile = load_autonomous_profile(project_config)
    project_config[PROFILE_CONFIG_KEY] = profile.model_dump(mode="json")
    project_config["novel_dir"] = str(novel_dir)

    # 1. Create project
    engine._registry.novel_project_store.create(NovelProject(
        project_id=pid,
        title=project.get("title", ""),
        genre=project.get("genre", ""),
        core_emotion=project.get("core_emotion", ""),
        one_sentence_pitch=project.get("one_sentence_pitch", ""),
        target_reader=project.get("target_reader", ""),
        target_platform=project.get("target_platform", ""),
        config=project_config,
        status="writing",
    ))
    print(f"{GREEN}项目: {project['title']} ({pid}){RESET}")

    # 2. Create characters
    for c in meta.get("characters", []):
        rels = []
        for r in c.get("relationships", []):
            rels.append(CharacterRelationship(
                target_character_id=r.get("target_character_id", ""),
                target_name=r.get("target_name", r.get("target_character_id", "")),
                relation_type=r.get("relation_type", ""),
                description=r.get("description", ""),
                tension=r.get("tension", "none"),
            ))
        ch = NovelCharacter(
            character_id=c["character_id"],
            project_id=pid,
            name=c.get("name", ""),
            aliases=tuple(c.get("aliases", [])),
            role=c.get("role", "supporting"),
            personality=c.get("personality", ""),
            voice_style=c.get("voice_style", ""),
            pov_eligible=c.get("pov_eligible", False),
            core_motivation=c.get("core_motivation", ""),
            weakness=c.get("weakness", ""),
            current_state=c.get("current_state", {}),
            arc_phase=c.get("arc_phase", "setup"),
            first_appearance=c.get("first_appearance", 0),
            relationships=tuple(rels),
        )
        engine._registry.novel_character_store.save(ch)
        print(f"  角色: {ch.name} [{ch.role}]")

    # 3. Create volume plan
    vol = meta.get("volume", {})
    if vol:
        volume_id = f"vol-{pid}-{vol.get('index', 1)}"
        vp = VolumePlan(
            volume_id=volume_id,
            project_id=pid,
            index=vol.get("index", 1),
            title=vol.get("title", ""),
            chapter_start=vol.get("chapter_start", 1),
            chapter_end=vol.get("chapter_end", 1),
            chapter_count=vol.get("chapter_end", 1) - vol.get("chapter_start", 1) + 1,
            objective=vol.get("objective", ""),
            key_results=tuple(vol.get("key_results", [])),
            core_conflict=vol.get("core_conflict", ""),
            emotional_arc=vol.get("emotional_arc", ""),
            major_payoffs=tuple(vol.get("major_payoffs", [])),
            foreshadowing_plan=tuple(vol.get("foreshadowing_plan", [])),
        )
        engine._registry.novel_volume_store.save(vp)
        print(f"  卷计划: {vp.title} (第{vp.chapter_start}-{vp.chapter_end}章)")

    # 4. Inject world-building as LedgerItem (world_rules)
    world_md = _read_text(novel_dir / "world.md")
    if world_md:
        engine._registry.novel_ledger_store.upsert(LedgerItem(
            item_id=f"ledger-{pid}-world",
            project_id=pid,
            section="world_rules",
            entity="world_rules",
            content=world_md,
            status="active",
            source_chapter=0,
        ))
        print(f"  世界观: 已注入 ({len(world_md)} 字)")

    # 5. Inject outline as LedgerItem
    outline_md = _read_text(novel_dir / "outline.md")
    if outline_md:
        engine._registry.novel_ledger_store.upsert(LedgerItem(
            item_id=f"ledger-{pid}-outline",
            project_id=pid,
            section="world_rules",
            entity="outline",
            content=outline_md,
            status="active",
            source_chapter=0,
        ))
        print(f"  大纲: 已注入 ({len(outline_md)} 字)")

    # Save db path in state file for subsequent commands
    state = {"db_path": db_path, "project_id": pid, "novel_dir": str(novel_dir)}
    (novel_dir / ".novel_cli.json").write_text(json.dumps(state, ensure_ascii=False, indent=2))

    print(f"\n{CYAN}数据已注入数据库: {db_path}{RESET}")
    print(f"{YELLOW}下一步: python scripts/novel_cli.py plan {novel_dir} 1 --task \"...\"{RESET}")


def cmd_profile_init(args: argparse.Namespace) -> None:
    """Explicitly add the autonomy profile required by older projects."""
    novel_dir = Path(args.dir).resolve()
    meta_path = novel_dir / "project.json"
    meta = _read_json(meta_path)
    project = meta.get("project")
    if not isinstance(project, dict):
        raise ValueError("project.json 必须包含 project 对象")
    config = dict(project.get("config", {}) or {})
    if PROFILE_CONFIG_KEY in config:
        print(f"{YELLOW}Profile 已存在，未修改: {meta_path}{RESET}")
        return
    config[PROFILE_CONFIG_KEY] = default_autonomous_profile().model_dump(mode="json")
    project["config"] = config
    meta["project"] = project
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{GREEN}已写入默认 Novel Profile: {meta_path}{RESET}")


def _load_state(novel_dir: Path) -> dict:
    state_file = novel_dir / ".novel_cli.json"
    if not state_file.exists():
        raise FileNotFoundError(f"状态文件不存在: {state_file}。请先运行 'seed' 命令。")
    return json.loads(state_file.read_text(encoding="utf-8"))


def _sync_project_runtime_config(novel_dir: Path, state: dict) -> None:
    """Keep the DB runtime prompt config aligned with project.json.

    Existing projects may have been seeded before prompt overrides or the
    project directory were added. Plan/write commands repair that drift
    without rebuilding story state.
    """
    meta_path = novel_dir / "project.json"
    if not meta_path.exists():
        return
    meta = _read_json(meta_path)
    file_project = meta.get("project", {})
    project_id = state.get("project_id") or file_project.get("id", "")
    if not project_id:
        return
    engine = _get_engine(state["db_path"])
    stored = engine._registry.novel_project_store.load(project_id)
    if stored is None:
        return
    merged = dict(getattr(stored, "config", {}) or {})
    merged.update(dict(file_project.get("config", {}) or {}))
    merged["novel_dir"] = str(novel_dir.resolve())
    if merged != stored.config:
        engine._registry.novel_project_store.update(
            replace(stored, config=merged)
        )


def cmd_plan(args: argparse.Namespace) -> None:
    _prepare_agent_runtime()
    novel_dir = Path(args.dir).resolve()
    state = _load_state(novel_dir)
    _sync_project_runtime_config(novel_dir, state)
    engine = _get_engine(state["db_path"])
    pid = state["project_id"]
    chapter = int(args.chapter)

    outline = _read_text(novel_dir / "outline.md")
    chapters = _parse_outline(outline)
    task = getattr(args, "task", "") or ""
    guidance = _load_plan_guidance(novel_dir, chapter, getattr(args, "guidance", ""))

    # Try to find task_description from outline
    outline_task = ""
    for c in chapters:
        if c.get("title", "").startswith(f"第{chapter}章"):
            outline_task = c.get("info", {}).get("任务描述", "")
            break

    if task:
        final_task = task
    elif outline_task:
        final_task = outline_task
    else:
        final_task = f"第{chapter}章"

    # Append guidance as hard requirements
    if guidance:
        final_task = f"{final_task}\n\n【硬性要求 — 必须执行】\n{guidance}"

    print(f"{DIM}Architect 规划第{chapter}章... (thinking=HIGH){RESET}")
    print(f"{DIM}  任务: {final_task[:200]}...{RESET}" if len(final_task) > 200 else f"{DIM}  任务: {final_task}{RESET}")

    plan = engine.plan_chapter(
        project_id=pid,
        chapter_index=chapter,
        task_description=final_task,
    )

    print(f"{GREEN}第{chapter}章规划完成{RESET}")
    print(f"  标题: {plan.title}")
    print(f"  目标字数: {plan.target_chars} | 定位: {plan.chapter_position}")
    print(f"  目标情绪: {plan.target_emotion}")
    print(f"  开篇钩子: {plan.opening_hook}")
    print(f"  主要内容: {plan.main_payoff}")
    if plan.content_summary:
        cs = plan.content_summary
        print(f"  内容: 起因={cs.cause[:40]}... | 发展={cs.development[:40]}... | 高潮={cs.climax[:40]}...")


def cmd_write(args: argparse.Namespace) -> None:
    _prepare_agent_runtime()
    novel_dir = Path(args.dir).resolve()
    state = _load_state(novel_dir)
    _sync_project_runtime_config(novel_dir, state)
    pid = state["project_id"]
    chapter = int(args.chapter)
    use_stream = getattr(args, "stream", False)
    guidance = _load_writer_guidance(novel_dir, chapter, getattr(args, "guidance", ""))

    if guidance:
        print(f"{DIM}微调引导: {guidance[:100]}...{RESET}" if len(guidance) > 100 else f"{DIM}微调引导: {guidance}{RESET}")

    if use_stream:
        callbacks = _create_stream_callbacks_basic()
        engine = _get_engine(state["db_path"], callbacks=callbacks)

        draft = engine.write_chapter_stream(
            project_id=pid, chapter_index=chapter,
            write_guidance=guidance,
        )

        print(f"\n{GREEN}=== 第{chapter}章: {draft.char_count}字 | {draft.status} ==={RESET}")
        output_dir = _ensure_dir(novel_dir / "output")
        out_file = output_dir / f"chapter_{chapter:02d}.md"
        out_file.write_text(f"# 第{chapter}章\n\n{draft.text}", encoding="utf-8")
        print(f"{DIM}已保存: {out_file}{RESET}")
        print(f"{DIM}质检标注: {_write_quality_report(output_dir, chapter, draft)}{RESET}")
    else:
        engine = _get_engine(state["db_path"])

        print(f"{DIM}Director + Writer 生成第{chapter}章...{RESET}")
        print(f"{DIM}  (thinking=HIGH + MEDIUM, 可能需要几分钟){RESET}")

        draft = engine.write_chapter(project_id=pid, chapter_index=chapter, write_guidance=guidance)

        print(f"\n{GREEN}=== 第{chapter}章: {draft.char_count}字 | {draft.status} ==={RESET}\n")
        print(draft.text)

        output_dir = _ensure_dir(novel_dir / "output")
        out_file = output_dir / f"chapter_{chapter:02d}.md"
        out_file.write_text(f"# 第{chapter}章\n\n{draft.text}", encoding="utf-8")
        print(f"\n{DIM}已保存: {out_file}{RESET}")
        print(f"{DIM}质检标注: {_write_quality_report(output_dir, chapter, draft)}{RESET}")


def cmd_batch(args: argparse.Namespace) -> None:
    _prepare_agent_runtime()
    novel_dir = Path(args.dir).resolve()
    state = _load_state(novel_dir)
    pid = state["project_id"]
    start = int(args.start)
    end = int(args.end)
    use_stream = getattr(args, "stream", False)

    print(f"{CYAN}批量生成: 第{start}-{end}章 @ {pid}{RESET}")
    print(f"{DIM}每章间隔5秒用于限流...{RESET}\n")

    total_chars = 0
    output_dir = _ensure_dir(novel_dir / "output")

    if use_stream:
        for ch_idx in range(start, end + 1):
            if ch_idx > start:
                time.sleep(5)

            callbacks = _create_stream_callbacks_basic()
            engine = _get_engine(state["db_path"], callbacks=callbacks)

            print(f"\n{CYAN}═══ 第{ch_idx}章 ═══{RESET}")

            try:
                draft = engine.write_chapter_stream(
                    project_id=pid, chapter_index=ch_idx,
                )
            except Exception as exc:
                print(f"{RED}第{ch_idx}章失败: {exc}{RESET}")
                continue

            total_chars += draft.char_count
            out_file = output_dir / f"chapter_{ch_idx:02d}.md"
            out_file.write_text(f"# 第{ch_idx}章\n\n{draft.text}", encoding="utf-8")
            status_icon = "✓" if draft.status == "accepted" else "⚠"
            print(f"  {YELLOW}[{status_icon}] 第{ch_idx}章: {draft.char_count:5d}字 | {draft.status:8s} → {out_file.name}{RESET}")
    else:
        engine = _get_engine(state["db_path"])

        def _on_chapter(idx: int, draft) -> None:
            nonlocal total_chars
            total_chars += draft.char_count

            out_file = output_dir / f"chapter_{idx:02d}.md"
            out_file.write_text(f"# 第{idx}章\n\n{draft.text}", encoding="utf-8")

            status_icon = "✓" if draft.status == "accepted" else "⚠"
            print(f"  {YELLOW}[{status_icon}] 第{idx}章: {draft.char_count:5d}字 | {draft.status:8s} → {out_file.name}{RESET}")

        drafts = engine.batch_write(
            project_id=pid,
            chapter_start=start,
            chapter_end=end,
            on_chapter_complete=_on_chapter,
        )

    print(f"\n{GREEN}批量完成: {end - start + 1}章, 总计{total_chars}字{RESET}")
    print(f"{DIM}输出目录: {output_dir}{RESET}")


def cmd_export(args: argparse.Namespace) -> None:
    """Export all DB state back to files."""
    novel_dir = Path(args.dir).resolve()
    state = _load_state(novel_dir)
    engine = _get_engine(state["db_path"])
    pid = state["project_id"]

    export_dir = _ensure_dir(novel_dir / "export")

    # Project
    project = engine._registry.novel_project_store.load(pid)
    if project:
        (export_dir / "project.json").write_text(
            json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    # Characters
    chars = engine._registry.novel_character_store.list_by_project(pid)
    chars_data = [c.to_dict() for c in chars]
    (export_dir / "characters.json").write_text(
        json.dumps(chars_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  角色: {len(chars)}个")

    # Chapter plans
    plans = engine._registry.novel_chapter_plan_store.list_by_project(pid)
    plans_data = [p.to_dict() for p in plans]
    (export_dir / "plans.json").write_text(
        json.dumps(plans_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  章节计划: {len(plans)}个")

    # Chapter drafts
    draft_store = engine._registry.novel_chapter_draft_store
    plans = engine._registry.novel_chapter_plan_store.list_by_project(pid)
    for plan in plans:
            chapter_id = plan.chapter_id or f"ch-{pid}-{plan.chapter_index}"
            draft = draft_store.load_latest(chapter_id)
            if draft is not None and draft.text:
                (export_dir / f"chapter_{plan.chapter_index:02d}.txt").write_text(draft.text, encoding="utf-8")

    # Ledger
    ledger_items = engine._registry.novel_ledger_store.list_by_project(pid)
    ledger_data = [li.to_dict() for li in ledger_items]
    (export_dir / "ledger.json").write_text(
        json.dumps(ledger_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  账本条目: {len(ledger_items)}个")

    print(f"{GREEN}导出完成: {export_dir}{RESET}")


def cmd_status(args: argparse.Namespace) -> None:
    """Show project pipeline status."""
    novel_dir = Path(args.dir).resolve()
    state = _load_state(novel_dir)
    engine = _get_engine(state["db_path"])
    pid = state["project_id"]

    project = engine._registry.novel_project_store.load(pid)
    if not project:
        print(f"{RED}项目不存在: {pid}{RESET}")
        return

    print(f"{CYAN}=== {project.title} ({pid}) ==={RESET}")
    print(f"  类型: {project.genre} | 状态: {project.status}")
    print(f"  一句话: {project.one_sentence_pitch}")

    # Characters
    chars = engine._registry.novel_character_store.list_by_project(pid)
    print(f"\n{GREEN}角色 ({len(chars)}):{RESET}")
    for c in chars:
        st = c.current_state
        loc = st.get("location", "?") if isinstance(st, dict) else "?"
        emo = st.get("emotion", "?") if isinstance(st, dict) else "?"
        print(f"  [{c.role:13s}] {c.name:10s} | {loc} | {emo} | arc={c.arc_phase}")

    # Volume
    volumes = engine._registry.novel_volume_store.list_by_project(pid)
    print(f"\n{GREEN}卷计划 ({len(volumes)}):{RESET}")
    for v in volumes:
        print(f"  {v.title}: 第{v.chapter_start}-{v.chapter_end}章 | {v.core_conflict[:40]}")

    # Chapters
    plans = engine._registry.novel_chapter_plan_store.list_by_project(pid)
    draft_store = engine._registry.novel_chapter_draft_store
    print(f"\n{GREEN}章节状态:{RESET}")
    for p in plans:
        chapter_id = p.chapter_id or f"ch-{pid}-{p.chapter_index}"
        draft = draft_store.load_latest(chapter_id)
        draft_info = f"{draft.char_count}字 | {draft.status}" if draft else "未生成"
        status_icon = "✓" if (draft and draft.status == "accepted") else "○"
        print(f"  [{status_icon}] 第{p.chapter_index:2d}章: {p.title:20s} | {p.chapter_position:15s} | {draft_info}")

    # Ledger
    ledger = engine._registry.novel_ledger_store.list_by_project(pid)
    sections = {}
    for li in ledger:
        sections.setdefault(li.section, 0)
        sections[li.section] += 1
    print(f"\n{GREEN}账本 ({len(ledger)}):{RESET}")
    for s, count in sections.items():
        print(f"  {s}: {count}条")


def cmd_run(args: argparse.Namespace) -> None:
    """一键: seed → batch → export"""
    novel_dir = Path(args.dir).resolve()
    start = int(args.start)
    end = int(args.end)

    # Check if already seeded
    state_file = novel_dir / ".novel_cli.json"
    if not state_file.exists():
        print(f"{DIM}Step 1/3: 注入数据...{RESET}")
        cmd_seed(args)
    else:
        print(f"{DIM}Step 1/3: 数据已注入 (跳过){RESET}")

    print(f"\n{DIM}Step 2/3: 批量生成第{start}-{end}章...{RESET}")
    cmd_batch(args)

    print(f"\n{DIM}Step 3/3: 导出数据...{RESET}")
    cmd_export(args)

    print(f"\n{GREEN}全部完成!{RESET}")


POLISH_PROMPT = """你现在是一位经验丰富的起点/轻小说金牌主编。你的任务是对我提供的初稿进行"去AI味"的深度精修。
你的核心目标是：增加文本的呼吸感、留白和网感，消除机械的生成痕迹。

请严格遵守以下"四删三改"原则进行精修：

一、 必须删除的内容（四删）

1. 删除"说明书式"动作堆叠：不要连续使用"她皱眉。她咬唇。她深吸一口气"这种机械切片。将微表情融入台词或单一核心动作中。

2. 删除过度解释的旁白：如果角色的动作和台词已经表现了某种情绪（如紧张、愤怒），绝对禁止在后面紧跟一句旁白来解释含义。把阅读理解的权利还给读者。

3. 删除强行升华的抽象总结：绝对禁止在段落或章节结尾使用抽象总结句。用一个具体的动作、一件物品或一句锋利的对白收尾。

4. 删除毫无交互的环境打卡：不要为了写景而写景。只保留与角色当前行为、情绪直接互动的环境细节。

二、 必须调整的结构（三改）

1. 压缩开场与垃圾时间：删减不必要的过渡段落。让场景切换像电影剪辑一样干脆。

2. 合并短句，打乱句式节奏：消除连续的"主谓宾"短句轰炸。多用从句、长短句结合，加入人类口语化的语气词和吐槽。

3. 克制配角的功能性：不要让配角像拥有上帝视角的AI一样说话。点到为止，只需提供一点反常的动作或半句话。

三、 视角红线（不可违背）

必须保持主角陈默的第三人称有限视角。严禁保留或生成陈默离开后的场景。严禁揭示其他角色未被陈默观察到的内心活动。严禁上帝视角旁白。

四、 执行要求

请在保持原剧情走向、核心对白、人物关系和主角视角不变的前提下，根据以上原则输出精修后的文本。要求文字干练、潜台词丰富、具有人类作者的松弛感。直接输出精修后的文本，不要输出任何分析或注释。"""


def _call_llm_direct(
    system_prompt: str,
    user_prompt: str,
    model: str = "",
) -> str:
    """Make a direct LLM call reusing configured env vars."""
    from openai import OpenAI

    base_url = os.environ.get(
        "NOVEL_LLM_BASE_URL",
        "https://api.deepseek.com/v1",
    )
    api_key_env = (
        os.environ.get("NOVEL_LLM_API_KEY_ENV", "OPENCODE_API_KEY")
    )
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    model_name = model or os.environ.get("NOVEL_LLM_MODEL_WRITER", "deepseek-v4-pro")

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=8000,
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""


def cmd_polish(args: argparse.Namespace) -> None:
    """Polish a generated chapter using the '四删三改' post-processing filter."""
    novel_dir = Path(args.dir).resolve()
    chapter = int(args.chapter)
    output_file = novel_dir / "output" / f"chapter_{chapter:02d}.md"

    if not output_file.exists():
        print(f"{RED}章节文件不存在: {output_file}{RESET}")
        return

    original = output_file.read_text(encoding="utf-8")
    print(f"{DIM}读取: {output_file} ({len(original)}字){RESET}")

    # Strip markdown heading for cleaner processing
    text_lines = original.split("\n")
    if text_lines and text_lines[0].startswith("# "):
        text_lines = text_lines[1:]
    text_content = "\n".join(text_lines).strip()

    print(f"{DIM}正在调用 {_writer_role_connection().provider} / {_writer_role_connection().model} 精修...{RESET}")

    try:
        polished = _call_llm_direct(
            system_prompt=POLISH_PROMPT,
            user_prompt=text_content,
        )
    except Exception as exc:
        print(f"{RED}LLM 调用失败: {exc}{RESET}")
        return

    if not polished.strip():
        print(f"{RED}精修返回空文本{RESET}")
        return

    # Write back
    output_file.write_text(polished.strip(), encoding="utf-8")
    print(f"{GREEN}=== 第{chapter}章精修完成: {len(polished)}字 ==={RESET}")
    print(f"{DIM}已覆盖: {output_file}{RESET}")

    # Show diff stats
    added = len(polished) - len(text_content)
    sign = "+" if added >= 0 else ""
    print(f"{DIM}字数变化: {sign}{added}字{RESET}")


def cmd_promote_state(args: argparse.Namespace) -> None:
    """Manually promote an accepted npc_action into a character's current_state."""
    novel_dir = Path(args.dir).resolve()
    state = _load_state(novel_dir)
    engine = _get_engine(state["db_path"])
    pid = state["project_id"]
    character_id = args.character_id
    source_item_id = args.source

    try:
        patch = json.loads(args.patch)
    except json.JSONDecodeError as e:
        print(f"{RED}patch JSON 解析失败: {e}{RESET}")
        return
    if not isinstance(patch, dict):
        print(f"{RED}patch 必须是 JSON 对象{RESET}")
        return

    forbidden_keys = {"identity", "motivation", "known_fact_ids"}
    bad_keys = [k for k in patch if k in forbidden_keys]
    if bad_keys:
        print(f"{RED}禁止写入的键: {', '.join(bad_keys)}{RESET}")
        return

    character = engine._registry.novel_character_store.load(character_id)
    if character is None or character.project_id != pid:
        print(f"{RED}角色不存在或不属于本项目: {character_id}{RESET}")
        return

    source_item = engine._registry.novel_ledger_store.load(source_item_id)
    if (
        source_item is None
        or source_item.project_id != pid
        or source_item.section != "npc_action"
    ):
        print(f"{RED}source 必须是本项目已接受的 npc_action 账本项: {source_item_id}{RESET}")
        return

    from datetime import datetime, timezone

    new_state = dict(character.current_state)
    new_state.update(patch)
    new_state["promoted_from_item_id"] = source_item_id
    new_state["promoted_at"] = datetime.now(timezone.utc).isoformat()

    updated = replace(character, current_state=new_state, updated_at=new_state["promoted_at"])
    engine._registry.novel_character_store.save(updated)

    print(f"{GREEN}已提升角色状态: {character.name} ({character_id}){RESET}")
    print(f"  来源: {source_item_id}")
    print(f"  写入: {json.dumps(patch, ensure_ascii=False)}")


# ============================================================
# Parser
# ============================================================

PARSER = argparse.ArgumentParser(
    description="Novel CLI — 文件驱动的小说管线命令行工具",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
示例:
  python scripts/novel_cli.py init ./my_novel
  python scripts/novel_cli.py seed ./my_novel
  python scripts/novel_cli.py plan ./my_novel 1 --task "开篇引入主角"
  python scripts/novel_cli.py write ./my_novel 1
  python scripts/novel_cli.py batch ./my_novel 1 3
  python scripts/novel_cli.py run ./my_novel 1 3
  python scripts/novel_cli.py export ./my_novel
  python scripts/novel_cli.py status ./my_novel
""",
)
sub = PARSER.add_subparsers(dest="command", required=True)

# init
p_init = sub.add_parser("init", help="初始化小说目录（生成模板文件）")
p_init.add_argument("dir")

# seed
p_seed = sub.add_parser("seed", help="读取文件 → 写入DB")
p_seed.add_argument("dir")

# profile-init
p_profile_init = sub.add_parser("profile-init", help="为旧项目显式写入默认 Novel Profile")
p_profile_init.add_argument("dir")

# plan
p_plan = sub.add_parser("plan", help="规划章节 (Architect)")
p_plan.add_argument("dir")
p_plan.add_argument("chapter", type=int)
p_plan.add_argument("--task", default="", help="本章任务描述（可选，默认从outline.md读取）")
p_plan.add_argument("--guidance", default="", help="微调引导（补充硬性要求，自动合并 guidance/chapter_NN.md）")

# write
p_write = sub.add_parser("write", help="生成章节 (Director + Writer + Quality)")
p_write.add_argument("dir")
p_write.add_argument("chapter", type=int)
p_write.add_argument("--stream", action="store_true", help="流式输出，实时展示 Agent 执行过程")
p_write.add_argument("--guidance", default="", help="微调引导（补充硬性要求，自动合并 guidance/chapter_NN.md）")

# batch
p_batch = sub.add_parser("batch", help="批量生成章节")
p_batch.add_argument("dir")
p_batch.add_argument("start", type=int)
p_batch.add_argument("end", type=int)
p_batch.add_argument("--stream", action="store_true", help="流式输出，实时展示 Agent 执行过程")

# export
p_export = sub.add_parser("export", help="导出全部数据（章节/账本/角色状态）")
p_export.add_argument("dir")

# status
p_status = sub.add_parser("status", help="查看项目管道状态")
p_status.add_argument("dir")

# promote-state
p_promote_state = sub.add_parser("promote-state", help="人工将已接受的 npc_action 提升为角色 current_state")
p_promote_state.add_argument("dir")
p_promote_state.add_argument("character_id")
p_promote_state.add_argument("--source", required=True, help="来源 npc_action 账本项 ID")
p_promote_state.add_argument("--patch", required=True, help="要合并的 JSON 对象补丁，例如 '{\"injured\": true}'")

# polish (后处理精修)
p_polish = sub.add_parser("polish", help="对已生成的章节进行降AI率精修（四删三改）")
p_polish.add_argument("dir")
p_polish.add_argument("chapter", type=int)

# run (一键)
p_run = sub.add_parser("run", help="一键 seed → plan → batch → export")
p_run.add_argument("dir")
p_run.add_argument("start", type=int)
p_run.add_argument("end", type=int)


def main(argv: list[str]) -> int:
    args = PARSER.parse_args(argv)
    try:
        match args.command:
            case "init":
                cmd_init(args)
            case "seed":
                cmd_seed(args)
            case "profile-init":
                cmd_profile_init(args)
            case "plan":
                cmd_plan(args)
            case "write":
                cmd_write(args)
            case "batch":
                cmd_batch(args)
            case "export":
                cmd_export(args)
            case "status":
                cmd_status(args)
            case "promote-state":
                cmd_promote_state(args)
            case "polish":
                cmd_polish(args)
            case "run":
                cmd_run(args)
            case _:
                PARSER.print_help()
                return 1
    except Exception as exc:
        print(f"{RED}错误: {exc}{RESET}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
