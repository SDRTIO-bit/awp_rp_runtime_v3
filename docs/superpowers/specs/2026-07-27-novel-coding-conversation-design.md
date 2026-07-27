# 小说专属 Coding 对话升级设计

日期：2026-07-27
状态：设计已确认，等待实施

## 1. 目标

把现有 Novel Coding 网页中的“能聊天、能调用项目工具”升级为一个可靠的、
可追溯的小说专属 Coding 对话系统。作者无需输入技能名或命令；编辑自行判断何时读取
项目、搜索、建立工作计划、委派只读调查、申请文件修改审批，以及何时继续追问作者。

本次升级解决五类实际问题：

1. 作者对某轮对话不满意时，不能新建对话、修改重发或重新生成。
2. 所有历史共用一个 Pi 会话，错误方向会持续污染后续上下文。
3. 服务重启后，未结束的 `editor_delta` 可能永久显示“正在回应”。
4. 编辑回复按普通文本渲染，Markdown、表格、列表和代码不可读。
5. 工具、文件改动、审批和工作进度没有归属到具体对话轮次。

## 2. 不可破坏的产品边界

- 系统仍然是 novel-only，不恢复 RP、ComfyUI 或通用开发终端。
- 编辑忠于作品和目标读者，不讨好作者，也不替作者选择剧情。
- 编辑负责捕获、追问、质疑、综合和形成待确认的作者计划，不直接写完整章节。
- “编辑工作计划”只是调查和操作清单，绝不能作为章节剧情计划或 Writer 输入。
- 作者计划的提出、批准和执行仍必须发生在不同作者轮次。
- Writer 只消费经过批准的作者计划；编辑对话分支不能绕过 `AuthorPlanCompiler`。
- 项目工具只能访问绑定小说项目，不能访问项目外路径、网络或任意 Shell。
- AI 自动调用工具；任何能力都不能要求作者记忆斜杠命令或技能名。
- Python 继续作为项目状态和文件的唯一写入方。
- 旧对话、旧项目文件和旧 Pi 会话不得被迁移过程覆盖或删除。

## 3. 核心模型：追加式对话分支

### 3.1 分支不是覆盖

每个全书或章节房间拥有一棵对话分支树。作者执行以下动作时创建新分支：

- 新建对话：创建没有父分支的新根。
- 修改并重新发送：从目标作者消息之前分叉，再发送修改后的消息。
- 重新生成：从目标作者消息之前分叉，再发送原消息。
- 从旧版本继续：从该版本当前头部创建子分支，再接收下一条作者消息。

旧分支保持只读。继续在归档分支或非叶分支输入时，服务器必须先创建新分支。
任何操作都不得删除、改写或重排原 JSONL 事件。

### 3.2 存储

沿用 `.awp/authoring/conversations/`：

```text
book.jsonl
book.branches.jsonl
chapter-000001.jsonl
chapter-000001.branches.jsonl
```

- 房间 JSONL 保存不可变对话事件。
- `*.branches.jsonl` 保存 `branch_created`、`branch_renamed`、
  `branch_archived` 等不可变元数据事件。
- `event_id` 继续使用项目级单调递增序号。
- 新事件增加 `branch_id` 和可选 `turn_id`。
- 旧事件缺少 `branch_id` 时读取为 `main`，不得重写旧文件。
- 没有分支元数据的旧房间在读取时合成一个 `main` 根分支。

### 3.3 继承与上下文隔离

子分支只继承父分支到 `fork_event_id` 为止的最终对话和已发生事实。父分支在分叉点
之后的编辑回答、工具调用和计划不能进入子分支 Pi 上下文。

Pi Session 的键从 `(project_id, room)` 改为
`(project_id, room, branch_id)`。新分支使用独立 Session 目录。首次启动该 Session
时，由 Python 从分支事件生成有界的上下文快照，并作为只读历史背景交给 Pi；之后继续
使用该分支自己的持久 Session。

上下文快照只包含：

- 已保存的作者消息；
- 已完成的编辑回复；
- 已确认的作者计划引用；
- 已发生的文件修改、管线和批准事实摘要。

未完成增量、失败回复的残片、其他分支未来事件和私有推理不得进入快照。

## 4. 副作用原则

离开、归档或从旧节点分叉只改变对话视图，不回滚项目状态。以下事件属于副作用：

- `write`、`edit` 或文件版本恢复成功；
- 保存、批准或执行作者计划；
- Writer/质量/账本管线开始产生正式结果；
- 正式草稿或其他版本化项目文档保存。

当“修改重发”或“重新生成”会舍弃分叉点之后含副作用的对话路径时，服务器返回
结构化冲突。前端必须展示副作用清单，作者确认“保留这些改动并创建新版本”后才能创建
分支。确认不意味着回滚。

自动回滚明确禁止。文件恢复是一个独立的重要写操作，必须显示准确 Diff、检查当前
哈希并再次得到审批。

## 5. 持久轮次状态机

每条作者消息建立唯一 `turn_id`。状态按事件推进：

```text
turn_started
  → author_message_saved
  → editor_delta / tool_activity / tool_approval_requested
  → editor_message_completed
  → turn_completed
```

终止事件：

- `turn_failed`
- `turn_cancelled`
- `turn_interrupted`

计划批准和管线执行也必须带 `turn_id`，并以同样方式记录运行、等待审批、完成和失败。

服务器首次加载某个分支时，扫描最后一个非终态轮次。如果进程中没有对应活动任务，
追加 `turn_interrupted`。浏览器收到后清除流式光标、保留已有残片为“未完成回复”，
并显示“重试本轮”。因此刷新或服务重启后不能永久显示“正在回应”。

同一 `(project_id, room)` 在所有分支之间最多允许一个活动编辑轮次或管线动作，避免
两个分支并发修改同一本书。输入、重新生成、分支切换和管线按钮在冲突状态下禁用。

## 6. 消息与分支操作

### 6.1 消息显示

- 编辑回复使用安全 Markdown 渲染。
- 支持标题、段落、列表、表格、引用、链接、行内代码和代码块。
- 不启用原始 HTML，不使用 `rehype-raw`。
- 每条消息显示作者/编辑、时间、轮次状态和副作用标记。
- 支持复制；复制失败显示可见错误。
- 作者消息提供“编辑并重新发送”。
- 已完成编辑回复提供“重新生成”。
- 失败、中断或取消轮次提供“重试本轮”。

### 6.2 分支管理

顶部对话工具栏提供：

- 当前版本选择器；
- 新建对话；
- 重命名；
- 归档；
- 搜索当前房间所有版本。

默认选择 `main`。版本标题默认取首条作者消息的前 30 个字符，也可重命名。归档只影响
选择器默认展示，不删除历史；“显示已归档”可以重新打开。对归档版本继续输入会创建
新的未归档子分支。

当前分支 ID 保存在 URL 查询参数 `conversation` 中：

```text
/novels/{project_id}/workspace/{room}?conversation={branch_id}
```

没有该参数时使用 `main`，保证旧书签仍可打开。

## 7. 项目文件引用

输入框提供项目文件搜索按钮和 `@文件` 引用：

- 服务器只列出项目沙箱允许读取的文本文件。
- 每轮最多引用 12 个文件。
- 所有引用内容合计最多 256 KiB。
- 每个路径必须是项目相对路径并通过现有 symlink/`..`/保护目录检查。
- 事件只持久化路径、SHA-256 和大小，不在对话 JSONL 重复保存全文。
- 发送给 Pi 的上下文明确标注为“作者引用的项目资料”，并保留文件边界。
- UI 显示已引用文件标签；作者可以在发送前移除。
- 每轮完成后显示“本轮引用、读取和修改的文件”。

项目外文件、任意上传和 URL 抓取不在本次范围内。

## 8. 工具、工作计划和改动证据

### 8.1 每轮工具记录

所有 `tool_activity`、审批、工作代理结果和管线事件必须带当前 `turn_id`，并显示在该轮
对话下方的折叠活动卡中，而不是只显示底部最近五条。

卡片展示工具名、状态、目标相对路径、面向作者的摘要、开始/结束时间和结果证据。
不得展示模型私有思维链、API Key 或项目外绝对路径。

### 8.2 编辑工作计划

新增自动工具 `update_work_plan`：

- 接受 1–20 条工作项；
- 每项状态只能是 `pending`、`in_progress`、`completed`；
- 同时最多一项 `in_progress`；
- 计划属于当前对话分支和轮次；
- 更新通过 `editor_work_plan_updated` 事件持久化；
- 只描述调查、比较、修改和验证工作，不能包含替作者决定的剧情结论；
- 不进入 `.awp/authoring/plans`，不具有批准或执行权限。

只读 `delegate_project_task` 的开始、证据路径和结论也显示为子任务卡。

### 8.3 Diff 和文件历史

`write`、`edit` 与恢复执行前先在内存中计算 unified diff。重要写审批卡必须显示该 Diff；
普通自动写入也要在完成事件中显示实际 Diff。

每次修改产生不可变 `ProjectMutationReceipt`：

- `change_id`
- `turn_id`
- `branch_id`
- `path`
- `operation`
- `before_hash`
- `after_hash`
- `diff`
- `history_version_id`
- `created_at`

现有 `.awp/file-history/*.json` 继续可读。新历史记录增加稳定版本 ID，但不迁移或覆盖旧
备份。恢复旧版本前必须：

1. 验证当前文件哈希；
2. 展示“当前内容 → 历史内容”的准确 Diff；
3. 通过已有工具审批代理；
4. 把恢复本身保存为一个新版本和新改动事件。

## 9. API 与 WebSocket

### 9.1 REST

新增项目绑定 API：

```text
GET   /awp/api/v1/novels/{project_id}/editor-rooms/{room}/conversations
POST  /awp/api/v1/novels/{project_id}/editor-rooms/{room}/conversations
PATCH /awp/api/v1/novels/{project_id}/editor-rooms/{room}/conversations/{branch_id}
GET   /awp/api/v1/novels/{project_id}/editor-rooms/{room}/conversation-search
GET   /awp/api/v1/novels/{project_id}/project-files
GET   /awp/api/v1/novels/{project_id}/project-files/history
```

创建分支请求包含父分支、分叉事件、标题和 `confirm_effects`。如果分叉点之后存在副作用
且没有确认，返回 HTTP 409，并在 `data.effects` 中提供结构化清单。

搜索词限制 1–200 字符，返回最多 50 条消息摘要。文件搜索返回最多 100 条，不返回
文件内容。

### 9.2 WebSocket

新增主路由：

```text
/awp/ws/v1/novels/{project_id}/editor/{room}/branches/{branch_id}
```

原 `/editor/{room}` 暂时映射到 `main`，用于旧客户端兼容。

`author_message` 增加可选 `references`：

```json
{
  "type": "author_message",
  "client_message_id": "uuid",
  "text": "检查第三章与人物设定是否冲突",
  "references": [{"path": "characters.md"}, {"path": "outline.md"}]
}
```

新增浏览器帧：

```json
{"type": "restore_file_version", "path": "outline.md", "version_id": "opaque", "expected_hash": "sha256"}
```

恢复帧只发起审批；不能在同一帧中携带“自动允许”。审批仍使用现有
`tool_approval_decision`。

所有服务端持久事件包含 `branch_id`，轮次事件包含 `turn_id`。浏览器按
`(branch_id, event_id)` 去重。

## 10. 前端结构

新增或拆分以下职责：

- `ConversationToolbar`：版本、新建、重命名、归档和搜索。
- `MessageCard`：安全 Markdown、复制和消息动作。
- `TurnActivity`：工具、审批、计划、代理、文件改动和状态。
- `ProjectFilePicker`：项目文件搜索和引用标签。
- `ChangesPane`：当前分支工作计划、文件历史、Diff 和恢复入口。

`EditorRoom` 只负责组合这些组件，不继续堆积事件解释逻辑。右侧文档栏由“计划 / 正文 /
批注”扩展为“计划 / 正文 / 批注 / 任务与改动”。窄屏仍以中栏为主，所有新增按钮必须
可通过键盘访问并有中文 `aria-label`。

## 11. 明确不做

- 不提供任意终端或任意 Coding 工具。
- 不提供外部文件上传、云盘、网页搜索或多人协作。
- 不显示 token 数、模型思维链或可调 temperature。
- 不自动合并两个对话分支。
- 不自动撤销弃用分支产生的项目改动。
- 不把编辑工作计划升级为作者计划。
- 不为了实现分支而复制整份对话日志。

## 12. 验收标准

1. 旧项目首次打开仍看到原对话，默认版本为 `main`。
2. 新建、修改重发、重新生成和从旧版本继续都产生独立 Pi 上下文。
3. 任何原历史都未被覆盖；有副作用的分叉必须先显示警告。
4. 服务重启后未完成回复显示“已中断”，不再永久流式。
5. Markdown 表格、列表、代码和复制功能可用，原始 HTML 不执行。
6. 文件选择器不能读项目外、保护目录、数据库、二进制或越界链接。
7. 每轮清楚显示引用文件、工具、代理任务、审批、Diff、计划和最终状态。
8. 文件恢复显示准确 Diff、校验哈希、重新审批并产生新历史版本。
9. 同一房间两个分支不能并发执行编辑或 Writer 管线。
10. 作者不输入技能名或命令，编辑仍会自行使用计划、搜索和项目工具。
11. 作者计划三轮授权边界、Writer 管线和现有工具审批测试继续通过。
12. Python、agent harness、React 单测、生产构建和浏览器端到端验收全部通过。
