# RP ComfyUI 双主 Agent、记忆与动态子 Agent 架构记录

**版本：** v0.1（讨论归档 / 后续开发指引）  
**日期：** 2026-06-27  
**定位：** 本文记录当前已经形成的系统级共识，避免“让世界活起来”的关键想法在后续开发中丢失。它不是一次性重构指令，也不替代每一阶段的实施计划、验收报告与测试契约。

---

## 1. 核心结论

本项目的目标不是把一个越来越长、越来越臃肿的提示词交给单一模型；也不是把所有功能都塞进一个万能主 Agent。

目标是构建一个**以 ComfyUI 工作流为编排骨架**的 RP 运行时：

- 用确定性状态节点保存“现实到底是什么”；
- 用有限且完整的近忆维持叙事连续性；
- 用活跃记忆与 RAG 让长期剧情可被找回；
- 用两个主 Agent 分担“理解、调度、创作、整合”；
- 用可动态委派的独立子 Agent 引入不同视角、不同检索路线和不同创意变量；
- 用质量门、状态提交与审计节点保证这些变量不会污染系统事实。

一句话概括：

> **确定性负责让故事不乱；独立 Agent 的受控自由负责让故事不死。**

---

## 2. 系统边界：这是 ComfyUI 工作流，不是酒馆黑箱 Agent

本项目的第一原则是：核心能力要显式存在于节点图里，而不是隐藏在某个 Agent 的长提示词、共享工作区或不可观察的内部循环中。

因此，未来的 RP 工作流应同时拥有两类能力：

1. **确定性节点层**：CardState、条件世界书、事件阶段、记忆读写、质量决策、状态提交、审计。
2. **Agent 推理层**：双主 Agent、动态子 Agent、工具调用、叙事决策、创意建议、写作与修订。

两者不是竞争关系。

- 节点层负责：可验证、可回放、可测试、可持久化的事实和副作用。
- Agent 层负责：理解、联想、判断、选择、调度、叙事表现。

不应照搬“共享工作区里多个 Agent 随便 Patch 同一份正文”的做法。ComfyUI 的优势正是可以把输入、输出、连接、状态写入和副作用边界显式化。

---

## 3. 双主 Agent：不是重复，而是分离两种高负荷工作

本文采用以下工作定义。实际节点名称与模型选择可以在实现阶段调整，但职责边界应保持。

### 3.1 主 Agent-A：叙事总控 / 编排者（Director）

主要职责：

- 读取本轮 Round Snapshot；
- 理解玩家意图、当前局面、人物关系与未解决线索；
- 判断当前回合是否需要工具调用、历史检索、世界书补充或子 Agent 委派；
- 生成本轮叙事意图、限制、重点和可选剧情机会；
- 合并子 Agent 建议，决定采纳、部分采纳或拒绝；
- 生成面向正式写作 Agent 的 Turn Brief；
- 只提出状态变更候选，不直接提交确定性状态。

它的价值不在于写得最长，而在于“知道这轮为什么要这样写”。

### 3.2 主 Agent-B：正式生成 / 整合者（Writer / Reviser）

主要职责：

- 基于 Turn Brief、必要上下文和已采纳建议，完成最终 RP 正文；
- 满足单次至少 1000 字以上的叙事长度和既定格式；
- 维持人物声音、节奏、描写密度与可读性；
- 在需要时对草稿进行一轮受控整合修订；
- 输出可供质量检查、状态提议和记忆提取使用的“最终候选正文”。

它不应承担无限检索、长期数据库翻阅、状态真实写入和多层调度，否则长文创作会被工具噪声、格式要求与状态细节拖垮。

### 3.3 双主 Agent 的共同约束

- 两个主 Agent 读取的事实必须来自同一份 Round Snapshot，不允许各自维护不同版本的“故事现实”。
- 正式正文、状态提议、记忆写入均必须基于通过质量门的最终内容。
- 主 Agent 可以提出建议、调度子 Agent、调用工具；但 CardState 的真正写入权只能属于确定性 Commit 节点。
- 双主 Agent 可以使用同一模型或不同模型；这是路由配置问题，不应改变数据合同。

---

## 4. 四层信息模型：不要把所有东西都叫“记忆”

### 4.1 Layer 0：CardState — 确定性现实

CardState 是唯一的状态真源。它保存：

- 人物身份、名称、关系、位置、已知信息；
- 数值变量、背德值、好感、资源、道具；
- 事件是否触发、事件阶段、条件标志；
- 场景时间、地点、不可被模糊化的事实。

它不应由“模型记忆”“摘要”或 RAG 条目替代。

P4D-1C 已建立 greeting bootstrap 与条件分支求值基础；P4D-2A 已建立严格、原子、带 revision 与 idempotency 的 CardState Commit 基础。后续所有 Agent 能力都必须建立在这条确定性底座之上。

### 4.2 Layer 1：最近 5 个完整 TurnRecord — 近忆

当前共识：主 Agent 的连续对话历史只保留**最近 5 个已接受回合**，并且每个回合必须保存完整原文。

一个 TurnRecord 只包括：

- 玩家该回合原始输入全文；
- 通过质量门、被最终接受的 AI 正文全文；
- 最小必要元数据，例如 turnId、时间、CardState revision、是否为 continue/retry。

明确禁止混入：

- 草稿；
- 被拒绝或重试失败的文本；
- 子 Agent 内部推理；
- 工具原始 JSON；
- 中间格式修复版本。

“保存 5 回合”不等于“提示词里按 token 再裁剪成残片”。存储层必须保留 5 个完整 TurnRecord；上下文不足时，先削减 RAG、世界书扩展、工具原始回包与附加说明，而不是悄悄把第五回合截断。

### 4.3 Layer 2：活跃模糊记忆 — 固定 15 条剧情注意力槽位

活跃记忆不是状态真相，也不是冗长摘要。它是 15 张可更新、可淘汰的“剧情注意力卡”。

应优先保存：

- 未兑现承诺；
- 未解决冲突；
- 关系正在变化的方向；
- 仍有效的秘密、误会与伏笔；
- 影响人物行为的情绪趋势；
- 玩家明确目标及尚未完成的行动。

每条建议控制在 30–80 个中文字，并携带来源回合、实体、重要度、状态版本、是否已解决等元数据。示例：

```json
{
  "memoryId": "mem_042",
  "type": "unresolved_promise",
  "content": "主角答应在三日后的雨夜前往后院，与林婉单独见面；该约定尚未兑现。",
  "entities": ["player", "linwan"],
  "importance": 0.93,
  "sourceTurnId": "turn_18",
  "stateVersion": 27,
  "status": "active"
}
```

### 4.4 Layer 3：长期 RAG 记忆库 — 可检索的旧剧情

长期记忆库保存较久远的事件、关系发展、对话片段、已发生但仍可能被回收的线索。它在体验上可以像“动态世界书条目”，但必须具备更完整的元数据和过期机制。

建议字段：

- cardId、sessionId；
- 实体与别名标签；
- 事件标签、地点标签、时间范围；
- sourceTurnId；
- 写入时的 CardState revision；
- 可信度、重要度、是否已解决、是否已过期；
- 可供审计的来源证据。

检索优先级：

```text
CardState 硬事实
  > 最近 5 回合完整原文
  > 活跃 15 条剧情记忆
  > 高置信、相关的 RAG 召回
  > 普通世界书背景
```

RAG 绝不能反过来覆盖 CardState。历史记忆只提供“提醒”和“联想”，不改写当前现实。

---

## 5. 子 Agent 的“自由”到底是什么

这里的自由不是给子 Agent 无限制写状态、修改正文或随机编造设定。

真正要保留的是：

> **独立模型、独立上下文视角、独立工具路径、独立思考结果所带来的叙事变量。**

子 Agent 可以是不同模型，也可以使用与主 Agent 不同的系统提示词、工具预算和检索策略。DeepSeek Flash 等低成本模型很适合承担其中相当一部分任务：它们在短上下文、明确目标、结构化工具合同和有限工具循环下，往往会给出高性价比的结果。

### 5.1 子 Agent 不应被压缩成“固定 Critic 节点”

系统不必预先固定“逻辑 Agent、文风 Agent、格式 Agent”三个人每回合都运行。更有价值的方式是：主 Agent-A 按本回合局面临时定义任务。

可能出现的动态角色包括：

| 动态角色 | 主要问题 | 可调用能力 | 典型产出 |
|---|---|---|---|
| History / Recall Agent | 有没有被遗忘但值得呼应的旧剧情？ | RAG、时间线、历史检索 | 旧承诺、旧物件、旧对话的回收建议 |
| Opportunity Agent | 当前局面有什么意外但合理的推进？ | 关系、事件、活跃记忆、世界书 | 1–3 张剧情机会卡 |
| World-Life Agent | 世界在主角视线之外可能发生什么？ | 场景、NPC、事件阶段、世界书 | 不强制发生的环境变化候选 |
| Emotion / Relationship Agent | 人物是否太理性、太平、缺少暗流？ | 关系状态、角色资料、最近文本 | 动作、停顿、误会、克制等建议 |
| Continuity Agent | 人物位置、知识边界、时间线是否冲突？ | CardState、近忆、事件与 RAG | 可证据化的问题列表 |
| Memory Curator Agent | 本轮哪些内容值得进入活跃记忆或 RAG？ | 最终正文、状态变更摘要 | 记忆候选与标签 |

这些 Agent 的价值不仅是找错，更是提供主 Writer 原本没有想到的角度。它们让叙事从“模型按当前输入线性续写”变成“世界会回忆、会联想、会暗自酝酿”。

### 5.2 允许能力，不允许越权

子 Agent 不应因为“安全”而被做成只能返回一句 Yes/No 的弱检查器。它可以：

- 读取完整授权的任务胶囊；
- 自主决定在预算内如何组合工具调用；
- 根据上一次工具结果改写下一次查询；
- 返回具有新意的建议、证据、检索线索和可选叙事机会；
- 给出候选状态变化，但只能作为 proposal。

但 V1 必须保留以下边界：

- 不直接写 CardState；
- 不直接写长期记忆库；
- 不直接提交最终正文；
- 不直接修改其他 Agent 的共享文件；
- 不允许子 Agent 再嵌套委派孙 Agent；
- 不允许未经 Gate 的文本触发副作用。

这不是牺牲能力，而是把“创造权”和“提交权”分开。

---

## 6. 建议的 ComfyUI 工作流形态

以下节点名是架构占位名；现有节点可以通过适配器逐步接入，不要求一次性重写旧骨架。

```text
玩家输入
  ↓
AWPCardStateInit / CardState Load
  ↓
条件世界书 / 事件阶段 / 角色资料 / 记忆读取
  ↓
AWPRoundSnapshot（统一且可审计的本轮事实包）
  ↓
主 Agent-A：Director
  ├─ 工具调用：状态查询、世界书查询、RAG、时间线、事件查询
  ├─ 生成：Turn Brief + Delegation Plan
  └─ 判断：本轮是否值得调用动态子 Agent
  ↓
AWPDynamicSubAgentPool（0–N 个独立子 Agent，可并发）
  ↓
AWPSuggestionMerge（建议、证据、冲突、采纳候选）
  ↓
主 Agent-B：Writer / Reviser
  ↓
Quality / Identity / Scene / Length / Format 检查
  ↓
AWPStateUpdateProposal（候选状态补丁，尚未写入）
  ↓
AWPSideEffectDecision
  ↓
AWPCardStateCommit（唯一确定性状态写入点）
  ↓
TurnRecord Commit + Active Memory Commit + RAG Memory Write
  ↓
向玩家输出最终正文
```

关键不是节点数量，而是“每条数据在哪里生成、谁有权写入、失败时是否会污染后续回合”都能看见。

---

## 7. 最小数据合同

### 7.1 Round Snapshot

`awp.rp.round-snapshot.v1` 至少包含：

- session/card/turn 标识与 CardState revision；
- 当前玩家输入；
- 最近 5 个完整 TurnRecord；
- 当前 CardState 的受控摘要或读取句柄；
- 当前激活条件世界书；
- 活跃 15 条记忆；
- 已检索 RAG 条目及 provenance；
- 当前场景、角色、事件阶段；
- 预设、长度、格式、模型与预算配置。

### 7.2 Delegation Plan

`awp.rp.delegation-plan.v1` 应明确：

```json
{
  "mode": "history_and_opportunity",
  "reason": "本轮涉及旧约定、多人场景和一条未解决秘密。",
  "tasks": [
    {
      "role": "history_recall",
      "goal": "检索可能自然呼应当前输入的旧剧情。",
      "toolScopes": ["memory.search", "timeline.read"],
      "maxToolCalls": 3,
      "maxResultTokens": 700
    },
    {
      "role": "opportunity_scout",
      "goal": "提出不改变既有事实的意外但合理推进。",
      "toolScopes": ["state.read", "event.read", "worldbook.read"],
      "maxToolCalls": 3,
      "maxResultTokens": 700
    }
  ]
}
```

### 7.3 子 Agent 建议

`awp.rp.agent-suggestion.v1` 至少包含：

- 建议类型；
- 内容；
- 重要度与风险；
- 证据来源；
- 适用约束；
- 可选的“不要做什么”；
- 可选 state patch proposal，但不得有 commit 权限。

### 7.4 状态提交

CardState 继续沿用 P4D-2A 的核心原则：

- Candidate Patch 先经过 Quality / SideEffect Gate；
- 严格路径与 operation 语义；
- 事务、revision、patchId、idempotency；
- 任一非法 operation 整批拒绝；
- 唯一 store writer 是 `AWPCardStateCommit`。

---

## 8. 提示词与缓存策略

缓存命中主要降低成本和延迟，不会减少模型对长上下文的注意力负担。因此，5 回合完整近忆仍然必须被认真控制，不能以“有缓存”为理由无限堆叠。

建议的 Prompt 排列：

```text
【稳定前缀，利于缓存】
1. 系统规则与安全边界
2. 工具定义与调用协议
3. 预设 / 文风 / 输出格式
4. 角色静态资料与常驻世界观

【动态尾部】
5. 当前 CardState 摘要
6. 最近 5 个完整 TurnRecord
7. 活跃 15 条模糊记忆
8. RAG 动态召回
9. 子 Agent 已采纳建议
10. 当前玩家输入
11. 本轮 Turn Brief
```

工具原始回包不进入五回合近忆。应保存在运行审计中，或被压缩为状态事实、记忆候选和可读摘要。

---

## 9. 当前 P4D 基础与不可倒退项

### 已具备的基础

- **P4D-1C**：条件条目按 branchGroupId / branchOrder 处理 first-match-wins；greeting 初始 Patch 支持通用 bootstrap 优先级；已有状态不会被 greeting 覆盖。
- **P4D-2A**：`AWPCardStateCommit` 建立严格提交语义；支持 gate 拒绝、revision 检查、idempotent replay、patchId 冲突检测、事务原子性与 patch log。

### 仍未完成的关键项

- `AWPStateUpdateProposal`：由 Agent / LLM 产生候选状态补丁，替换外部 JSON 占位输入；
- LLM State Updater 的真实链路；
- curator live JSON 写入修复；
- 复杂 EJS 语义；
- 记忆、RAG、工具与双主 Agent 的正式工作流接入；
- 动态子 Agent Pool、建议合并、模型路由与可观测性。

### 不可倒退的约束

- 不因新增 Agent 功能绕过 `AWPCardStateCommit`；
- 不让记忆库覆盖 CardState；
- 不让失败/拒绝文本写进正式近忆、长期记忆或状态；
- 不用一个“万能 Agent”偷偷替代条件、状态、事件、提交节点；
- 不为了接入新能力破坏旧卡、旧存档、旧世界书格式与既有运行骨架；新增能力优先通过节点、适配器、feature flag 与新工作流模板接入。

---

## 10. 开发路线：先让现实可靠，再让世界活起来

### Phase A：完成确定性状态闭环（当前优先）

1. 实现 `AWPStateUpdateProposal`；
2. 让 LLM / Agent 只能产生 Candidate Patch；
3. 接入现有 Quality Gate 与 `AWPSideEffectDecision`；
4. 由 `AWPCardStateCommit` 作为唯一 writer 完成提交；
5. 补齐 accepted / rejected / retry / stale / replay 的端到端回归。

### Phase B：完成记忆三层结构

1. 建立完整 `TurnRecord` 存储与“最近 5 回合绝不裁剪”测试；
2. 建立 15 条活跃记忆的确定性选择、去重、淘汰与版本追踪；
3. 建立长期 RAG Memory 写入、检索、过滤与 provenance；
4. 建立“CardState 优先于任何记忆”的冲突处理；
5. 完成新建会话、继续、重试、回滚的记忆边界。

### Phase C：完成双主 Agent 与工具网关

1. 建立 `RoundSnapshot`；
2. 建立主 Agent-A 的工具调用协议和调度输出；
3. 建立主 Agent-B 的正式写作 / 整合输入；
4. 所有工具通过统一网关记录：输入、结果摘要、耗时、调用次数、失败原因；
5. 做模型路由：高价值理解/整合可用较强模型，短任务、检索规划、记忆整理、检查与灵感任务优先使用低成本模型。

### Phase D：接入动态子 Agent，提供“可控的意外性”

1. 先做 History / Recall Agent；
2. 再做 Opportunity Agent 与 World-Life Agent；
3. 再做 Emotion / Relationship Agent、Continuity Agent、Memory Curator Agent；
4. 支持主 Agent-A 动态生成 Delegation Plan；
5. 默认允许 0 个子 Agent，复杂回合允许有限并发；V1 禁止嵌套委派；
6. 所有建议进入 Suggestion Merge，最终仍由主 Agent-A / 主 Agent-B 选择。

### Phase E：评估、基准与玩家模式

- 快速模式：最少 Agent、最低延迟；
- 质量模式：启动有限审稿 / 修订；
- 剧情模式：允许 History / Opportunity / World-Life 等创意变量；
- 针对至少 1000 字回合，统计成本、时延、格式失败率、角色身份错误、状态冲突、记忆召回质量与剧情新颖度；
- 将“子 Agent 是否真的带来更活的剧情”做成可比较的基准，而不是只凭感觉判断。

---

## 11. 验收标准：怎样证明它真的在工作

### 状态与记忆

- 新建会话不会复用旧 session 的近忆、RAG 或 CardState；
- 最近 5 个 TurnRecord 在保存与再读取时逐字完整；
- 被拒绝的草稿、重试失败文本和工具原始输出不会进入近忆；
- 15 条活跃记忆可解释其保留、合并、淘汰原因；
- RAG 召回与 CardState 冲突时，CardState 始终获胜；
- 任一状态更新只能经过 Gate 与 `AWPCardStateCommit`。

### 双主 Agent 与子 Agent

- 主 Agent-A 能明确给出本轮是否委派、为什么委派、调用了谁；
- 子 Agent 可在授权范围内进行多步工具调用，而不是只做固定单次检查；
- 子 Agent 输出既能发现冲突，也能提出合理的叙事机会；
- 子 Agent 不具备直接提交状态、直接写长记忆、直接覆盖正文的路径；
- Writer 最终输出能引用被采纳的建议，但不会把建议清单暴露给玩家；
- 每一条“意外推进”可以追溯到状态、历史、世界书或子 Agent 建议，而不是不可解释的随机漂移。

---

## 12. 最后定稿的原则

本项目不要追求一个永远正确、永远按直线续写的死板系统；那样虽然安全，却会让 RP 失去“世界真的在流动”的感觉。

但也不要用自由 Agent 群替代事实、状态和提交机制；那样短期看似热闹，长期一定会把名字、关系、事件与变量写乱。

最终目标应当是：

> **CardState 让世界有骨头；近忆、活跃记忆与 RAG 让世界有记性；双主 Agent 让世界能理解和表达；动态子 Agent 让世界偶尔想起、联想到、发生意料之外但仍然合理的事。**

这份文档将“让一潭死水活起来”的想法保留下来。当前开发恢复时，先完成确定性状态与记忆底座；动态子 Agent 不被取消，而是作为建立在可靠现实之上的下一层能力。
