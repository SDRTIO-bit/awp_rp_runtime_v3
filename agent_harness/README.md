# AWP Pi 小说 Agent Harness

这个目录将 Pi 作为小说模式的内嵌 Agent harness。它不是外部 `pi` CLI，也不是一次 LLM 请求的转发器。

小说模式使用两个隔离的 Node Host：

- `novel_agent_host.mjs`：项目级交互 Agent，理解 TUI 指令并调用高层小说工具。
- `novel_role_host.mjs`：底层角色 Agent，分别运行 Architect、Director、Writer、Continuity、Style Cleaner 和 Ledger Curator 的 Pi Session。

两个 Host 分离是为了避免顶层 Pi 等待 `write_chapter` 时，Writer 又递归占用同一 Session 所造成的死锁。Python `NovelEngine` 只保留确定性编排、质量规则、状态提交和 SQLite 持久化。

交互 Agent 允许的工具只有：`project_status`、`read_chapter`、`plan_chapter`、`write_chapter`、`audit_chapter`。角色 Agent 按角色获得更窄的只读工具集；Style Cleaner 无工具。Pi 默认的 shell、读写文件和网络工具全部禁用。

```powershell
cd F:\12\语英\awp_rp_runtime_v3\agent_harness
npm ci
npm test
$env:NOVEL_AGENT_RUNTIME = 'pi'
python scripts\novel_cli.py plan novels\<project-name> 1
python scripts\novel_cli.py write novels\<project-name> 1 --stream
python scripts\awp_tui.py novels\<project-name>
```

`plan`、`write`、`batch`、`run` 会显示实际的 Agent Runtime 与 Writer provider/model。若依赖缺失，命令会明确提示在 `agent_harness` 运行 `npm ci`，不会悄悄退回旧实现。

使用已有的 `NOVEL_LLM_PROVIDER`、`NOVEL_LLM_MODEL`、`NOVEL_LLM_BASE_URL` 和 `NOVEL_LLM_API_KEY_ENV` 配置模型。密钥仅从环境变量交给 Node 进程，不写入会话或项目文件。

若需临时恢复旧 Python Agent，唯一方式是显式设置：

```powershell
$env:NOVEL_AGENT_RUNTIME = 'legacy'
```

Pi 失败时不会自动回退，以免误判当前执行的 Agent。
