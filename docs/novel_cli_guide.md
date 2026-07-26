# Novel CLI 使用指南

## 概述

Novel CLI 是一个文件驱动的小说管线命令行工具。通过项目目录管理小说，自动调用 LLM 生成章节内容。

默认创作入口是 `web.bat <项目目录名>` 打开的 Novel Coding 网页：作者直接谈剧情，消息先写入本地，编辑反复追问并形成计划，作者跨轮批准后才交给 Writer。TUI 是兼容诊断界面；CLI 的 `plan` / `batch` 是保留的显式 AI 自主模式，不代表默认创作权限。

## 快速开始

```bash
# 1. 初始化项目（生成模板文件）
python scripts/novel_cli.py init novels/my_novel

# 2. 编辑项目文件
# 编辑 novels/my_novel/project.json、world.md、outline.md

# 3. 将文件数据注入数据库
python scripts/novel_cli.py seed novels/my_novel

# 4. 规划第1章
python scripts/novel_cli.py plan novels/my_novel 1

# 5. 生成第1章正文
python scripts/novel_cli.py write novels/my_novel 1

# 6. 查看状态
python scripts/novel_cli.py status novels/my_novel

# 7. 导出
python scripts/novel_cli.py export novels/my_novel
```

## 子命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `init <dir>` | 初始化项目目录，生成模板文件 | `init novels/new_book` |
| `seed <dir>` | 读取 project.json/world.md/outline.md → 写入 SQLite | `seed novels/new_book` |
| `plan <dir> <ch>` | Architect 规划章节结构（beats/hook/情绪） | `plan novels/new_book 1` |
| `write <dir> <ch>` | Director+Writer 生成正文 → Quality Gate | `write novels/new_book 1` |
| `batch <dir> <s> <e>` | 批量生成 [s, e] 章节（自动 plan + write） | `batch novels/new_book 1 10` |
| `run <dir> <s> <e>` | 一键：seed → batch → export | `run novels/new_book 1 10` |
| `export <dir>` | 导出全部数据到 export/ 目录 | `export novels/new_book` |
| `status <dir>` | 查看项目状态（章节进度/角色/账本） | `status novels/new_book` |

## 项目文件结构

```
novels/my_novel/
├── project.json       # 项目元数据 + 角色定义 + 卷计划
├── world.md           # 世界观设定
├── outline.md         # 章节大纲/灵感
├── novel.db           # SQLite 数据库（seed 后生成）
├── .novel_cli.json    # CLI 运行时配置
├── .awp/authoring/    # 作者原话、素材与版本化批准计划
├── output/            # 生成的章节 .md 文件
└── export/            # 导出的结构化数据
```

## project.json 结构

```json
{
  "project": {
    "id": "my-novel",
    "title": "小说标题",
    "genre": "类型",
    "one_sentence_pitch": "一句话简介"
  },
  "volume": {
    "index": 1,
    "title": "第一卷",
    "chapter_start": 1,
    "chapter_end": 10,
    "objective": "本卷目标",
    "core_conflict": "核心冲突",
    "emotional_arc": "情绪弧线"
  },
  "characters": [
    {
      "character_id": "char-01",
      "name": "主角名",
      "role": "protagonist",
      "personality": "性格描述",
      "core_motivation": "核心动机",
      "arc_phase": "setup"
    }
  ]
}
```

角色 role 可选值：`protagonist`（主角）、`deuteragonist`（第二主角）、`supporting`（配角）、`antagonist`（反派）。

## 管线流程

默认作者主导 TUI：

```text
作者对话 → 本地日志 → 编辑追问/质疑 → 待确认计划
        → 下一轮批准 → 更后轮执行 → 确定性编译 → Writer
```

显式自主 CLI：

```
init → 编辑文件 → seed（文件→DB）
                         ↓
plan ← Architect（规划章节结构，3 beats）
                         ↓
write ← Director（展开 beats）→ Writer（逐 beat 生成）→ Quality Gate
                         ↓
                    status/export
```

## 常见问题

**Q: plan 超时？** Architect 使用 thinking=HIGH，大型项目可能需 2-3 分钟。失败会自动重试。

**Q: write 返回 rejected？** Quality Gate 检测到问题（元数据泄露/AI 拒绝/字数不足），已降级接受并保存。可修改 prompts/writer.md 调整质量标准。

**Q: 如何修改文风？** 编辑 `prompts/writer.md`（SFW 和 NSFW 规范），修改后新章节立即生效。

**Q: 如何调整角色走向？** 编辑 `project.json` 中角色的 personality/core_motivation，重新 seed 即可更新角色状态。
