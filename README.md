# AWP Novel Runtime V3

一个作者主导、项目管线执行的小说创作运行时。

系统使用两个隔离的嵌入式 Pi Host：

- 交互 Host：在 TUI 中理解作者意图并调用项目级小说工具。
- 角色 Host：为 Writer、Continuity、Style Cleaner、Ledger Curator 等角色维护受限会话。

Python 负责确定性编排、SQLite 持久化、质量检查和文件写入。Agent 没有任意 shell、文件或网络权限。

## 环境

- Python 3.10+
- Node.js 22.19+

```powershell
pip install -e ".[dev,tui]"
cd agent_harness
npm ci
npm test
```

## TUI

```powershell
tui novels\<project-name>
python -m awp_rp_runtime_v3.scripts.awp_tui novels\<project-name>
```

默认使用嵌入式 Pi 专属写作编辑。作者直接说剧情、人物或世界观想法即可，无需调用技能；消息会先保存到项目的 `.awp/authoring/`，再进入编辑对话。编辑不会直接写整章，只有跨轮确认的作者计划才能交给 Writer。

```powershell
$env:NOVEL_AGENT_RUNTIME = "pi"
```

默认作者主导流程：

```powershell
作者对话 → 编辑追问/质疑 → 待确认计划
        → 下一轮批准 → 更后轮执行 → Writer 管线
```

旧 Python NovelBrain 只作为显式兼容边界：

```powershell
$env:NOVEL_AGENT_RUNTIME = "legacy"
```

Pi 启动失败时不会静默切换到 legacy。

## CLI（显式自主模式）

```powershell
python scripts\novel_cli.py init novels\my_novel
python scripts\novel_cli.py seed novels\my_novel
python scripts\novel_cli.py plan novels\my_novel 1
python scripts\novel_cli.py write novels\my_novel 1 --stream
python scripts\novel_cli.py export novels\my_novel
```

CLI 的 `plan` / `batch` 会显式使用 AI 自主规划，保留用于兼容和批处理，不是默认作者主导入口。

## 测试

```powershell
python -m pytest tests\test_novel_*.py -q
cd agent_harness
npm test
```

架构与当前实施计划见：

- `docs/architecture/2026-07-26-novel-only-cleanup-audit.md`
- `docs/superpowers/specs/2026-07-26-author-editor-agent-design.md`
