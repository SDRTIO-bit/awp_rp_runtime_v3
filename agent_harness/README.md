# AWP Pi 专属写作编辑 Harness

这里内嵌两个隔离的 Pi Host，不依赖外部 Pi CLI，也不开端口。

- `novel_agent_host.mjs`：项目级专属写作编辑。它自动识别创作意图、读取上下文、保存素材、整理计划并执行跨轮确认。
- `novel_role_host.mjs`：自动管线角色 Host，运行 Writer、Continuity、Style Cleaner、Ledger Curator，以及显式自主 CLI 使用的 Architect/Director。

默认编辑有以下项目绑定工具：

`project_status`、`read_chapter`、`audit_chapter`、`read_authoring_context`、`capture_author_material`、`save_author_plan`、`approve_author_plan`、`execute_author_plan`、`update_work_plan`、`delegate_project_task`。

以及沙箱内的 `read`、`ls`、`find`、`grep`、`write`、`edit`、`bash`（仅 `pwd`）。

```powershell
cd agent_harness
npm ci
npm test
$env:NOVEL_AGENT_RUNTIME = 'pi'
python ..\scripts\awp_tui.py ..\novels\&lt;project-name&gt;
```

编辑器没有 shell（仅 `bash pwd`）、网络或任意文件读写能力，没有 `plan_chapter` / `write_chapter` 绕过入口。

本地恢复资料位于：

```text
<project>/.awp/authoring/journal/YYYY-MM-DD.jsonl
<project>/.awp/authoring/inbox.jsonl
<project>/.awp/authoring/chapter-plans/<plan-id>.v<revision>.json
<project>/.awp/authoring/index.json
```

若需显式使用旧 Python NovelBrain：

```powershell
$env:NOVEL_AGENT_RUNTIME = 'legacy'
```

Pi 故障不会自动回退。
