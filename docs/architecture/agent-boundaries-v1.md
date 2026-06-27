# Agent 权限边界 V1

## D1～D6 Agent 总览

| Agent | 代号 | 职责 | 输入 | 输出 | 可用工具 | 能否委派 | 能否写 CardState | 能否写 Memory | 能否写正文 | 运行阶段 | 失败降级 |
|-------|------|------|------|------|----------|----------|------------------|---------------|------------|----------|----------|
| D1 History/Recall | history-recall | 历史证据回查 | RoundSnapshot + recall_focus | AgentSuggestion（历史证据） | rag_memory_lookup, turn_record_lookup | 否 | 否 | 否 | 否 | Wave A | 跳过，无历史证据 |
| D2 Opportunity | opportunity | 戏剧机会识别 | RoundSnapshot + opportunity_context | AgentSuggestion（机会候选） | rag_memory_lookup, active_memory_lookup | 否 | 否 | 否 | 否 | Wave A | 跳过，无机会 |
| D3 World-Life | world-life | 世界活性事件 | RoundSnapshot + world_life_context | AgentSuggestion（世界事件） | rag_memory_lookup, worldbook_lookup | 否 | 否 | 否 | 否 | Wave A | 跳过，无世界事件 |
| D4 Emotion/Relationship | emotion-relationship | 情绪与关系解读 | RoundSnapshot + emotion_context | AgentSuggestion（情绪/关系） | rag_memory_lookup, active_memory_lookup | 否 | 否 | 否 | 否 | Wave A | 跳过，无情绪信号 |
| D5 Continuity | continuity | 连续性约束 | Wave A 标准化产出 + CardState + accepted Turns | ContinuityIssue 列表 | turn_record_lookup, active_memory_lookup | 否 | 否 | 否 | 否 | Wave B（Continuity Barrier 后） | 跳过，仅使用确定性约束 |
| D6 Memory Curator | memory-curator | accepted-turn 后记忆治理 | accepted TurnRecord + 现有 Memory | MemoryCommitPlan | rag_memory_lookup, active_memory_lookup | 否 | 否 | 否（产出 Plan，由 CommitRuntime 执行） | 否 | Post-Commit | 跳过，不执行记忆变更 |

---

## 共同约束

所有 D1～D6 Agent 遵循以下共同约束：

1. **只读**：Agent 不能直接写入任何存储
2. **不可委托**：Agent 不能委派其他 Agent
3. **不可写状态**：Agent 不能写 CardState
4. **不可写记忆**：Agent 不能直接写 ActiveMemory 或 RagMemory
5. **不可写正文**：Agent 不能产出玩家可见正文
6. **有 no-op 路径**：每个 Agent 都有安全的跳过/降级路径
7. **标准化产出**：所有产出通过 Continuity Barrier 标准化为 CandidateSuggestion

---

## 双主 Agent 边界

| Agent | 职责 | 输入 | 输出 | 禁止 |
|-------|------|------|------|------|
| **Director** | 理解玩家意图，规划叙事方向，委派子 Agent | RoundSnapshot | DirectorPlan + DelegationPlan + DirectorResolution | 不输出玩家可见正文，不写状态/记忆 |
| **Writer** | 产出玩家可见 RP 正文 | FinalTurnBrief | WriterDraft | 不使用工具，不委派，不写状态/记忆 |

---

## 工具权限

每个 Agent 的工具权限由 ToolProfile 严格定义：

- `HISTORY_RECALL_TOOLS`：D1 可用工具集
- `OPPORTUNITY_TOOLS`：D2 可用工具集
- `WORLD_LIFE_TOOLS`：D3 可用工具集
- `EMOTION_RELATIONSHIP_TOOLS`：D4 可用工具集
- `CONTINUITY_TOOLS`：D5 可用工具集
- `MEMORY_CURATOR_TOOLS`：D6 可用工具集

工具调用受以下限制：
- 每回合总 Tool Call 上限：max_tool_calls_per_turn（默认 20）
- 单 Agent Tool Call 上限：max_tool_calls_per_agent（默认 5）
- Agent 超时：agent_timeout_ms（默认 30000ms）
- 回合截止：turn_deadline_ms（默认 120000ms）

---

## 预算策略

| 参数 | Simple | Normal | Complex |
|------|--------|--------|---------|
| max_agents_per_turn | 0 | 1 | 4 |
| max_parallel_agents | 0 | 1 | 3 |
| wave_a_max_agents | 0 | 1 | 3 |
| wave_b_max_agents | 0 | 0 | 1 |
| max_tool_calls_per_turn | 0 | 5 | 20 |
| agent_timeout_ms | — | 30000 | 30000 |
| turn_deadline_ms | — | 120000 | 120000 |
