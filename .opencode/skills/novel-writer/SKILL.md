---
name: novel-writer
description: 使用 novel_cli.py 管理小说项目和生成章节。当用户提到写小说、生成章节、novel CLI、plan/write/batch/seed 命令、小说项目目录（novels/）、微调引导/guidance 文件时使用。触发词: novel_cli, 小说, chapter, 章节, guidance, plan, write, batch, seed, 大纲 outline.md, 项目 project.json。
---

# Novel Writer — 小说 CLI 工作流

## 项目结构

每个小说项目是一个独立目录，位于 `novels/<name>/`:

```
novels/<name>/
  project.json      ← 项目元数据 + 人物设定 + 卷计划（init 生成模板）
  world.md          ← 世界观设定
  outline.md        ← 章节大纲（Markdown 格式，可手动编辑）
  guidance/         ← 分章节微调引导（可选，手动创建）
    chapter_01.md
    chapter_02.md
  novel.db          ← SQLite（seed 后生成）
  .novel_cli.json   ← 状态文件（seed 后生成）
  output/           ← 生成的章节（write 后输出）
    chapter_01.md
```

## 管线流程

```
Architect(plan)  →  Director + Writer + Quality(write)  →  Ledger(curation)
  thinking=high       thinking=high + medium                  thinking=disabled
```

## 命令

统一入口: `python scripts/novel_cli.py`

### init `<dir>` — 初始化项目
生成 `project.json` / `world.md` / `outline.md` 三个模板文件，创建 `output/` 目录。

### seed `<dir>` — 注入数据
读取 `project.json` 和 `world.md`，将以下内容写入 SQLite:
- NovelProject
- NovelCharacter（含人物关系）
- VolumePlan
- LedgerItem（world.md 作为 world_rules，outline.md 作为 outline_map）

### plan `<dir> <章节号>` — 规划章节 (Architect)
```
python scripts/novel_cli.py plan novels/daily_high_school 1
```
从 `outline.md` 读取任务描述，调用 Architect Agent (thinking=high) 生成 ChapterPlan。
可选参数:
- `--task "..."`  覆盖默认任务描述
- `--guidance "..."`  补充硬性要求（与 guidance/chapter_NN.md 自动合并）

输出字段: 标题、定位、目标情绪、开篇钩子、主要内容、scene_beats

### write `<dir> <章节号>` — 生成章节 (Director + Writer + Quality)
```
python scripts/novel_cli.py write novels/daily_high_school 1
python scripts/novel_cli.py write novels/daily_high_school 1 --stream
```
先生成 ChapterPlan 再生成正文。可选参数:
- `--stream`  流式输出，实时展示 Director/Writer/Quality/Curator 各阶段进度
- `--guidance "..."`  硬性要求注入 Writer 提示词

### batch `<dir> <起始章> <终止章>` — 批量生成
```
python scripts/novel_cli.py batch novels/project 1 5
python scripts/novel_cli.py batch novels/project 1 5 --stream
```
连续生成多章，每章间隔 5 秒限流。

### run `<dir> <起始章> <终止章>` — 一键执行
```
python scripts/novel_cli.py run novels/project 1 5
```
等价于 seed → batch → export，一键到底。

### export `<dir>` — 导出数据
导出章节正文、账本条目、角色状态到 `output/`。

### status `<dir>` — 查看状态
展示每个章节的规划/生成状态、账本统计。

## 微调引导系统 (guidance)

### 原理
Guidance 在 plan 阶段追加到 task_description，在 write 阶段注入 Writer 的系统提示词（`### WRITER GUIDANCE` 区块，标注为硬性要求）。

### 自动加载
`plan` 和 `write` 命令自动读取 `guidance/chapter_NN.md`（NN 为两位章节号）:
```
novels/<name>/guidance/chapter_01.md  ← 每次 plan/write 第 1 章时自动加载
novels/<name>/guidance/chapter_02.md  ← 第 2 章
```

### 内联写法
`--guidance` 标志与文件内容合并，用于临时补充:
```bash
python scripts/novel_cli.py write novels/project 1 --guidance "确保沈溪脸红三次以上"
```

### 合并规则
文件内容 + `--guidance` 用空行拼接，一起注入。

### 编写指导
```
1. 【称呼】用"你"直接对 LLM 说话。
2. 【硬性 + 具体】给出具体指令，不是原则性建议。❌ "开篇要有吸引力" ✅ "前500字内必须有冲突或悬念钩子"
3. 【顺序优先】前面的要求权重更高。把最重要的放在第 1 条。
4. 【每条 5-8 条】太少没约束力，太多 LLM 会漏。
```

## 典型工作流

### 从头开始一个新项目
```bash
python scripts/novel_cli.py init novels/my_novel
# 编辑 novels/my_novel/project.json（人物、卷计划）
# 编辑 novels/my_novel/world.md
# 编辑 novels/my_novel/outline.md（章节大纲）
# 可选: 创建 guidance/chapter_01.md 等
python scripts/novel_cli.py seed novels/my_novel
python scripts/novel_cli.py plan novels/my_novel 1
python scripts/novel_cli.py write novels/my_novel 1 --stream
```

### 微调 regen 流程（已生成后修正）
```bash
# 创建或编辑 guidance 文件
# 然后重新规划 + 写入
python scripts/novel_cli.py plan novels/project 1
python scripts/novel_cli.py write novels/project 1 --stream
```

### 批量生成
```bash
python scripts/novel_cli.py batch novels/project 1 40 --stream
```

## 重要文件

| 文件 | 作用 |
|------|------|
| `scripts/novel_cli.py` | CLI 入口 |
| `runtime/novel_engine.py` | NovelEngine — plan/write 编排 |
| `runtime/novel_architect_adapter.py` | Architect LLM 适配器 (thinking=high) |
| `runtime/novel_director_adapter.py` | Director LLM 适配器 (thinking=high) |
| `runtime/novel_writer_adapter.py` | Writer LLM 适配器 (thinking=medium) |
| `runtime/novel_quality_pipeline.py` | 质量门控 |
| `runtime/novel_llm_factory.py` | LLM role-based factory (provider/model/tokens) |
| `runtime/novel_trace.py` | 流式回调数据结构 |

## Notes
- 所有 LLM 调用均为同步阻塞（无 async）
- 需要先 `pip install -e ".[dev]"` 安装依赖
- `NOVEL_LLM_PROVIDER` 环境变量切换 provider（deepseek/opencode/zengate）
- 不支持 rewrite/edit/revise 命令 — 需要重新 plan + write
