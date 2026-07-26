# AWP Pi 专属写作编辑 Harness

这里内嵌两个隔离的 Pi Host，不依赖外部 Pi CLI，也不开端口。

- `novel_agent_host.mjs`：项目级专属写作编辑。它自动识别创作意图、读取上下文、保存素材、整理计划并执行跨轮确认。
- `novel_role_host.mjs`：自动管线角色 Host，运行 Writer、Continuity、Style Cleaner、Ledger Curator，以及显式自主 CLI 使用的 Architect/Director。

默认编辑只有八个项目绑定工具：

`project_status`、`read_chapter`、`audit_chapter`、`read_authoring_context`、`capture_author_material`、`save_author_plan`、`approve_author_plan`、`execute_author_plan`。

它没有 shell、网络或任意文件读写能力，也没有 `plan_chapter` / `write_chapter` 绕过入口。Python 会在每条作者消息发给 Pi 之前写入项目日志，并强制计划提出、作者批准、启动写作发生在三个不同作者轮次。

```powershell
cd agent_harness
npm ci
npm test
$env:NOVEL_AGENT_RUNTIME = 'pi'
python ..\scripts\awp_tui.py ..\novels\<project-name>
```

作者可直接用自然语言讨论剧情，无需输入 `/skill`。`author-collaboration` Skill 会自动进入 CAPTURE → DIVERGE → CHALLENGE → SYNTHESIZE → CONFIRM → HANDOFF 循环。

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
