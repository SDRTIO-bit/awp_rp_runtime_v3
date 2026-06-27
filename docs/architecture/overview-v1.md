# 架构总览 V1

## 项目目标

本项目构建一个以 ComfyUI 工作流为编排骨架的 RP 运行时：

- 用确定性状态节点保存"现实到底是什么"
- 用有限且完整的近忆维持叙事连续性
- 用活跃记忆与 RAG 让长期剧情可被找回
- 用两个主 Agent 分担"理解、调度、创作、整合"
- 用可动态委派的独立子 Agent 引入不同视角与创意变量
- 用质量门、状态提交与审计节点保证这些变量不会污染系统事实

> **确定性负责让故事不乱；独立 Agent 的受控自由负责让故事不死。**

---

## 双主 Agent

| Agent | 职责 | 产出 | 禁止 |
|-------|------|------|------|
| **Director**（叙事总控） | 读取 RoundSnapshot，理解玩家意图，生成 TurnBrief 与 DelegationPlan | TurnBrief + DelegationPlan + DirectorPlan | 不输出玩家可见正文，不写状态/记忆 |
| **Writer**（写作节点） | 读取 FinalTurnBrief，产出玩家可见 RP 正文 | WriterDraft | 不使用工具，不委派，不写状态/记忆 |

---

## 确定性状态

**CardState** 是世界变量、事件标志、场景状态的唯一真实来源。

- 只有 `CardStateCommitRuntime` 可以写入
- 所有写入需要：Gate 通过 + Revision 匹配 + 唯一 patchId + 事务原子性
- Agent 不能直接写 CardState

---

## 三层记忆

| 层级 | 内容 | 上限 | 来源 |
|------|------|------|------|
| L1 近忆窗口 | 最近 5 条 accepted TurnRecord（完整，不截断） | 5 条 | `turn_record_store.get_recent` |
| L2 活跃记忆 | 剧情注意力卡片（30-80 字符） | 15 条 | `active_memory_store.recall` |
| L3 RAG 记忆 | 长期可搜索记忆 | 每轮 ≤10 条 | `rag_memory_store.recall` |

---

## 受控动态 Agent

D1～D6 是在双主 Agent 基础上引入的受控动态子 Agent：

| Agent | 代号 | Wave | 位置 |
|-------|------|------|------|
| D1 History/Recall | history-recall | Wave A | Writer 前 |
| D2 Opportunity | opportunity | Wave A | Writer 前 |
| D3 World-Life | world-life | Wave A | Writer 前 |
| D4 Emotion/Relationship | emotion-relationship | Wave A | Writer 前 |
| D5 Continuity | continuity | Wave B | Continuity Barrier 后 |
| D6 Memory Curator | memory-curator | Post-Commit | Quality Gate + Commit 后 |

- Agent 不直接写 CardState
- Agent 不直接写记忆
- Agent 产出的是建议（Suggestion），不是既成事实
- 玩家代理权约束不能被 Agent 覆盖

---

## ComfyUI 工作流可观测性

所有关键步骤都暴露为 ComfyUI 节点：

- 状态初始化、快照、提交
- Director 规划、工具网关、Writer 输出
- 质量检查、修订、执行追踪
- D1～D6 各自的 Trigger / Request / Agent / Validator / Ranker / Result / Diagnostics 节点
- 动态 Agent 调度、Wave 执行、冲突治理、集成追踪

---

## Alpha 当前边界

### 已实现

- 确定性 CardState（SQLite + 事务提交）
- 三层记忆（L1 近忆窗口 + L2 活跃记忆 + L3 RAG）
- 双主 Agent 职责边界（Director / Writer）
- D1～D5 Writer 前受控动态 Agent（Wave A / Wave B）
- D6 accepted-turn 后记忆治理
- 动态 Agent 调度、预算、冲突治理、降级、Trace
- ComfyUI 节点与官方 workflow JSON
- Fake Adapter 集成测试（566 测试全部通过）

### 未承诺

- 生产级真实模型接入体验
- 一键安装即玩的完整 RP 产品
- 完整前端 UI
- 自动世界事件系统
- 无限制多 Agent 自主协作
- 稳定的第三方插件生态兼容性
