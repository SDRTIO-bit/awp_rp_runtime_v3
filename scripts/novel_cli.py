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
  python scripts/novel_cli.py run <dir> <start> <end>         # 一键 seed → plan → batch → export
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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

GREEN = "\033[92m"
RED = "\033[91m"
DIM = "\033[2m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

TEMPLATE_NOVEL_JSON = """{
  "project": {
    "id": "my-novel",
    "title": "我的小说",
    "genre": "都市悬疑",
    "core_emotion": "压抑→怀疑→执着→释然",
    "one_sentence_pitch": "一句话简介",
    "target_reader": "22-35岁悬疑爱好者",
    "target_platform": "番茄长篇"
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


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


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


def _get_engine(db_path: str) -> NovelEngine:
    db = Database(db_path)
    db.initialize()
    reg = SessionRuntimeStoreRegistry(db)
    return NovelEngine(reg)


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

    (novel_dir / "project.json").write_text(TEMPLATE_NOVEL_JSON.strip(), encoding="utf-8")
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

    # 1. Create project
    engine._registry.novel_project_store.create(NovelProject(
        project_id=pid,
        title=project.get("title", ""),
        genre=project.get("genre", ""),
        core_emotion=project.get("core_emotion", ""),
        one_sentence_pitch=project.get("one_sentence_pitch", ""),
        target_reader=project.get("target_reader", ""),
        target_platform=project.get("target_platform", ""),
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


def _load_state(novel_dir: Path) -> dict:
    state_file = novel_dir / ".novel_cli.json"
    if not state_file.exists():
        raise FileNotFoundError(f"状态文件不存在: {state_file}。请先运行 'seed' 命令。")
    return json.loads(state_file.read_text(encoding="utf-8"))


def cmd_plan(args: argparse.Namespace) -> None:
    novel_dir = Path(args.dir).resolve()
    state = _load_state(novel_dir)
    engine = _get_engine(state["db_path"])
    pid = state["project_id"]
    chapter = int(args.chapter)

    outline = _read_text(novel_dir / "outline.md")
    chapters = _parse_outline(outline)
    task = getattr(args, "task", "") or ""

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

    print(f"{DIM}Architect 规划第{chapter}章... (thinking=HIGH){RESET}")
    print(f"{DIM}  任务: {final_task}{RESET}")

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
    novel_dir = Path(args.dir).resolve()
    state = _load_state(novel_dir)
    engine = _get_engine(state["db_path"])
    pid = state["project_id"]
    chapter = int(args.chapter)

    print(f"{DIM}Director + Writer 生成第{chapter}章...{RESET}")
    print(f"{DIM}  (thinking=HIGH + MEDIUM, 可能需要几分钟){RESET}")

    draft = engine.write_chapter(project_id=pid, chapter_index=chapter)

    print(f"\n{GREEN}=== 第{chapter}章: {draft.char_count}字 | {draft.status} ==={RESET}\n")
    print(draft.text)

    # Save to output/
    output_dir = _ensure_dir(novel_dir / "output")
    out_file = output_dir / f"chapter_{chapter:02d}.md"
    out_file.write_text(f"# 第{chapter}章\n\n{draft.text}", encoding="utf-8")
    print(f"\n{DIM}已保存: {out_file}{RESET}")


def cmd_batch(args: argparse.Namespace) -> None:
    novel_dir = Path(args.dir).resolve()
    state = _load_state(novel_dir)
    engine = _get_engine(state["db_path"])
    pid = state["project_id"]
    start = int(args.start)
    end = int(args.end)

    print(f"{CYAN}批量生成: 第{start}-{end}章 @ {pid}{RESET}")
    print(f"{DIM}每章间隔5秒用于限流...{RESET}\n")

    total_chars = 0
    output_dir = _ensure_dir(novel_dir / "output")

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

    print(f"\n{GREEN}批量完成: {len(drafts)}章, 总计{total_chars}字{RESET}")
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

# plan
p_plan = sub.add_parser("plan", help="规划章节 (Architect)")
p_plan.add_argument("dir")
p_plan.add_argument("chapter", type=int)
p_plan.add_argument("--task", default="", help="本章任务描述（可选，默认从outline.md读取）")

# write
p_write = sub.add_parser("write", help="生成章节 (Director + Writer + Quality)")
p_write.add_argument("dir")
p_write.add_argument("chapter", type=int)

# batch
p_batch = sub.add_parser("batch", help="批量生成章节")
p_batch.add_argument("dir")
p_batch.add_argument("start", type=int)
p_batch.add_argument("end", type=int)

# export
p_export = sub.add_parser("export", help="导出全部数据（章节/账本/角色状态）")
p_export.add_argument("dir")

# status
p_status = sub.add_parser("status", help="查看项目管道状态")
p_status.add_argument("dir")

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
