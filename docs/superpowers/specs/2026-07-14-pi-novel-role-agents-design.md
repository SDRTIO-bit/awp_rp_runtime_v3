# Pi 小说角色 Agent 底层迁移设计

日期：2026-07-14  
状态：已批准，进入实施规划

## 1. 目标

将小说模式中所有依赖大模型判断的角色迁移为真正的 Pi Agent Session，而不是把 Pi 当作一次 `generate_text()` 的转发器。

迁移范围包括：

- 顶层小说调度 Agent
- Architect
- Director
- Writer
- Continuity Checker / Auditor
- Style Cleaner / Rewriter
- Ledger Curator

所有小说入口统一使用同一套角色运行时：

- `scripts/novel_cli.py plan/write/batch/run`
- `scripts/awp_tui.py`
- 后续 Web 小说入口

RP 模式不在本次范围内。

## 2. 三种方案

### 方案 A：Pi 只作为 LLM 代理

Python 保留现有角色逻辑，只把 `OpenAICompatibleAdapter.generate_text()` 换成经 Pi 发出一次模型请求。

优点是改动小。缺点是 Pi 不拥有角色会话、工具循环和 Skill，实质仍是原有自建 Agent，仅更换传输层。

结论：拒绝。它不符合“底层 Agent 是 Pi”的要求。

### 方案 B：Pi 作为所有小说角色的底层 Agent Runtime

Python 向 Pi 提交结构化角色任务。Pi 创建角色 Session，加载角色 Skill/插件，按需调用项目绑定的只读工具，并在 Pi 内部调用配置的模型。Python 只负责上下文序列化、结果校验、质量门、状态提交和文件导出。

结论：采用。

### 方案 C：将整个小说管线迁移到 Node/Pi

由 Pi 同时负责角色调度、数据库、状态提交和文件写入。

该方案会破坏当前“质量门拒绝时零副作用”和“只有确定性运行时可以提交状态”的边界，也会重复实现 Python 存储层。

结论：拒绝。

## 3. 目标架构

```text
TUI / novel_cli / Web
          |
          v
Python NovelEngine（确定性编排）
          |
          v
NovelPiRoleRuntime（JSONL 桥）
          |
          v
独立 Node Pi Role Host
          |
          +-- Architect Session + Skill + 只读工具
          +-- Director Session + Skill + 只读工具
          +-- Writer Session + Skill + 只读工具
          +-- Auditor Session + Skill + 只读工具
          +-- Cleaner Session + Skill
          +-- Ledger Session + Skill + 只读工具
          |
          v
Kimi / DeepSeek / MiMo / 其他兼容模型

Pi 返回结构化结果
          |
          v
Python 校验 -> Quality Gate -> Store Commit -> Export
```

Pi 是角色执行层；Python 不再直接对这些角色发起模型请求。

## 4. 与现有顶层 Pi 的关系

保留现有交互式 `NovelAgentHost`，但它只负责理解用户指令和选择高层小说工具。

新增独立的 `NovelRoleHost` 承担 Architect、Director、Writer 等角色任务。两个 Host 必须是不同进程或完全独立的消息循环。

原因：顶层 Pi 调用 `write_chapter` 时，Python 会进入 `NovelEngine`；如果 Writer 再复用正在等待工具结果的同一个 Pi Session，会产生递归等待和死锁。

数据流如下：

```text
顶层 Pi Host --write_chapter--> Python NovelEngine --writer task--> Pi Role Host
```

## 5. Python 与 Pi 的职责边界

### Python 保留

- SQLite Registry/Store
- 项目、章节、角色、账本的读取接口
- 写作包和任务上下文的确定性序列化
- Pydantic 契约校验
- 章节计划、正文、质量结果和账本的提交
- Quality Gate 及“拒绝时零副作用”
- CLI/TUI 流式事件转发
- 导出 Markdown 与质量报告

### Pi 承担

- 角色 Session 生命周期
- 角色系统提示和 Skill 加载
- 工具选择与 ReAct 循环
- 模型调用
- 同一章节内 Writer 上下文延续
- 角色输出的初步结构化
- 中止、超时和会话错误报告

### 明确禁止

- Pi 直接写 SQLite
- Pi 直接修改小说正文文件
- Pi 使用任意 shell
- Pi 使用任意文件读写工具
- Pi 使用未登记的网络工具
- 角色 Pi 调用 `plan_chapter` 或 `write_chapter`，造成递归
- Pi 失败后自动切回旧 LLM Adapter

## 6. 角色任务协议

Python 向 Role Host 发送 `role_prompt`，至少包含：

- `request_id`
- `role`
- `project_id`
- `chapter_index`
- `revision`
- `phase`
- `session_key`
- `task_contract`
- `input_payload`
- `model_connection`
- `max_tokens`
- `thinking_level`
- `stream`

Role Host 返回：

- 文本增量事件
- 工具调用事件
- 角色阶段事件
- 最终文本或结构化 JSON
- 模型、token、时延和结束原因
- 可诊断但不包含密钥的错误

Python 使用新的 `PiRoleResult` 契约接收结果。Architect、Director、Auditor、Ledger 的 JSON 仍由 Python Pydantic/解析器做最终校验；Writer 和 Cleaner 的正文由现有长度、截断和质量规则校验。

## 7. 会话生命周期

采用章节级混合会话：

- 顶层调度 Agent：项目级持久 Session。
- Architect：每次规划新建 Session，完成即关闭。
- Director：每次章节细纲任务新建 Session，完成即关闭。
- Writer：同一 `project_id + chapter_index + revision` 的所有 beat 共用一个 Session；章节结束、失败或取消后关闭。
- Continuity/Auditor：每次审计新建 Session。
- Style Cleaner：每次改写任务新建 Session；片段改写不得跨章复用上下文。
- Ledger Curator：每章提交前新建 Session，完成即关闭。
- 重跑或修订章节：使用新的 `revision` Session，不复用失败历史。

长期事实只能来自 Python Store、Ledger 和任务输入。Pi 聊天历史不是权威状态。

## 8. 角色只读工具

新增项目绑定的只读工具服务。所有工具从当前任务自动绑定 `project_id`，模型不能传入其他项目路径或数据库标识。

基础工具：

- `project_status`
- `read_project_contract`
- `read_chapter_plan`
- `read_chapter`
- `read_ledger`
- `read_characters`
- `read_write_packet`

角色允许列表：

| 角色 | 工具 |
|---|---|
| Architect | project_status, read_project_contract, read_chapter, read_ledger, read_characters |
| Director | read_project_contract, read_chapter_plan, read_chapter, read_ledger, read_characters |
| Writer | read_chapter_plan, read_chapter, read_ledger, read_characters, read_write_packet |
| Continuity/Auditor | read_chapter_plan, read_chapter, read_ledger, read_characters |
| Style Cleaner | 无工具，输入中已包含待改文本和问题清单 |
| Ledger Curator | read_chapter_plan, read_chapter, read_ledger, read_characters |

工具返回设定最大字符数并记录调用轨迹，避免 Agent 重复读取全书造成 token 浪费。

## 9. Skill 与插件

内置角色资源放在：

```text
agent_harness/resources/roles/<role>/system-prompt.md
agent_harness/resources/roles/<role>/skills/<skill-name>/SKILL.md
```

第一期内置 Skill：

- Architect：章节契约、节奏和场景 beat 规划
- Director：场景摩擦、对话推进和信息交付
- Writer：对话驱动、去 AI 味、章节连续性
- Auditor：计划遵循、角色声音、重复表达和连续性
- Cleaner：最小改写与截断保护
- Ledger：事实提取、关系变化和伏笔状态

项目可在以下目录提供额外 Skill：

```text
<novel_dir>/agent/skills/<skill-name>/SKILL.md
```

只加载项目目录中的 Skill，不加载用户全局 `.pi`、其他项目或外部 Pi 包。

插件采用项目仓库内登记的 Pi Extension，主要负责上述只读工具和结构化输出辅助。第一期不自动安装第三方网络插件；后续若引入 Pi package，必须有明确 allowlist、锁定版本并通过工具权限审计。

## 10. 模型与运行时配置

`NOVEL_AGENT_RUNTIME` 控制 Agent 实现：

- `pi`：默认。所有小说 LLM 角色由 Pi Session 执行。
- `legacy`：显式回退。保留现有直接 LLM Adapter 便于对照和紧急恢复。

模型仍由现有环境变量配置：

- `NOVEL_LLM_PROVIDER`
- `NOVEL_LLM_MODEL`
- `NOVEL_LLM_PROVIDER_<ROLE>`
- `NOVEL_LLM_MODEL_<ROLE>`
- `NOVEL_LLM_BASE_URL`
- `NOVEL_LLM_API_KEY_ENV`

Role Host 初始化时注册全部角色所需模型。密钥只由 Node 子进程从环境变量读取，不通过 JSONL、Session 文件或日志传递。

默认 `pi` 模式缺少 Node、Pi 依赖或密钥时必须清晰失败，并给出修复命令；不得静默使用 legacy。

## 11. CLI 与 TUI 行为

### CLI

`novel_cli.py status/export` 不需要启动 Pi。

下列命令默认通过 Pi 角色运行时：

- `plan`
- `write`
- `batch`
- `run`

CLI 启动时显示：

```text
Agent Runtime: Pi role agents
Provider/Model: opencode / kimi-k2.6
```

### TUI

顶层对话继续由现有 Pi 调度 Host 负责。调用 plan/write 工具后，角色生成转交独立 Role Host。TUI 同时展示顶层 Agent 事件和角色 phase/beat/chunk 事件。

## 12. 流式输出

Writer Role Host 把 Pi `text_delta` 映射到现有 `NovelStreamCallbacks.on_chunk`。Python 仍负责 beat 起止、质量阶段和账本阶段事件。

Role Host 必须保证：

- 同一请求的 delta 顺序稳定
- 取消后不再发出正文增量
- 最终文本等于已发送增量拼接结果
- 空输出和截断输出作为失败返回

## 13. 错误与恢复

- Host 启动失败：命令失败，提示 `npm ci`、Node 版本或缺失密钥。
- Role 输出无效：Python 校验失败，不提交计划/正文。
- Writer 中途失败：关闭当前章节 Writer Session，不保存半章。
- 工具越权：Role Host 拒绝，并记录角色、工具名和 request id。
- 超时/取消：Python 向 Role Host 发送 cancel，等待短暂退出后终止子进程。
- Pi SDK 异常：不得自动调用旧 Adapter；用户必须显式设置 `NOVEL_AGENT_RUNTIME=legacy`。
- 顶层 Host 与 Role Host 任一崩溃时，另一方可独立关闭，不留下锁定数据库或半写文件。

## 14. 兼容迁移

现有角色 Adapter 不立即删除。迁移期间它们承担两类职责：

1. legacy 模式的直接模型调用。
2. pi 模式下可复用的确定性任务序列化和结果解析。

但 pi 模式不得从这些 Adapter 调用 `generate_text()`。最终调用路径必须能通过测试证明进入 `NovelPiRoleRuntime`。

建议实施顺序：

1. 协议与 Role Host
2. 只读工具与角色资源加载
3. Architect/Director
4. Writer 与流式章节会话
5. Continuity/Style/Ledger
6. CLI/TUI 默认切换
7. legacy 对照与真实 Kimi 验收

## 15. 测试策略

### Node 单元测试

- 每个角色加载正确 Skill
- 每个角色只获得允许的工具
- Role Host 使用 `createAgentSession`
- Writer 同章复用、跨章隔离
- 无全局 `.pi` 资源和默认 shell/file/network 工具
- cancel、超时和结构化结果事件

### Python 单元测试

- pi 默认路径不实例化 Direct LLM Adapter
- legacy 显式路径仍可运行
- Role Task/Result 协议校验
- 工具项目绑定与长度上限
- Writer 流式增量和最终正文一致
- 空输出、坏 JSON、截断时零持久化

### 集成测试

- `novel_cli plan` 经过 Architect Pi Session
- `novel_cli write --stream` 经过 Director/Writer/Auditor/Ledger Pi Session
- 顶层 Pi 调用 `write_chapter` 时独立 Role Host 无死锁
- 质量门拒绝时 Draft/Ledger 无副作用
- `NOVEL_AGENT_RUNTIME=legacy` 可完成同一假模型测试

### 真实模型验收

通过显式环境开关运行，不纳入默认 CI：

- OpenCode + Kimi K2.6
- 单章 plan -> write -> audit -> export
- 验证角色轨迹中所有 LLM 角色均标记为 Pi Session
- 验证正文文件、质量报告和账本正常写入

## 16. 完成标准

满足以下条件才算完成迁移：

1. `novel_cli plan/write/batch/run` 默认使用 Pi 角色 Agent。
2. TUI 高层 Pi 与角色 Pi 可嵌套工作且无死锁。
3. Architect、Director、Writer、Continuity/Auditor、Style Cleaner、Ledger Curator 的模型调用全部发生在 Pi Session 内。
4. Pi 角色能加载项目内 Skill，并只能使用角色允许的只读工具。
5. Python 仍是唯一状态和文件提交者。
6. Pi 失败不会静默回退。
7. 流式正文、质量门和账本行为保持兼容。
8. 单元、集成和真实 Kimi 单章验收均通过。

## 17. 实施与验收状态（2026-07-14）

已实现：

- 顶层交互 Pi Host 与底层 Pi Role Host 分进程运行。
- Architect、Director、Writer、Continuity Checker、Style Cleaner、Ledger Curator 均通过 `NovelPiRoleTask` 进入真实 Pi Agent Session。
- Writer 以 `project + chapter + revision` 复用章节 Session，其余角色使用任务 Session。
- 角色只获得白名单只读工具；Style Cleaner 无工具；Python 保持唯一写状态方。
- CLI `plan/write/batch/run` 默认检查 Pi 依赖并显示 Agent Runtime 与 provider/model；只允许显式 `NOVEL_AGENT_RUNTIME=legacy` 回退。

本地验证：

- `npm test`（`agent_harness`）：14 passed。
- `python -m pytest tests -q`：1222 passed, 3 skipped。
- 双 Host 集成：顶层 fake Pi 依次触发 Architect → Director → Writer → Continuity → Ledger，独立 Role Host 完成并落库，无死锁。

真实 Kimi 2.6 验收：

- 配置：`NOVEL_AGENT_RUNTIME=pi`、`NOVEL_LLM_PROVIDER=opencode`、`NOVEL_LLM_MODEL=kimi-k2.6`。
- Architect 真实 Pi Session 正常 `stop`，曾调用 4 个只读工具；最终正文 2810 字符，usage output 4460 tokens。
- Director 真实 Pi Session 正常 `stop`，曾调用 2 个只读工具；最终正文 2834 字符，usage output 5145 tokens。
- Writer 真实 Pi Session 已启动并完成一次只读工具调用，但整条 pytest 命令在 600 秒外层时限到达后被终止，未取得 Writer 终止帧。
- 结论：真实 Pi/Kimi 架构、鉴权、工具回路已验证；完整单章端到端仍标记为未通过，原因是累计执行时间超过本次外层验收窗口。不得把该结果表述为完整 E2E 通过。

