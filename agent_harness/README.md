# AWP Pi 小说 Agent Harness

这个目录将 Pi 作为小说模式的内嵌 Agent harness。它不是外部 `pi` CLI：Textual TUI 启动本地 Node Host，Pi 只能调用五个项目绑定的小说工具；Python `NovelEngine` 保留所有生成、审计和状态写入职责。

允许的工具只有：`project_status`、`read_chapter`、`plan_chapter`、`write_chapter`、`audit_chapter`。Pi 默认的 shell、读写文件和网络工具被 `noTools: "all"` 禁用。

```powershell
cd F:\12\语英\awp_rp_runtime_v3\agent_harness
npm ci
npm test
$env:NOVEL_AGENT_RUNTIME = 'pi'
python scripts\awp_tui.py novels\<project-name>
```

使用已有的 `NOVEL_LLM_PROVIDER`、`NOVEL_LLM_MODEL`、`NOVEL_LLM_BASE_URL` 和 `NOVEL_LLM_API_KEY_ENV` 配置模型。密钥仅从环境变量交给 Node 进程，不写入会话或项目文件。

若需临时恢复旧 Python Agent，唯一方式是显式设置：

```powershell
$env:NOVEL_AGENT_RUNTIME = 'legacy'
```

Pi 失败时不会自动回退，以免误判当前执行的 Agent。
