# 冲突治理架构 V1

## 证据优先级

硬约束，不可被 Agent 覆盖：

```
CardState (100)
> accepted TurnRecord (90)
> ActiveMemory (80)
> 高置信 RagMemory (70, confidence ≥ 0.7)
> 当前激活世界书 (60)
> DirectorPlan
> AgentSuggestion
> 无证据推测
```

---

## 硬约束与软 Guidance

### 硬约束（hardConstraints）

- 来自 CardState 的不可变事实
- 来自 accepted TurnRecord 的已发生事件
- 来自 Continuity Agent 的 blocking 问题
- 玩家代理权约束
- Writer 必须遵守，不可忽略

### 软 Guidance（softGuidance）

- 来自 Opportunity / World-Life / Emotion 的建议
- 来自 Director 的叙事方向偏好
- Writer 可以参考，但不强制遵守
- 不能自动变成既成事实

---

## 玩家代理权

- 玩家代理权约束不能被任何 Agent 覆盖
- Agent 不能代替玩家做决定
- Agent 不能强制玩家执行特定动作
- Agent 不能将未发生的事情写入 CardState
- `player_agency_violation` 是 blocking 级别的冲突类型

---

## 事实泄漏防护

以下类型的 Agent 建议不能自动变成既成事实：

- `world_life_fact_leak`：World-Life Agent 的世界事件不能自动写入 CardState
- `opportunity_fact_leak`：Opportunity Agent 的机会候选不能自动写入 CardState
- `emotion_fact_leak`：Emotion Agent 的情绪解读不能自动写入 CardState

这些建议只能作为 Writer 的参考输入，由 Writer 决定是否在正文中体现。

---

## 冲突类型（ConflictKind）

| 类型 | 描述 | 处理 |
|------|------|------|
| `fact_contradiction` | 两个来源对同一事实有矛盾 | 高优先级来源胜出 |
| `state_path_collision` | 两个建议修改同一状态路径 | 高优先级来源胜出 |
| `player_agency_violation` | Agent 试图代替玩家做决定 | 阻止，标记为 blocked_by_player_agency |
| `evidence_priority_override` | 低优先级证据被高优先级覆盖 | 降级为 soft_guidance |
| `temporal_contradiction` | 时间线矛盾 | 高优先级来源胜出 |
| `relationship_boundary` | 关系边界越界 | 阻止或降级 |
| `world_life_fact_leak` | 世界事件泄漏为事实 | 降级为 soft_guidance |
| `opportunity_fact_leak` | 机会泄漏为事实 | 降级为 soft_guidance |
| `emotion_fact_leak` | 情绪解读泄漏为事实 | 降级为 soft_guidance |
| `continuity_hard_block` | 连续性硬阻断 | 阻止，标记为 blocked_by_hard_fact |

---

## Resolution 类型

| 类型 | 描述 |
|------|------|
| `accepted` | 建议被完全采纳 |
| `partially_accepted` | 建议被部分采纳（部分内容降级） |
| `rejected` | 建议被完全拒绝 |
| `downgraded_to_soft_guidance` | 从硬约束降级为软 Guidance |
| `deferred` | 建议被推迟到后续回合 |
| `blocked_by_player_agency` | 因玩家代理权约束被阻止 |
| `blocked_by_hard_fact` | 因硬事实冲突被阻止 |

---

## FinalTurnBrief 裁剪顺序

当 FinalTurnBrief 需要裁剪时，按以下顺序裁剪（从先裁剪到后裁剪）：

1. 低优先级说明
2. 重复软 Guidance
3. 低价值世界活性
4. 低价值机会
5. 必要上下文

### 不得裁剪

- CardState 硬事实
- accepted Turn 窗口
- blocking Continuity Constraint
- 玩家代理权
- Turn Goal
