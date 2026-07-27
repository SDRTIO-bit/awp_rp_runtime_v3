# 个人小说工作区与持续协作编辑审计交接

日期：2026-07-27

状态：待实施。本文汇总代码审视结论、已确认的缺陷、产品决策和建议的实施顺序，供后续 Claude 会话制定并执行修复计划。

## 1. 已确认的产品决策

这些是后续设计和实现的约束，不应重新退回到旧的多模型状态。

1. 产品定位是个人使用的写作工具，可以公开为代码仓库，但不应把作者小说当作运行时仓库附属数据。
2. 编辑是一个项目级、持续协作的编辑，不是每章独立、彼此失忆的聊天 Agent。
3. 作者保留最终决定权。AI 可以检索、质疑、归纳、保存待确认素材和提出计划；修改正式作品资料、批准计划和启动 Writer 必须按明确审批规则进行。
4. 推荐数据主从关系：

```text
可读项目文件 = 小说作品的唯一真实来源
SQLite          = 可重建的索引、检索、任务和运行元数据
JSONL / .awp    = 对话、审批、AI 操作和版本审计
```

5. 不推荐 SQLite 作为正文的唯一真实来源，也不推荐 event sourcing 作为作品事实来源。

## 2. 目标项目布局

运行时仓库必须可以打开个人目录，而不要求把作品放到仓库的 `novels/` 下。目标项目应接近：

```text
<novel-root>/
  project.json
  outline.md
  world.md
  characters/
    <character>.md
  chapters/
    001-<title>.md
  .awp/
    state.db
    conversations/
    approvals/
    revisions/
    prompt-snapshots/
    runtime/
```

约束：

- 正文、世界观、大纲和角色资料在可读文件中保存，支持 Git diff、任意文本编辑器、同步盘和独立备份。
- SQLite 可删除并从项目文件重建；它不能是唯一保存正文的地方。
- `.awp/` 是可再生或审计性运行数据，不应该是作者唯一保存的作品资料。
- 当前 `novels/*/.novel_cli.json` 扫描模式可作为兼容发现方式，但不能继续是唯一允许的工作区模型或安全边界。

## 3. 最重要的架构收敛

### 3.1 一个项目级编辑，章节是工作焦点

当前实现将 `(project_id, room, branch_id)` 映射到独立持久 Pi Session：

- `book` 是一个 session；
- 每个 `chapter:N` 又是一个 session；
- 每个 branch 还是一个 session。

这导致全书讨论和章节讨论互相失忆。后续改为：

- 一个项目级 Editor Session 保存持续协作记忆；
- `chapter_focus` 只是工作上下文，自动加入该章计划、相邻章节、人物状态、相关账本和待确认项；
- 对话 UI 可以按“全书 / 第 N 章”过滤和组织，但不应默认启动不同的 Agent 心智；
- branch 仅代表作者显式创建的替代性讨论，且必须明确它是否只分叉对话，还是同时建立可隔离的作品草案。

在未实现真正的作品状态分叉前，UI 不得将 branch 表达为可回滚的作品实验环境。

### 3.2 分层的作者审批

建议的审批策略：

| 操作 | 默认策略 |
|---|---|
| 读取项目、章节、搜索、分析 | 自动允许 |
| 保存待确认素材、章节工作笔记 | 自动保存，明确标记未确认 |
| 修改 outline/world/characters/chapters | 显示精确 diff，作者确认 |
| 保存章节计划 | 作者要求收敛后保存为待确认 |
| 批准作者计划 | 后续作者轮次明确批准 |
| 启动 Writer | 再后续作者轮次明确执行 |

不要将“项目文件普通 write”与“正式作品文件修改”混为一类。工具层应按文档类别强制政策，而不只依赖系统提示词要求模型自律。

## 4. 已确认的 P0/P1 缺陷

以下项目已由代码路径确认，优先于新功能或视觉优化。

### P0：错误归属、错误状态或不可用主流程

1. **非 `main` 对话分支会把大量事件写到 `main`。**
   - `EditorSessionManager._emit_event()` 调用 `store.append()` 时遗漏 `key.branch_id`。
   - `complete_editor_message()` 也默认 `main`。
   - 批准、执行、取消、拒绝及 pipeline 相关事件有多处遗漏 `branch_id` 或 `turn_id`。
   - 修复原则：事件写入必须强制接收 `EditorRoomKey` 和活动 `turn_id`；禁止无上下文的默认 main append。
   - 补完整 WebSocket 集成测试：非 main 分支消息、工具、审批、执行、取消、断线回放。

2. **章节 API 存在未定义变量。**
   - `NovelApiHandlers.write_chapter()` 与 `revise_chapter()` 使用未定义的 `project_id` 变量。
   - 旧 `NovelDetail` 的“写作”按钮会经由该路径失败。
   - 修复后补请求级测试，而不是只验证路由注册。

3. **网页创建大纲/项目和 workspace 项目模型脱节。**
   - `POST /novels/plan` 写全局 registry；Web workspace 仅发现 `novels/*/.novel_cli.json`。
   - 规划成功不等于生成可打开的个人工作区。
   - 修复为单一 `create/open workspace` 流程，原子创建项目目录、正式文件、数据库和 manifest。

4. **`delegate_project_task` 的 Python 实现虚报完成。**
   - Python `NovelPiToolService._handle_delegate()` 只发 started/completed 事件，未真正执行 Worker，证据路径恒为空。
   - Node Pi Host 的同名工具却可真正启动只读 Worker，造成同名能力的路径不一致。
   - 修复为统一真实执行结果；若某路径不支持，明确失败而不能返回成功。

5. **文件版本恢复包含必然失败的 placeholder preview。**
   - `restore_file_version()` 调用 `preview("edit", {oldText: "", ...})`，空文本通常不是唯一匹配，且结果未使用。
   - 恢复路径还应补完整 round trip 测试：修改、列版本、恢复、再次恢复、冲突拒绝。

### P1：用户可见的空壳或误导行为

6. **“任务与改动”面板传入硬编码假 turn，无法展示真实改动。**
7. **消息上的编辑、重新生成、重试按钮是空函数。**
8. **全书 room 的顶部“章节编辑室”按钮无法进入章节。**
9. **前端 workspace API 只读取 `body.data.error`，而 conversation API 常返回顶层 `error`；多个 UI 又静默 `catch`。**
10. **取消事件不带活动 `turn_id`，并且 UI 可先标记取消、模型后续仍返回完成。**
11. **WebSocket 回放最多 500 event，超过时可能静默缺失后续事件。**
12. **订阅队列的 128 仅为 soft cap，慢客户端可以积压不可合并事件。**

## 5. 作品数据和版本一致性风险

1. **草稿 revision 有两套不兼容计数器。**
   - 自动 Writer 使用 `ChapterDraft.revision`。
   - 网页 Document Service 使用自己的 document revision，并将其直接作为 `ChapterDraft.revision` 写回。
   - 手工编辑和自动生成交错后可能倒退、冲突或覆盖历史。
   - 必须定义一套章节版本实体；Markdown 内容、生成元数据、审计记录围绕同一个 revision ID 工作。

2. **同一资料存在两套版本历史。**
   - AI sandbox 的 `.awp/file-history`。
   - 网页 Document Service 的 `.awp/versions/documents`。
   - 它们互相不可见，恢复和审计也不一致。
   - 应合并为一个 version/revision 服务，由所有写入路径调用。

3. **文档保存不是跨文件/数据库事务。**
   - canonical 内容与版本 metadata 的写入顺序不同，崩溃可留下半完成状态。
   - 文件为真实来源后，应采用原子文件替换，随后异步/可重建地更新 SQLite；版本记录要能检测并修复不一致。

4. **恢复绕过普通 sandbox 的备份与审计。**
   - 恢复前内容不会自动成为新的可恢复版本。
   - 修复时恢复也应作为普通“写入新 revision”，不能直接调用私有 `_atomic_write()`。

5. **`AuthorMaterial` 缺少 room、chapter、branch、生命周期和吸收状态。**
   - 当前所有待处理素材都混在项目级 inbox。
   - 至少要增加 `scope`、`chapter_index`、`conversation_id`、`status`、`superseded_by` 或等价字段。

6. **同一章多个作者计划缺少明确取代机制。**
   - 枚举有 `SUPERSEDED`，保存新方案时却不自动或显式处理旧方案。
   - UI 应显示“当前可执行方案”和“已替代方案”，Writer 只能接受唯一的已批准计划。

## 6. 运行时、提示词和质量风险

1. **Prompt Studio 保存不会热更新已有 editor session。**
   - 编辑器 prompt 在 Pi Host 初始化时读取；长期 room runtime 仍使用旧 prompt。
   - 产品上至少要显示“新提示词将在重启编辑会话后生效”，并提供明确重启动作。

2. **Prompt snapshot 目前只保存文件，不保证角色运行时实际使用快照内容。**
   - 角色 Host 仍从当前 `.awp/prompts/<role>.md` 读取。
   - `prompt_snapshot_id` 被写入 draft provenance，但实际 prompt 可能已变。
   - 修复为 role task 传递 snapshot 内容或 snapshot ID 并由资源加载器按 snapshot 解析。

3. **角色 Host 丢弃 stderr。**
   - Writer/role 出错后无法给作者或维护者足够诊断。
   - 应保留有限 stderr tail，像 editor bridge 一样随错误提供安全的诊断摘要。

4. **连续性检查和账本更新失败被静默当作成功。**
   - `_check_continuity()` 出错返回空问题列表。
   - `_update_ledger()` 出错直接忽略。
   - 修复为可见降级状态：章节可否接受应有明确策略，至少在 UI、草稿 metadata 和日志里记录“该检查未运行”。

5. **章节修订缺少首次写作时拥有的跨章上下文。**
   - revise 路径将上一章结尾和全书总结传空。
   - 修订可能破坏前后衔接，应复用完整 chapter write packet。

6. **角色筛选仍是占位实现。**
   - write packet builder 当前把全部角色交给 Writer。
   - 长篇下会浪费上下文并增加角色串台；需以出场、关系、章节计划、当前场景和状态筛选。

7. **LLM 配置更改的生效边界未产品化。**
   - 配置 snapshot 隔离已修复，但已有 editor/role bridge 不会自动换模型。
   - UI 需显示会话使用的 config revision，并区分“对新会话生效”与“立即重启”。

## 7. 旧路径和项目边界

1. **旧 `NovelBrain` 仍携带网络抓取、下载器和自主 plan/write。**
   - 这与默认 Pi 编辑的无网络、作者审批边界冲突。
   - 决策建议：将 legacy runtime 完全隔离到显式兼容 CLI；不要继续在 TUI/Web 暴露旧命令或暗含支持。

2. **Legacy 创建项目路径与 workspace 发现路径不一致。**
   - 有 DB 时它可能把新项目创建在当前 DB 目录下。
   - 所有创建项目逻辑应委托同一个 workspace initializer。

3. **Launcher 只要 8188 health 成功就复用服务，不验证服务根或项目可见性。**
   - 可能复用另一个仓库/工作区的旧 server。
   - health 应包含 runtime instance ID、workspace roots 或 launcher 应启动/复用一个显式标识的实例。

4. **SQLite WAL 不等于安全的跨进程协作。**
   - 未见 busy timeout、文件锁策略或双进程写入验收。
   - 个人工具也应明确：默认单 writer；检测到并发时给出可理解错误，而不是裸 `database is locked` 或 HTTP 500。

## 8. 推荐实施阶段

不要一次性重写全部系统。每一阶段都必须通过真实浏览器流程和相关测试，完成前不进入下一阶段。

### 阶段 A：可靠性止血

目标：消除已确认的错误状态和空壳操作。

1. 修 branch/turn 传播、取消语义和完整分支回放测试。
2. 修章节 API 未定义变量。
3. 修文件恢复与统一 mutation receipt。
4. 修真实 Worker 行为或移除虚假工具。
5. 修前端 API 错误解析和静默失败；移除或禁用未实现按钮。
6. 将 ChangesPane 接到真实 editor event state。
7. 对 continuity/ledger 检查失败建立可见降级状态。

验收：主分支、子分支、审批、执行、取消、断线重连、文件恢复和错误反馈都可在浏览器中实际走通。

### 阶段 B：统一个人 workspace 生命周期

目标：任何个人项目目录都能由同一入口创建、打开、移动、备份和恢复。

1. 定义 workspace manifest 和项目目录初始化器。
2. `awp open <path>` / launcher 接受显式个人项目路径。
3. 网页新建项目通过同一初始化器创建真实 workspace，而不是只写全局 DB。
4. `NovelWorkspaceCatalog` 改为接收显式 roots / registry，不再把运行时仓库位置当安全边界。
5. 定义删除策略：默认归档或从列表移除，不删除作品；物理删除必须是显式危险操作。

验收：新建项目、关闭服务、移动项目目录、重新打开、从文件重建 SQLite、再打开均成功。

### 阶段 C：文件优先数据模型

目标：让作者可读文件成为小说正文和设定的唯一真实来源。

1. 建立 canonical Markdown 文件和单一 revision 服务。
2. 合并 sandbox history 与 document history。
3. SQLite 改为索引、搜索、运行 metadata；提供 rebuild 命令。
4. 为每个章节 revision 关联计划、prompt snapshot、质量结果、生成来源和作者修改来源。
5. 清理旧 DB-only output 的双向漂移。

验收：删除/重建数据库后，项目仍可完整阅读、搜索、继续写作，且章节版本连续。

### 阶段 D：持续协作编辑模型

目标：一个项目级编辑，章节为焦点而非隔离人格。

1. 设计 project editor session 和 chapter focus contract。
2. 将项目事实、章节笔记、候选素材、已批准决定分层持久化。
3. 将 branch 重新定义为纯对话分支，或实现真正的作品草案分支；二者必须选其一并写清 UI。
4. 编辑启动时自动获得项目摘要和当前焦点资料，不再要求每次用工具重新拼装基本上下文。
5. 保持作者审批状态机，但让计划和素材具有可追溯来源。

验收：作者可在总线讨论后直接进入某章继续工作，编辑无需重复询问已确认背景；章节讨论的临时方案不会污染全书事实。

### 阶段 E：退役冲突路径

目标：默认产品不再包含与作者审批模型冲突的旁路。

1. 从 Web/TUI 默认界面移除 legacy Brain、下载器和自主写作入口。
2. 保留 legacy 仅作为明确标记的兼容 CLI，或在确认无人使用后删除。
3. 删除不再成立的文档、命令和测试夹具。

## 9. 必须补的验收测试

在阶段 A-D 中，至少实现并持续运行：

1. 浏览器端：创建/打开个人项目、全书对话、章节 focus、分支、审批、执行、取消、重连、错误呈现。
2. 非 main branch 全流程的事件、branch ID、turn ID、回放和副作用提示。
3. 文件改动、版本列表、恢复、冲突、再次恢复的 round trip。
4. Prompt 保存前后：旧会话与新会话分别使用的 prompt 版本；draft provenance 与实际 prompt 内容一致。
5. Writer/continuity/ledger 角色故障时，章节 metadata 和 UI 的明确降级反馈。
6. 自动生成、手工 Markdown 编辑、重建 SQLite 后的章节 revision 一致性。
7. 两个客户端或 CLI/Web 同时写同一项目时的策略与反馈。
8. launcher 命中已有 server、不同 workspace root、项目不可见时的行为。

## 10. 当前工作区注意事项

当前工作区已经存在与先前修复报告相关的未提交改动，涉及 LLM 配置 snapshot、HTTP smoke、CI 和文档。后续实施不得回退或覆盖这些改动；先检查 `git status` 与 `git diff`，将它们与本报告提出的新阶段分开评估。

此前已验证的测试基线记录在 `docs/fix-report-2026-07-27.md`。该报告中的通过结果不能代替本文要求的浏览器端到端验收。

## 11. 不应做的事情

1. 不要先美化 UI，再处理项目/版本/事件真相来源。
2. 不要继续增加仅靠系统提示词约束的正式文件写入；应在工具和数据模型层执行审批规则。
3. 不要把更多功能写进 `NovelBrain` 作为过渡方案。
4. 不要让 Web 新建项目继续只写全局数据库。
5. 不要声称 branch 是作品分支，除非实现作品文件、DB、账本和计划的真实隔离。
6. 不要以“测试通过”为由跳过真实浏览器操作和个人项目目录迁移测试。
