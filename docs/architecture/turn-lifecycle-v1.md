# 完整回合生命周期 V1

## 完整主链

```
Player Input
→ CardState / Memory / Worldbook Context
→ RoundSnapshot
→ DirectorPlan
→ DelegationPlan
→ Dynamic Agent Scheduler
→ Wave A (D1～D4 并发)
→ Continuity Barrier
→ D5 Continuity (Wave B)
→ Conflict Governance
→ Director Suggestion Resolution
→ FinalTurnBrief
→ Writer / Reviser
→ Quality Gate
→ State Proposal
→ CardState Commit
→ TurnRecord Commit
→ D6 Memory Curator
→ Deterministic Memory Commit
→ Completed Turn
```

---

## Writer 前执行链

### 1. Snapshot 阶段

- 加载或初始化 CardState
- 加载最近 5 条 TurnRecord（L1 近忆窗口）
- 加载活跃 15 条记忆（L2）
- 加载 RAG 召回（L3）
- 加载条件世界书
- 构建冻结的 RoundSnapshot

### 2. Director 阶段

- 读取 RoundSnapshot
- 理解玩家意图
- 产出 DirectorPlan（结构化叙事意图、目标、约束）
- 产出 DelegationPlan（委派哪些子 Agent）

### 3. Dynamic Agent Scheduler 阶段

- 根据 DelegationPlan 与预算策略，决定本轮启用哪些 Agent
- 确定性排序：history-recall (1.0) > continuity (0.95) > emotion-relationship (0.7) > opportunity (0.6) > world-life (0.5)
- 超预算时确定性跳过，记录跳过原因

### 4. Wave A 阶段

并发执行（受预算限制）：

| Agent | 触发条件 | 产出 |
|-------|----------|------|
| D1 History/Recall | 历史回查触发策略 | AgentSuggestion（历史证据） |
| D2 Opportunity | 戏剧机会触发策略 | AgentSuggestion（机会候选） |
| D3 World-Life | 世界活性触发策略 | AgentSuggestion（世界事件） |
| D4 Emotion/Relationship | 情绪关系触发策略 | AgentSuggestion（情绪/关系） |

每个 Agent 只读、不可委托、不可写状态/记忆。
产出标准化为 CandidateSuggestion（suggestion_id, role, kind, priority, confidence, summary, recommendations, evidence_refs, risk_flags）。

### 5. Continuity Barrier 阶段

- 等待 Wave A 全部完成
- 标准化所有 Agent 产出
- 只传递结构化摘要，不传递原始思维链/工具输出/系统 Prompt

### 6. Wave B 阶段（D5 Continuity）

- 读取 Wave A 标准化产出 + CardState + accepted TurnRecord
- 检测连续性问题（时间线、地点、知识边界、秘密暴露风险）
- 产出 ContinuityIssue 列表

### 7. Conflict Governance 阶段

- `SuggestionConflictGovernor` 检测所有建议间的冲突
- 证据优先级：CardState (100) > accepted Turn (90) > ActiveMemory (80) > RAG (70) > worldbook (60) > DirectorPlan > AgentSuggestion > 无证据推测
- 冲突类型：fact_contradiction, state_path_collision, player_agency_violation, evidence_priority_override, temporal_contradiction, relationship_boundary, world_life_fact_leak, opportunity_fact_leak, emotion_fact_leak, continuity_hard_block
- Resolution 类型：accepted, partially_accepted, rejected, downgraded_to_soft_guidance, deferred, blocked_by_player_agency, blocked_by_hard_fact

### 8. Director Suggestion Resolution 阶段

- `DirectorSuggestionResolutionRuntime` 结构化输出：
  - accepted_suggestion_ids
  - partially_accepted_suggestion_ids
  - rejected_suggestion_ids
  - rejection_reasons
  - hard_constraints
  - soft_guidance
  - writer_priorities
  - player_agency_guards
  - evidence_refs
- Director 不直接输出玩家可见正文

### 9. FinalTurnBrief 阶段

- 裁剪后的 Writer 输入
- 裁剪顺序：先低优先级说明 → 重复软 Guidance → 低价值世界活性 → 低价值机会 → 必要上下文
- 不得裁剪：CardState 硬事实、accepted Turn 窗口、blocking Continuity Constraint、玩家代理权、Turn Goal

---

## Writer / Quality / Commit

### 10. Writer / Reviser 阶段

- 读取 FinalTurnBrief
- 产出玩家可见 RP 正文
- 不使用工具，不委派，不写状态/记忆
- Reviser 根据 QualityPipeline 反馈修订

### 11. Quality Gate 阶段

- 确定性检查（长度、格式、无 JSON）
- LLM 质量检查（可选）
- 决策：accept / revise / reject
- reject = 零副作用

### 12. State Proposal 阶段

- 从 accepted 文本生成 StateUpdateProposal
- 这是候选 patch，尚未提交

### 13. Commit 阶段

- `CardStateCommitRuntime`：应用状态变更（revision 检查、幂等）
- `TurnRecordCommitRuntime`：保存 accepted turn record

---

## D6 的 post-accept 位置

```
QualityGate(ACCEPT) → CardStateCommit(SUCCESS) → TurnRecordCommit(SUCCESS)
    → MemoryCurationTriggerPolicy → MemoryCurationRuntime
    → MemoryPlanCompiler → ActiveMemoryCommit + RagMemoryCommit
```

- D6 永远不在 Writer 前 DynamicSubAgentPool 中
- D6 永远不参与 SuggestionMerge
- D6 永远不影响当前回合已经写出的正文
- D6 只读取 accepted turn

---

## retry / resume / idempotency

- Writer 前 Agent 全部只读，可在相同 snapshot 下安全重跑
- D6 MemoryCommit 保持幂等（idempotency_key = turn_id:memory_commit_id）
- retry 不得重复创建 ActiveMemory / RagMemory
- 已 accepted 的 TurnRecord 不得重复提交
- CardState patch 不得重复提交
- 最大重试次数：3 次
