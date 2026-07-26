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

默认使用嵌入式 Pi：

```powershell
$env:NOVEL_AGENT_RUNTIME = "pi"
```

旧 Python NovelBrain 只作为显式兼容边界：

```powershell
$env:NOVEL_AGENT_RUNTIME = "legacy"
```

Pi 启动失败时不会静默切换到 legacy。

## CLI

```powershell
python scripts\novel_cli.py init novels\my_novel
python scripts\novel_cli.py seed novels\my_novel
python scripts\novel_cli.py plan novels\my_novel 1
python scripts\novel_cli.py write novels\my_novel 1 --stream
python scripts\novel_cli.py export novels\my_novel
```

## 测试

```powershell
python -m pytest tests\test_novel_*.py -q
cd agent_harness
npm test
```

架构与当前实施计划见：

- `docs/architecture/2026-07-26-novel-only-cleanup-audit.md`
- `docs/superpowers/specs/2026-07-26-author-editor-agent-design.md`
