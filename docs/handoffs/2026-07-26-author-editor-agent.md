# 专属写作编辑 Agent 交接（2026-07-26）

默认 Pi 交互 Agent 已从“小说命令调度器”改为专属写作编辑。

## 冻结行为

- 作者无需输入技能名；创作意图自动触发 `author-collaboration`。
- 每条作者消息在发给 Pi 前，先写入 `.awp/authoring/journal`。
- 编辑忠于作品与目标读者，不使用空洞奉承，并主动质疑人物、因果、信息和套路风险。
- 素材、计划、批准都有本地来源记录；计划实质修订只增版本、不覆盖历史。
- 计划提出、作者批准、启动 Writer 必须来自三个不同作者轮次。
- 作者轮次使用项目级持久序列；重启 TUI 后不会归零。
- 否定、拒绝、引用命令或含糊表述不能作为批准/执行授权。
- 默认 Pi 没有 Architect 规划或直接写章的绕过工具。
- `AuthorPlanCompiler` 不调用 LLM，不增删场景，只把作者批准计划映射到 `ChapterPlan`。
- 编译章节绑定精确的作者计划 ID、版本和批准哈希；来源缺失、错配或篡改时中止执行。
- author-led 管线不调用 Architect、Director 或自主 NPC 规划，Writer 直接消费作者批准契约。
- Writer 的钩子、对白比例等通用公式在 author-led 模式失效；作者契约优先。

## 工具

默认交互 Host 暴露：

`project_status`、`read_chapter`、`audit_chapter`、`read_authoring_context`、`capture_author_material`、`save_author_plan`、`approve_author_plan`、`execute_author_plan`。

所有写操作由 Python 完成，工具不接受路径或项目 ID。

## 故障恢复

- 日志失败时消息不会发送给 Pi。
- 保存/批准失败时 Agent 收到结构化失败，不得声称成功。
- Writer 失败时批准计划仍保留，不自动改剧情重试。
- Pi Host 失败不回退 legacy；只有显式 `NOVEL_AGENT_RUNTIME=legacy` 才使用旧 NovelBrain。

## 验证

- Python 全量：235 项通过，3 项真实凭据验收跳过。
- Node Harness：17 项通过。
- 小说前端生产构建通过。
- `git diff --check` 与变更 Python 文件 `py_compile` 通过。
