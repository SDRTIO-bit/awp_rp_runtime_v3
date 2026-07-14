# Pi 小说 Agent Harness 设计

**状态：** 已确认

**实施：** `agent_harness/`、`NovelPiBridge`、`NovelPiToolService` 与 `NovelAgentRuntime` 已按本文边界落地；真实模型联调仍由 `NOVEL_PI_E2E=1` 显式开启。

## 目标

将 Pi 0.80.6 的 `AgentSession` 作为小说模式的 Agent harness，替换 TUI 直接使用的固定 Python `NovelBrain` ReAct 循环。Pi 负责会话、技能、工具循环、上下文压缩、取消与流式 Agent 事件；Python 小说管线继续负责生成、质量门、账本和所有持久化写入。

## 范围与非目标

范围只限小说模式及 `awp_tui.py`。RP 模式、现有网页入口、小说大纲与正文内容均不在此次改造范围内。

本次不嵌入 Pi 的交互 TUI，不调用外部 `pi` CLI，不开放任意 shell、文件编辑、文件读取或联网工具，不安装第三方 Pi 技能包。Pi 以受控 Node SDK 进程形式运行在项目内部。

## 架构

```text
Textual NovelTui
    │ Python 调用与界面回调
    ▼
NovelPiBridge（Python，子进程与协议管理）
    │ 双向 JSON Lines，标准输入/输出
    ▼
NovelAgentHost（Node，Pi AgentSession）
    │ Pi 自定义领域工具
    ▼
NovelPiToolService（Python，参数校验与业务适配）
    ▼
NovelEngine（唯一业务写入者）
```

`NovelAgentHost` 使用 Pi SDK 的 `createAgentSession()`。它以 `noTools: "all"` 启动，仅注册本项目定义的领域工具；不会把 Pi 默认的 `read`、`bash`、`edit`、`write` 暴露给模型。

Node 与 Python 不使用网络端口。Python 启动 Node 子进程后，双方通过带 `request_id` 的 JSON Lines 协议通信：Python 发出 `prompt`、`cancel` 与会话控制请求；Node 发出 Agent 流式事件及 `tool_call` 请求；Python 发回 `tool_result` 或 `tool_error`。同一会话一次只执行一个 prompt，桥接层以互斥锁保证工具请求与流式事件不会交叉到其他项目。

## 组件职责

### Node：`agent_harness/`

- `package.json` 将 `@earendil-works/pi-coding-agent` 精确固定为 `0.80.6`，并提交 lockfile。运行环境要求 Node `>=22.19`；当前机器的 Node 24.11.0 满足要求。
- `src/novel_agent_host.mjs` 管理 Pi `AgentSession`、JSON Lines 收发、每项目会话恢复、取消和事件转换。
- `src/novel_tools.mjs` 使用 Pi `defineTool` 定义工具 schema；工具实现只会发送 Python RPC，不能执行 Node shell 或访问任意路径。
- `resources/` 放置项目审阅过的系统提示与三个技能。Host 使用受控资源加载器，不扫描用户全局 `~/.pi`、项目任意 `.pi` 目录或外部扩展。

### Python：小说业务边界

- `runtime/novel_pi_protocol.py` 定义 Pydantic v2 的协议帧和错误码。
- `runtime/novel_pi_bridge.py` 启停 Host 子进程、关联请求、转发取消、将 Pi 与小说流式事件映射到 `BrainCallbacks`。
- `runtime/novel_pi_tool_service.py` 将经过校验的领域调用转交给 `NovelEngine` 或现有只读 store 接口。
- `scripts/awp_tui.py` 使用桥接层，不再直接实例化 `NovelBrain`。它保留现有阶段、正文和错误展示方式。

`NovelEngine`、`CardStateCommitRuntime`、`ActiveMemoryCommitRuntime` 与 `RagMemoryCommitRuntime` 的写入职责不改变。Agent host 不持有数据库连接，也不直接写项目文件。

## 初始工具与技能

工具均绑定当前已经打开的小说项目；模型不能传入任意目录、数据库路径或其他项目标识。

| 工具 | 权限 | 行为 |
|---|---|---|
| `project_status` | 只读 | 返回当前项目、章节、计划和质量状态摘要。 |
| `read_chapter` | 只读 | 读取指定已存在章节，限制返回长度。 |
| `plan_chapter` | 受控写入 | 通过现有规划运行时创建或更新指定章节细纲。 |
| `write_chapter` | 受控写入 | 调用 `NovelEngine.write_chapter_stream()`；所有阶段事件回送 TUI。 |
| `audit_chapter` | 只读 | 运行质量与连续性审查，只返回报告，不自动改写正文。 |

初始技能保持为三个短小、可审阅的文件：

1. `project-status`：先查项目、再做操作，遇到未连接项目立即解释。
2. `single-chapter`：一章一事；无细纲不写；生成失败不把空结果说成成功。
3. `audit`：报告明确问题与建议；除非用户再次要求，不触发改写或章节生成。

这些技能替代当前 `NovelBrain` 中堆叠的长规则，但不承载正文风格提示词。Architect、Writer、Quality 等角色提示仍由 Python 小说管线按需加载。

## 模型、会话与配置

Python 保留 `NOVEL_LLM_PROVIDER`、`NOVEL_LLM_MODEL` 作为唯一配置入口。启动 Host 时，桥接层解析当前 provider、模型名与连接配置，以仅在进程内存中存在的方式交给 Pi；密钥不得写入 Pi session、项目文件或日志。

Pi 会话按小说项目隔离，保存到项目受控的 Agent session 目录；项目切换必然创建或恢复对应会话，不允许跨项目注入历史。会话内容仅保存对话和工具结果摘要，章节全文仍由 SQLite/章节存储作为权威来源。

首次上线时，TUI 默认使用 `NOVEL_AGENT_RUNTIME=pi`。`NOVEL_AGENT_RUNTIME=legacy` 明确启用原 `NovelBrain` 作为人工回退；不会在 Pi 失败时静默回退，避免用户误以为正在使用新 harness。

## 失败、取消与可观察性

- Node 未安装、版本不足、Host 退出、Pi 模型认证失败、协议帧不合法时，桥接层返回可读错误并不调用 `NovelEngine`。
- 工具参数错误、未知工具、工具超时与 `NovelEngine` 异常均以结构化 `tool_error` 返回 Pi，同时显示在 TUI 的错误区。
- 用户取消时，Python 向 Host 发送 `cancel`，Host 调用 `AgentSession.abort()`；已经进入 `NovelEngine` 的生成由现有回调和异常路径终止，质量门未接受前不得提交副作用。
- 每轮设置最大工具调用数与单工具超时；超出预算时 Host 终止该轮并保留会话诊断。
- 每个 prompt 生成关联 ID。Pi 的 Agent 开始、文本增量、工具开始/结束、管线阶段、错误和取消都带该 ID，供 TUI 和执行追踪关联。

## 测试与验收

Python 使用 pytest，Node 使用内建 `node:test`，不引入新的测试框架。

1. Node 单元测试验证：只注册五个领域工具；默认文件和 shell 工具不可见；每个工具的 schema 与协议映射正确；取消会调用 session abort。
2. Python 单元测试使用伪 Host 验证：帧编解码、请求关联、异常传播、超时、取消、项目隔离与回调事件顺序。
3. `NovelPiToolService` 测试验证：只读工具没有副作用；写作工具必须走 `NovelEngine`；审计工具不会改写正文；空白 Writer 失败不被报告为成功。
4. TUI 回归测试验证：Pi bridge 的阶段、正文块与错误仍显示在既有面板；`legacy` 开关仍可启动旧 Brain。
5. 可选真实联调由 `NOVEL_PI_E2E=1` 显式开启，使用现有 Kimi/OpenCode 配置跑一项只读状态操作和一项单章计划操作；默认测试不访问外部模型。

验收标准是：TUI 的一次小说指令在 Pi 会话中完成，Agent 只能调用受限小说工具；生成的章节仍通过原有质量门与账本提交；失败、取消和工具错误均不会留下空章节或未批准的状态写入。
