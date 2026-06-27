# 记忆治理架构 V1

## 三层记忆

| 层级 | 合同 | 上限 | 来源 | 描述 |
|------|------|------|------|------|
| L1 近忆窗口 | AcceptedTurnWindow | ≤5 条完整 accepted TurnRecord | `turn_record_store.get_recent` | 完整回合记录，永不截断 |
| L2 活跃记忆 | ActiveMemoryRecord | ≤15 条 per card+session | `active_memory_store.recall` | 剧情注意力卡片（30-80 字符） |
| L3 RAG 记忆 | RagMemoryRecord | ≤10 条 per round（可配置） | `rag_memory_store.recall` | 长期可搜索记忆（FTS5 + LIKE fallback） |

---

## 优先级顺序（硬约束，不可被 LLM 覆盖）

```
CardState 硬事实
> 最近 5 条完整 accepted TurnRecord (L1)
> ActiveMemory (L2)
> 高置信 RAG (L3, confidence ≥ 0.7)
> 普通 RAG
> 世界书背景
```

---

## accepted-only 原则

- 只有 Quality Gate accepted 的回合才能进入记忆系统
- rejected 或 draft 回合不产生记忆写入
- TurnRecord 的 `turn_index` 在 cardId+sessionId 内严格递增
- 每条 TurnRecord 记录 `base_card_state_revision`（提交前）和 `result_card_state_revision`（提交后）

---

## D6 触发条件

D6 Memory Curator 仅在以下条件全部满足时触发：

1. Quality Gate 决策为 `accept`
2. `CardStateCommitRuntime` 成功
3. `TurnRecordCommitRuntime` 成功
4. `MemoryCurationTriggerPolicy` 判定需要记忆治理

D6 不在 Writer 前 DynamicSubAgentPool 中。
D6 不参与 SuggestionMerge。
D6 不影响当前回合已经写出的正文。

---

## MemoryCommitPlan

D6 产出 `MemoryCommitPlan`，包含：

- 新增 ActiveMemory 条目
- 更新现有 ActiveMemory 条目
- 淘汰过期 ActiveMemory 条目
- 新增 RagMemory 条目
- 更新现有 RagMemory 条目

MemoryCommitPlan 由 `ActiveMemoryCommitRuntime` 和 `RagMemoryCommitRuntime` 执行。

---

## 幂等、retry、degraded、pending

### 幂等

- `idempotency_key = turn_id:memory_commit_id`
- 相同 idempotency_key 的重复提交返回相同结果
- 不会重复创建 ActiveMemory / RagMemory

### retry

- D6 失败不影响已 accepted 的回合输出
- retry 不重复提交已成功的记忆变更
- 最大重试次数：3 次

### degraded

- 当 D6 超时或失败时，进入 degraded 模式
- degraded 模式下跳过非关键记忆操作
- 已 accepted 的回合输出不受影响

### pending

- 当记忆操作需要等待外部资源时，进入 pending 状态
- pending 状态的记忆操作在下次回合开始前完成或超时

---

## 记忆冲突判定

确定性冲突判定（不依赖 LLM）：

- `ConflictSignal{entity_refs, negated_terms, reason}` → 实体重叠 + 否定词 → `conflicted` / `ignored`
- `source_card_state_revision < current.revision` → `stale`（降级）
- CardState 始终优先 — 无 LLM 判断

---

## 记忆保留优先级

当活跃记忆达到上限（15 条）时，淘汰优先级：

```
promise (0.95) > secret (0.90) > relationship_shift (0.85) > misunderstanding (0.82)
> player_goal (0.78) > scene_pressure (0.72) > unresolved_thread (0.70)
```

低优先级记忆被淘汰，为高优先级记忆腾出空间。
