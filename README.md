# AWP RP Runtime V2

ComfyUI RP Runtime V2：持久化会话 + 双主 Agent + 受控动态子 Agent + 确定性 CardState + 三层记忆

---

## 1. 项目是什么

本项目是一个以 ComfyUI 工作流为编排骨架的 RP（角色扮演）运行时。

核心理念：

> **确定性负责让故事不乱；独立 Agent 的受控自由负责让故事不死。**

它不是把越来越长的提示词交给单一模型，也不是把所有功能塞进一个万能主 Agent。而是在 ComfyUI 节点图中显式暴露：

- **确定性节点层**：CardState、条件世界书、事件阶段、记忆读写、质量决策、状态提交、审计
- **Agent 推理层**：双主 Agent、动态子 Agent、工具调用、叙事决策、创意建议、写作与修订

两者不是竞争关系。节点层负责可验证、可回放、可测试、可持久化的事实和副作用；Agent 层负责理解、联想、判断、选择、调度、叙事表现。

---

## 2. 当前状态

**版本：** `playable-rp-runtime-persistent-v1`

这是一个**可玩的持久化 RP Runtime**。

### 已验证

- 持久化全链路：Bootstrap → Turn 1 → Turn 2+ → Replay，SQLite 持久化
- 会话恢复：ComfyUI 重启后仅凭 `sessionId` 恢复 L0/L1/L2/L3
- 幂等重放：同 `turnId` 重发返回 `replayed` receipt，零 Provider 调用
- 模型配置受控：白名单 profile（deepseek-v4-pro/flash, fake-*）
- 真实 DeepSeek：8/8 回合通过（Anthropic 端点）
- ComfyUI 实机：Bootstrap → 5 回合 → Replay 全部通过
- 852 个测试全部通过

### 尚待验证

- 真实 DeepSeek 在持久化节点链上连续运行
- 真实 D6 在真实模型输出下产生 MemoryCommitPlan
- 真实角色卡的叙事质量、角色一致性、世界书命中质量

---

## 3. 核心设计原则

1. **Agent 不直接写 CardState**：只有 `CardStateCommitRuntime` 可以写入
2. **Agent 不直接写记忆**：只有 `ActiveMemoryCommitRuntime` / `RagMemoryCommitRuntime` 可以写入
3. **Writer 不用工具、不直接写状态**：Writer 只能读取 FinalTurnBrief，产出 RP 正文
4. **Director 不输出玩家正文**：Director 只产出 TurnBrief / DelegationPlan / DirectorResolution
5. **D6 不参与 Writer 前 SuggestionMerge**：D6 在 Commit 后运行
6. **只有 Commit Runtime 可以产生副作用**：Quality Gate reject = 零副作用
7. **玩家代理权约束不能被 Agent 覆盖**：Agent 不能代替玩家做决定
8. **World-Life / Opportunity / Emotion 的建议不能自动变成既成事实**：只能作为 Writer 参考

---

## 4. 持久化架构

```
RuntimeStoreFactory (profile + namespace → SQLite)
  ↓
SessionRuntimeStoreRegistry (10 stores, 1 connection)
  ├── CardSessionBindingStore     (L0)
  ├── OpeningRecordStore          (L0)
  ├── WorldbookBindingStore       (L0)
  ├── BootstrapReceiptStore       (L0)
  ├── CardStateStore              (L0+L1)
  ├── TurnRecordStore             (L1)
  ├── RoundSnapshotStore          (snapshot)
  ├── TraceStore                  (trace)
  ├── ActiveMemoryStore           (L2)
  └── RagMemoryStore              (L3)
```

所有持久化节点通过 `RuntimeStoreFactory.from_env()` 获取 store，不接受 `dbPath` 输入。

---

## 5. 完整回合生命周期

```
Player Input
→ SessionRuntimeLoad (从 SQLite 恢复 L0/L1/L2/L3)
→ RoundSnapshotBuilder
→ DirectorPlan (tool_use / function calling)
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
→ CardState Commit (SQLite)
→ TurnRecord Commit (SQLite)
→ D6 Memory Curator
→ Deterministic Memory Commit (SQLite)
→ Completed Turn
```

---

## 6. 持久化节点

| 节点 | 功能 | 输入 |
|------|------|------|
| `AWPV2PersistentBootstrap` | 导入卡片 + 创建会话 | source_path, session_id, greeting_id |
| `AWPV2PersistentFirstTurn` | 首回合执行 | session_id, player_input, profile_id |
| `AWPV2PersistentContinuationTurn` | 连续回合 + 幂等重放 | session_id, player_input, turn_id |
| `AWPV2SessionRuntimeLoad` | 加载会话状态 | session_id, player_input |
| `AWPV2TurnResultProbe` | history-safe 输出 | receipt, diagnostics |

所有持久化节点不接受 `dbPath`、`history`、`memory`、`CardState` 输入。

---

## 7. 幂等重放

同 `sessionId + turnId + requestId` 重发时：

```
TurnRecordStore.load(turn_id)
  ├── 存在 → 返回 replayed receipt (idempotency_status="replayed")
  │          不调用 Provider，不写 State，不写 Memory
  └── 不存在 → 正常执行
```

`idempotency_status` 值：
- `fresh`：正常执行
- `replayed`：返回既有结果
- `conflict`：session 不匹配
- `recovery_required`：未完成且不可恢复

---

## 8. 模型配置

受控白名单，未知 profileId → fail closed。

| Profile | Provider | Model |
|---------|----------|-------|
| `deepseek-v4-pro-director` | deepseek | deepseek-v4-pro |
| `deepseek-v4-flash-writer` | deepseek | deepseek-v4-flash |
| `fake-director` | fake | fake_director_v1 |
| `fake-writer` | fake | fake_writer_v1 |

API workflow 不可覆盖 api_key、base_url、token_hard_limit。

---

## 9. DeepSeek Provider

支持双端点自动检测：

| 端点 | SDK | 特点 |
|------|-----|------|
| `api.deepseek.com/anthropic` | anthropic | tool_use 结构化输出，ThinkingBlock 分离 |
| `api.deepseek.com` | openai | function calling 结构化输出 |

Director 使用 tool_use/function calling 保证结构化输出。
Writer 使用标准文本生成。

---

## 9.1 LLM 连接配置

### 环境变量

```powershell
# 必须：DeepSeek API Key
$env:DEEPSEEK_API_KEY = "sk-xxxxxxxxxxxxxxxx"

# 可选：端点选择（默认 Anthropic）
$env:DEEPSEEK_BASE_URL = "https://api.deepseek.com/anthropic"  # Anthropic 端点（推荐）
# $env:DEEPSEEK_BASE_URL = "https://api.deepseek.com"          # OpenAI 端点

# 可选：模型覆盖（默认 deepseek-v4-pro / deepseek-v4-flash）
$env:AWP_DIRECTOR_MODEL = "deepseek-v4-pro"
$env:AWP_WRITER_MODEL = "deepseek-v4-flash"
```

### 端点对比

| 端点 | Base URL | SDK | 特点 |
|------|----------|-----|------|
| Anthropic | `https://api.deepseek.com/anthropic` | anthropic | tool_use 结构化输出，ThinkingBlock 分离，更稳定 |
| OpenAI | `https://api.deepseek.com` | openai | function calling，兼容性更广 |

适配器根据 `DEEPSEEK_BASE_URL` 自动选择 SDK，无需改代码。

### 模型说明

| 模型 | 用途 | 说明 |
|------|------|------|
| `deepseek-v4-pro` | Director | 推理能力强，用于叙事规划 |
| `deepseek-v4-flash` | Writer | 速度快，用于文本生成 |
| `deepseek-chat` | 兼容 | 2026/07/24 弃用，等同 deepseek-v4-flash |

### ComfyUI 节点中使用

持久化节点通过 `director_profile_id` / `writer_profile_id` 选择模型：

```
fake-director / fake-writer          → 测试用，不调用 API
deepseek-v4-pro-director             → 真实 DeepSeek Director
deepseek-v4-flash-writer             → 真实 DeepSeek Writer
```

未知 profileId 会 fail closed（拒绝执行）。

### 快速验证

```powershell
# 1. 设置 API Key
$env:DEEPSEEK_API_KEY = "sk-xxx"

# 2. 测试连接
python -c "
import os, anthropic
client = anthropic.Anthropic(
    api_key=os.environ['DEEPSEEK_API_KEY'],
    base_url='https://api.deepseek.com/anthropic',
)
msg = client.messages.create(
    model='deepseek-v4-flash', max_tokens=50,
    messages=[{'role': 'user', 'content': 'Say hello'}],
)
for b in msg.content:
    if hasattr(b, 'text'): print(b.text)
"
```

---

## 10. D1～D6 Agent 总览

| Agent | 代号 | 职责 | 运行位置 |
|-------|------|------|----------|
| D1 History/Recall | history-recall | 历史证据回查 | Wave A（Writer 前） |
| D2 Opportunity | opportunity | 戏剧机会识别 | Wave A（Writer 前） |
| D3 World-Life | world-life | 世界活性事件 | Wave A（Writer 前） |
| D4 Emotion/Relationship | emotion-relationship | 情绪与关系解读 | Wave A（Writer 前） |
| D5 Continuity | continuity | 连续性约束 | Wave B（Continuity Barrier 后） |
| D6 Memory Curator | memory-curator | accepted-turn 后记忆治理 | Post-Commit（Writer 后） |

---

## 11. 三层记忆

| 层级 | 内容 | 上限 | 描述 |
|------|------|------|------|
| L1 近忆窗口 | 最近 accepted TurnRecord | 5 条 | 完整回合记录 |
| L2 活跃记忆 | 剧情注意力卡片 | 15 条 | 30-80 字符 |
| L3 RAG 记忆 | 长期可搜索记忆 | 每轮 ≤10 条 | FTS5 + LIKE |

---

## 12. 测试

```bash
# 全部测试
python -m pytest tests/ -q
# 852 passed in 10s

# 实机 E2E (需要 ComfyUI 运行)
python -m awp_rp_runtime_v2.testing.playable_e2e_test --turns 8

# 持久化验收
python -m awp_rp_runtime_v2.testing.real_comfy_persistence_acceptance --restart-after-turn --turns 3

# 真实 DeepSeek (需要 DEEPSEEK_API_KEY)
$env:AWP_REAL_LLM_E2E = "1"
$env:AWP_ALLOW_EXTERNAL_CARD_CONTENT = "1"
$env:AWP_REAL_CARD_PATH = "<path>"
python -m awp_rp_runtime_v2.testing.real_provider_multiturn_acceptance --card-path $env:AWP_REAL_CARD_PATH --turns 8
```

---

## 13. 项目结构

```
awp_rp_runtime_v2/
├─ contracts/          # 数据合同 (schema_id + schema_version)
├─ policies/           # 纯策略 (无 I/O)
├─ storage/            # 存储接口 + SQLite 实现
├─ runtime/            # 运行时编排 (RuntimeStoreFactory, SessionRuntimeLoad)
├─ nodes/              # ComfyUI 节点 (101 个)
├─ adapters/           # 外部接口 (DeepSeek Anthropic/OpenAI 双端点)
├─ testing/            # 验收测试 + E2E
├─ tests/              # 单元测试 (852 个)
├─ workflows/api/      # API 工作流 JSON
└─ docs/               # 文档
   ├─ handoffs/        # 阶段验收报告
   └─ architecture/    # 架构文档
```

---

## 14. 环境要求

- Python ≥ 3.10
- pydantic ≥ 2.0
- openai ≥ 1.0 (DeepSeek OpenAI 端点)
- anthropic ≥ 0.100 (DeepSeek Anthropic 端点)
- pytest ≥ 7.0 (开发)

---

## 15. 安装

```bash
git clone https://github.com/SDRTIO-bit/comfyui_awp_rp-v2.git
cd comfyui_awp_rp-v2
pip install -e ".[dev]"
```

作为 ComfyUI 插件：

```bash
cd /path/to/ComfyUI/custom_nodes/
ln -s /path/to/comfyui_awp_rp-v2 awp_rp_runtime_v2
```

---

## 16. 路线图

### 当前：playable-rp-runtime-persistent-v1

- ✅ 持久化全链路 (SQLite L0-L3)
- ✅ 幂等重放
- ✅ 模型配置白名单
- ✅ 真实 DeepSeek (Anthropic 端点 8/8)
- ✅ ComfyUI 实机 E2E
- ✅ 852 测试通过

### 下一阶段

- 真实 DeepSeek 持久化节点链
- 真实 D6 MemoryCommitPlan
- Chat Surface / Playable RP UI
- 叙事质量与角色一致性

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/handoffs/playable-rp-runtime-persistent-v1.md](docs/handoffs/playable-rp-runtime-persistent-v1.md) | 当前里程碑验收 |
| [docs/handoffs/](docs/handoffs/) | 全部阶段验收报告 |
| [docs/architecture/](docs/architecture/) | 架构文档 |
