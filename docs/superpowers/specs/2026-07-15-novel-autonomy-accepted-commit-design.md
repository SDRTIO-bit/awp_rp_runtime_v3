# 小说自主 NPC：接受后原子提交设计

## 目的

修复自主 NPC 运行时的三个缺口：通用预设被固定故事污染、质量拒绝前已写入议程、议程不能跨章节延续。实现只服务于 Novel Mode；不读取或改动 RP 数据。

## 边界与不变量

1. `autonomous_profile` 缺失时使用兼容默认值；存在但结构、版本或 `mode` 非法时失败。
2. 兼容默认 Profile 只定义通用的中文小说叙事与角色自主性约束，不得包含固定题材、人物、事件、地点或章节编号。项目的具体世界观来自项目配置、账本、人物和章节计划。
3. NPC Planner、Director 与 Writer 运行期间只产生内存态。Writer 仅接收 `VisibleConsequence`，不接收私密议程、理由、知识、资源、截止时间或线程键。
4. 章节只有在 Quality verdict 为 `accept` 时，才提交本轮所有 NPC 变更；`reject` 与降级接受均不得写入 `npc_agenda`、`npc_action`、语义人物状态或记忆。
5. 一次接受后的提交是幂等的：同一章节重试不会复制同一议程或行动。议程更新按 `agenda_id` 覆盖，行动按确定性 ID 覆盖。

## 数据流

```text
已持久化 npc_agenda + 项目上下文
  -> Planner（内存候选：创建/推进/关闭/过期）
  -> Director（最多两个可见后果）
  -> Writer（仅可见后果）
  -> Quality
  -> reject：丢弃本轮 NPC 变更
  -> accept：Curator 原子写入 agenda updates + npc_action + 既有账本/记忆
```

Planner 的候选议程分两类：

- 已有线程：沿用稳定的 `agenda_id` 与 `thread_key`，更新下一步、截止状态或关闭状态；
- 新线程：生成稳定 ID，并在本次接受时写成 active。

Director 选择的条目会同时产生一项 `npc_action` 事实；未选择但仍 active 的议程也会在接受后保存，使它可在后续章节继续被推进。超过 deadline 的条目只在本章被接受后标记 `stale`。

## 组件职责

- `NovelEngine`：收集本轮 Agenda 变更，不得提前调用 ledger store；仅把待提交批次传给 Curator。
- `NpcAgendaService`：从账本解析既有议程，给出 active/stale 判定及待提交更新；不写存储。
- `NovelEvolutionCurator`：在质量接受后一次性写入议程变更与行动事实；拒绝时忽略整批 NPC 变更。
- `NovelProfileCompiler`：把通用 Profile 与项目实际上下文分层编译；不把默认情节注入任何角色提示。

## 错误与降级

- Planner 失败：返回空候选，小说主链继续，且不写议程。
- Profile 缺失：使用通用兼容默认值；非法 Profile：在所有 LLM 调用前报错。
- Director 未选择议程：接受后仍可保存 Planner 产生的 active/closed/stale 变更；不生成 `npc_action`。
- Quality 拒绝：丢弃整个待提交批次，包括过期标记。

## 验收测试

1. 缺失 Profile 的默认值不含固定故事元素，编译产物仅来自给定项目上下文。
2. 质量拒绝后，账本中不存在本轮的 `npc_agenda`、`npc_action` 或 stale 更新。
3. 质量接受后，新 active 议程与已推进/过期议程均持久化；选择的议程额外产生 `npc_action`。
4. 下一章 Planner 能读回已接受但未关闭的 agenda，保持相同 `agenda_id` / `thread_key`。
5. Writer packet 与其序列化形式均不含私密字段。
