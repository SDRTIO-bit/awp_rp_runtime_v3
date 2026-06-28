# 持久化 RP 完整管线 — 使用指南

## 概述

三步骤工作流，通过 ComfyUI `/prompt` 接口执行，所有状态持久化到 SQLite。

```
Step 1: Bootstrap（一次）  →  导入角色卡，建立 session
Step 2: First Turn（一次）  →  第一回合，从 SQLite 加载上下文
Step 3: Continuation Turn（N次）→  后续回合，仅需 sessionId + 玩家输入
```

### 核心特性

- **完全持久化**：所有状态（CardState、TurnRecord、Memory、Trace）写入 SQLite
- **ComfyUI 重启安全**：重启后用相同 sessionId 即可恢复
- **L1/L2/L3 记忆系统**：回合历史 + 活跃记忆 + RAG 全文检索
- **世界书检索**：角色卡世界书条目自动绑定和激活
- **D1-D5 子 Agent**：确定性触发规则，自动调度
- **D6 记忆策展**：每回合自动评估长期记忆价值
- **Quality Gate**：1000 字最低门槛，分级诊断
- **Writer 自检修订**：字数/禁词/格式/转述检查，最多 2 次修订
- **安全投影**：TurnResultProbe 仅输出元数据，不含完整文本

---

## 模型分配

| 角色 | 模型 | Profile ID | 说明 |
|------|------|-----------|------|
| Director（规划） | deepseek-v4-flash | `deepseek-v4-flash-writer` | 400B，轻量规划 |
| Writer（出文） | deepseek-v4-pro | `deepseek-v4-pro-director` | 1.6T，高质量叙事 |
| D1-D5 子 Agent | 确定性规则 | — | 0 API 调用，纯正则触发 |
| D6 Memory Curator | 确定性规则 | — | 0 API 调用，规则引擎 |
| Quality Gate | 确定性规则 | — | 0 API 调用 |

> 注意：Profile 名称含 "director"/"writer" 是历史遗留。实际使用中：Flash 做规划，Pro 出文章。

### 预备条件

1. ComfyUI 运行中（`http://127.0.0.1:8188`）
2. 环境变量 `DEEPSEEK_API_KEY` 已设置
3. 角色卡 JSON 文件位于可访问路径
4. 可选：`AWP_REAL_LLM_E2E=1`，`AWP_ALLOW_EXTERNAL_CARD_CONTENT=1`

---

## Step 1：Bootstrap（导入角色卡，建立 Session）

### 工作流文件

`workflows/api/persistent_rp_bootstrap.json`

### 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `source_path` | 角色卡 JSON 的绝对路径 | `C:/Users/.../角色卡.json` |
| `session_id` | 唯一 session 标识 | `my-story-001` |
| `greeting_id` | 开场白编号（g0/g1/g2...） | `g2` |
| `request_id` | 请求 ID（可选） | `req-bs-001` |
| `run_id` | 运行 ID（可选） | `run-001` |

### 执行

```bash
curl -X POST http://127.0.0.1:8188/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": <workflow JSON>, "client_id": "my-client"}'
```

### 内部流程

```
source_path → CardSourceLoad → CardPayloadParse → CardSecurityScan
→ CardNormalize → CardDefinition → Bootstrap Pipeline
→ CardSessionBinding + OpeningRecord + WorldbookBinding → SQLite
```

### 产出（写入 SQLite）

- `card_definitions`：角色定义（1 条）
- `card_session_bindings`：session 绑定（1 条）
- `opening_records`：开场白（1 条）
- `worldbook_bindings`：世界书绑定（1 条）
- `card_states`：初始 CardState（revision=0）

**记录 `session_id`，后续回合需要。**

---

## Step 2：First Turn（第一回合）

### 工作流文件

`workflows/api/persistent_rp_first_turn.json`

### 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `session_id` | Bootstrap 中使用的 ID | `my-story-001` |
| `player_input` | 你的发言 | `（推开门）语晴，俊伟今晚加班...` |
| `director_profile_id` | 规划模型 | `deepseek-v4-flash-writer` |
| `writer_profile_id` | 出文模型 | `deepseek-v4-pro-director` |
| `writer_preset_path` | 文风预设 | `kedai_heavy_v1`（空=不使用） |
| `turn_id` | 回合 ID（可选，自动生成） | — |
| `trace_id` | 追踪 ID（可选，自动生成） | — |

### 内部流程

```
SessionRuntimeLoad:
  ├─ card_session_binding  ← SQLite
  ├─ card_state            ← SQLite
  ├─ opening_record        ← SQLite
  └─ worldbook_binding     ← SQLite

RoundSnapshotBuilder:
  ├─ L1 回合历史（首回合为空）
  ├─ L2 活跃记忆召回（首回合为空）
  ├─ L3 RAG 记忆召回（首回合为空）
  └─ 世界书条目激活（40 条）

Director（Flash 400B）:
  └─ 生成 DirectorPlan（turn_goal, scene_focus, constraints, opportunities）

D1-D5 Trigger Policies（确定性规则）:
  ├─ D1 History Recall: "之前/约定/秘密/还记得" 关键词触发
  ├─ D2 Opportunity: 叙事机会检测
  ├─ D3 World Life: 环境/NPC/时间信号
  ├─ D4 Emotion Relationship: 关系变化/情感波动
  └─ D5 Continuity: 事实冲突/知识边界/时间线

Writer（Pro 1.6T + Preset）:
  ├─ WriterInputBundle（含 Agent 建议 + 世界书上下文）
  ├─ 第一轮生成
  ├─ 自检循环（字数/禁词/格式/转述）× 最多 2 次
  └─ 最终文本

Quality Gate:
  ├─ ≥ 1000 字 → accept
  ├─ 800-999 字 → warning（accept）
  ├─ 500-799 字 → revise
  └─ < 500 字 → reject

Commit:
  ├─ CardState (revision++)
  ├─ TurnRecord (writer_output)
  └─ D6 Memory Curator → L2 活跃记忆 + L3 RAG 记忆

TurnResultProbe:
  └─ 安全投影 → /history（不含完整文本，仅元数据）
```

### 产出（写入 SQLite）

- `turn_records`：第 1 回合记录（1 条，含完整 writer_output）
- `card_states`：revision 0→1
- `active_memory_records`：L2 记忆（如 D6 判定有价值）
- `rag_memory_records`：L3 记忆（如 D6 判定有价值）
- `execution_traces`：执行追踪（1 条，含所有阶段事件）

---

## Step 3：Continuation Turn（后续回合）

### 工作流文件

`workflows/api/persistent_rp_continuation_turn.json`

### 输入参数

| 参数 | 说明 |
|------|------|
| `session_id` | 同上 |
| `player_input` | 当前发言 |
| 其他 | 同 First Turn |

**与 First Turn 的区别：**

- 无 Bootstrap——所有上下文从 SQLite 恢复
- L1 包含历史回合
- L2/L3 包含已策展记忆
- 世界书持续激活

### 可无限复用

同一个 `persistent_rp_continuation_turn.json` 可用于第 2、3、...、N 回合。

---

## /history 输出解读

每个回合完成后，查询 `/history/{prompt_id}`。`AWPV2TurnResultProbe` 输出在 `outputs.*.ui.awp_turn_result_json`：

```json
{
  "turn_id": "t1-...",
  "session_id": "my-story-001",
  "turn_index": 5,
  "turn_kind": "continuation",
  "quality_status": "accept",
  "idempotency_status": "fresh",
  "card_state_revision_before": 4,
  "card_state_revision_after": 5,
  "accepted_text_hash": "sha256...",
  "accepted_text_length": 1523,
  "memory_disposition": "curated",
  "worldbook_activated_entry_ids": ["wb_0", ...],
  "diagnostic_status": "success"
}
```

注意：`accepted_text_hash` 是 SHA-256，不含原始文本。完整文本在 `turn_records` 表中。

### TraceDisplay 输出

`AWPV2TraceDisplay`（节点 3）在 ComfyUI 界面显示结构化诊断信息：

- L1/L2/L3 召回 ID
- 世界书激活条目
- Director 规划摘要
- 子 Agent 触发列表
- Writer 模型与字数
- Quality 裁决与分数
- D6 记忆策展状态

---

## 预设系统

### 可用预设

`presets/writer/kedai_heavy_v1.txt` — 郁达夫散文文风 + 禁词库 + 1200-1600 字规范

### 使用方式

在节点输入中设置 `writer_preset_path: "kedai_heavy_v1"`（不含 `.txt` 后缀）。

留空则不加载预设，Writer 使用默认 prompt。

### 创建新预设

在 `presets/writer/` 目录下放置 `.txt` 文件即可。文件名为 preset name。

---

## 完整示例：手动执行 3 回合

```bash
# ComfyUI URL
URL="http://127.0.0.1:8188"
CARD="C:/path/to/card.json"
SID="demo-session-001"

# === Bootstrap ===
curl -s -X POST $URL/prompt \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":{\"1\":{\"class_type\":\"AWPV2PersistentBootstrap\",\"inputs\":{\"source_path\":\"$CARD\",\"session_id\":\"$SID\",\"greeting_id\":\"g2\",\"request_id\":\"req-bs\",\"run_id\":\"run-1\"}}},\"client_id\":\"demo\"}"

# 等待完成（轮询 /history）

# === Turn 1 ===
# 修改 player_input 后提交 persistent_rp_first_turn.json

# === Turn 2+ ===
# 修改 session_id + player_input 后提交 persistent_rp_continuation_turn.json
```

---

## SQLite 数据位置

数据库文件：`F:\12\语英\本体_ComfyUI\ComfyUI\awp_rp_runtime.db`

### 关键表

| 表 | 内容 |
|----|------|
| `turn_records` | 完整回合记录（含 writer_output 全文） |
| `card_states` | CardState 版本历史 |
| `active_memory_records` | L2 活跃记忆 |
| `rag_memory_records` | L3 RAG 记忆（含 FTS5 全文索引） |
| `execution_traces` | 每回合执行追踪 |
| `card_session_bindings` | Session 绑定 |
| `opening_records` | 开场白 |
| `worldbook_bindings` | 世界书绑定 |

---

## 故障排查

| 问题 | 可能原因 | 解决 |
|------|---------|------|
| status=error | 节点导入错误 | 检查 ComfyUI 日志 |
| 0 字输出 | ComfyUI 缓存命中 | 使用全新 session_id 或重启 ComfyUI |
| L2/L3 召回为 0 | 召回过滤 bug | 重启 ComfyUI 加载修复 |
| 开场白乱码 | greeting_id=g0 不可用 | 使用 g2 或更高 |
| 字数 < 1000 | Writer 未遵循 preset | 检查 preset 是否加载成功 |
