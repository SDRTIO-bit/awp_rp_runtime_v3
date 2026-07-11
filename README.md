# AWP RP Runtime V3

ComfyUI RP Runtime V3：持久化会话 + 双主 Agent + 受控动态子 Agent + 确定性 CardState + 三层记忆 + 管理面板

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

**版本：** `playable-rp-runtime-management-v1`

这是一个**可玩的持久化 RP Runtime**，带管理面板。

### 已验证

- 持久化全链路：Bootstrap → Turn 1 → Turn 2+ → Replay，SQLite 持久化
- 会话恢复：ComfyUI 重启后仅凭 `sessionId` 恢复 L0/L1/L2/L3
- 幂等重放：同 `turnId` 重发返回 `replayed` receipt，零 Provider 调用
- 模型配置受控：白名单 profile（deepseek-v4-pro/flash, fake-*）
- 真实 DeepSeek：8/8 回合通过（Anthropic 端点）
- ComfyUI 实机：Bootstrap → 5 回合 → Replay 全部通过
- 真实酒馆卡加载：大型酒馆卡（263KB, 40 worldbook, 6 greetings）
- 世界书激活：constant 8 条/回合 + selective 关键词匹配
- 双 Agent 真实 LLM：Director (Flash+思考) + Writer (Pro+禁思考)
- 子 Agent LLM 调用：D1-D5 触发后调 DeepSeek Flash 产出具体分析
- 管理面板：React SPA + REST API，会话浏览/回合历史/角色卡列表
- 20 回合连续运行：前 14 回合稳定（1000+ 字），CardState 8 次演化
- 981 个测试全部通过

### 尚待解决

- 子 Agent 触发条件过保守（20 回合测试中 0/20 触发）
- 记忆系统全程 noop（Curator prompt 未明确要求返回 memory candidates）
- 长会话崩溃（T15+ Curator 返回 None 导致，已修复根因）
- 缓存命中率低（prompt 动态内容在前部，稳定前缀短）
- Director/Writer 无工具调用能力（设计中有 ToolGateway，实现未接入）

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

## 6. ComfyUI 节点

共 **114** 个节点，覆盖完整 RP 生命周期。

### 持久化节点（用户直接使用）

| 节点 | 功能 | 输入 |
|------|------|------|
| `AWPV2PersistentBootstrap` | 导入卡片 + 创建会话 | source_path, session_id, greeting_id |
| `AWPV2PersistentFirstTurn` | 首回合执行 | session_id, player_input, profile_id |
| `AWPV2PersistentContinuationTurn` | 连续回合 + 幂等重放 | session_id, player_input, turn_id |
| `AWPV2ContinueTurnP1` | 正式 Continue 回合（P1 真实演化） | session_id, player_input, turn_id |
| `AWPV2SessionRuntimeLoad` | 加载会话状态 | session_id, player_input |
| `AWPV2TurnResultProbe` | history-safe 输出 | receipt, diagnostics |

所有持久化节点不接受 `dbPath`、`history`、`memory`、`CardState` 输入。

### 其他节点类别

| 类别 | 数量 | 说明 |
|------|------|------|
| CardState | ~15 | 卡片导入、规范化、绑定、状态提交 |
| Director/Writer | ~10 | 双主 Agent 编排 |
| D1-D6 子 Agent | ~40 | 历史回查、机会识别、世界活性、情绪关系、连续性、记忆治理 |
| Memory | ~8 | 活跃记忆、RAG 记忆、记忆编译 |
| Quality | ~5 | 质量门、质量管线 |
| Worldbook | ~5 | 条件世界书、会话绑定 |
| Trace/Diagnostics | ~10 | 执行追踪、诊断 |
| Integration | ~10 | 冲突治理、建议合并、工具网关 |

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

| Profile | Provider | Model | 用途 |
|---------|----------|-------|------|
| `deepseek-v4-flash-director` | deepseek | deepseek-v4-flash | Director（思考开启，reasoning_effort=high）|
| `deepseek-v4-pro-writer` | deepseek | deepseek-v4-pro | Writer（思考禁用）|
| `deepseek-v4-pro-director` | deepseek | deepseek-v4-pro | Director（兼容旧配置）|
| `deepseek-v4-flash-writer` | deepseek | deepseek-v4-flash | Writer（兼容旧配置）|
| `fake-director` | fake | fake_director_v1 | 测试 |
| `fake-writer` | fake | fake_writer_v1 | 测试 |

API workflow 不可覆盖 api_key、base_url、token_hard_limit。

---

## 9. DeepSeek Provider

支持双端点自动检测：

| 端点 | SDK | 特点 |
|------|-----|------|
| `api.deepseek.com/v1` | openai | function calling 结构化输出，**推荐** |
| `api.deepseek.com/anthropic` | anthropic | tool_use 结构化输出，ThinkingBlock 分离 |

> **注意**: DeepSeek Anthropic 端点当前不支持 `tool_choice` 参数，Director 的结构化输出必须使用 OpenAI 端点。

---

## 9.1 LLM 连接配置

### 环境变量

```powershell
# 必须：DeepSeek API Key
$env:DEEPSEEK_API_KEY = "sk-xxxxxxxxxxxxxxxx"

# 可选：端点选择（默认 OpenAI /v1）
$env:DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"        # OpenAI 端点（推荐）
# $env:DEEPSEEK_BASE_URL = "https://api.deepseek.com/anthropic" # Anthropic 端点

# 可选：模型覆盖
$env:AWP_DIRECTOR_MODEL = "deepseek-v4-flash"
$env:AWP_WRITER_MODEL = "deepseek-v4-pro"
```

### ComfyUI 节点中使用

持久化节点通过 `director_profile_id` / `writer_profile_id` 选择模型：

```
fake-director / fake-writer          → 测试用，不调用 API
deepseek-v4-flash-director           → Director（Flash + 思考）
deepseek-v4-pro-writer               → Writer（Pro + 禁思考）
```

未知 profileId 会 fail closed（拒绝执行）。

### 快速验证

```powershell
# 1. 设置 API Key
$env:DEEPSEEK_API_KEY = "sk-xxx"

# 2. 测试基础文本生成
python -c "
import os
from openai import OpenAI
client = OpenAI(
    api_key=os.environ['DEEPSEEK_API_KEY'],
    base_url='https://api.deepseek.com/v1',
)
resp = client.chat.completions.create(
    model='deepseek-v4-flash', max_tokens=50,
    messages=[{'role': 'user', 'content': '你好'}],
)
print(resp.choices[0].message.content)
"
```

### 破限声明

Director 和 Writer 的 prompt 中自动追加虚构创作声明，以应对 DeepSeek 的 NSFW 限制。

---

## 10. D1～D6 Agent 总览

| Agent | 代号 | 职责 | 运行位置 | LLM 调用 |
|-------|------|------|----------|----------|
| D1 History/Recall | history-recall | 历史证据回查 | Wave A（Writer 前） | DeepSeek Flash |
| D2 Opportunity | opportunity | 戏剧机会识别 | Wave A（Writer 前） | DeepSeek Flash |
| D3 World-Life | world-life | 世界活性事件 | Wave A（Writer 前） | DeepSeek Flash |
| D4 Emotion/Relationship | emotion-relationship | 情绪与关系解读 | Wave A（Writer 前） | DeepSeek Flash |
| D5 Continuity | continuity | 连续性约束 | Wave B（Continuity Barrier 后） | DeepSeek Flash |
| D6 Memory Curator | memory-curator | accepted-turn 后记忆治理 | Post-Commit（Writer 后） | TurnEvolutionCurator |

子 Agent 工作方式：
1. 规则触发器决定"是否触发"（基于关键词/快照/世界书/NPC）
2. 触发后，每个 Agent 调一次 DeepSeek Flash（禁思考）
3. 产出 2-3 句具体分析，进入 Writer prompt 的 `accepted_guidance`
4. 每条截断 200 字，最多取前 8 条

---

## 11. 三层记忆

| 层级 | 内容 | 上限 | 描述 |
|------|------|------|------|
| L1 近忆窗口 | 最近 accepted TurnRecord | 5 条 | 完整回合记录 |
| L2 活跃记忆 | 剧情注意力卡片 | 15 条 | 30-80 字符 |
| L3 RAG 记忆 | 长期可搜索记忆 | 每轮 ≤10 条 | FTS5 + LIKE |

> **注意**: 当前记忆系统在真实 LLM 运行中全程 noop，需要强化 Curator prompt 或分离 D6 Memory Curator。

---

## 12. 管理面板

React SPA + REST API，ComfyUI 启动后访问 `http://localhost:8188/awp/`。

### API 端点

```
GET    /awp/api/v1/sessions                         -> 会话列表
POST   /awp/api/v1/sessions                         -> 从已有角色卡创建会话
GET    /awp/api/v1/sessions/{id}                    -> 会话详情
DELETE /awp/api/v1/sessions/{id}                    -> 删除会话及其持久化记录
GET    /awp/api/v1/sessions/{id}/turns              -> 回合历史
GET    /awp/api/v1/sessions/{id}/opening            -> 开场白
POST   /awp/api/v1/sessions/{id}/turn               -> 玩家输入回合
POST   /awp/api/v1/sessions/{id}/first-turn         -> 首回合
POST   /awp/api/v1/sessions/{id}/continue           -> AI 自走续写回合
GET    /awp/api/v1/cards                            -> 角色卡列表
POST   /awp/api/v1/cards/import                     -> 导入角色卡
GET    /awp/api/v1/cards/{card_id}/greetings        -> 角色卡开场白列表
DELETE /awp/api/v1/cards/{card_id}                  -> 删除角色卡及其会话
GET    /awp/api/v1/workflows                        -> 可用 API workflow
GET    /awp/api/v1/presets/writer                   -> Writer preset 列表
GET    /awp/api/v1/presets/writer/{name}            -> Writer preset 内容
GET    /awp/{tail:.*}                               -> SPA 静态文件
```

生成类端点支持双轨执行参数：

```
?mode=hybrid|python&workflow=<workflow_name>
```

- `AWP_EXECUTION_MODE=hybrid|python` 控制默认轨道，未设置时默认 `hybrid`。
- `hybrid` 轨道通过 ComfyUI API workflow 排队执行；`python` 轨道直接调用运行时节点类。
- 默认 workflow 映射：`turn -> send_turn`，`first_turn -> first_turn`，`continue -> continue_world`。

### 前端技术栈

- React + TypeScript
- Vite 构建
- Ant Design 组件库
- 页面：Sessions（会话列表/新建/删除）、SessionChat（开场白+历史回合/玩家输入/续写）、Cards（导入/删除/greetings 详情）
- SessionChat 提供高级工作流选择器，可在 `hybrid` 与 `python` 间切换并指定 API workflow。
- SessionChat 提供 Writer preset 查看器，便于确认当前 preset 内容和本地文件路径。

---

## 13. 测试

```bash
# 全部测试
python -m pytest tests/ -q
# 981 collected

# 快速试玩（绕过 ComfyUI，直接调用 persistent 节点）
python -m awp_rp_runtime_v3.testing.quick_playtest --card "<角色卡路径>.json" --turns 8

# 20 回合压力测试
python -m awp_rp_runtime_v3.testing.twenty_turn_test --card "<角色卡路径>.json"

# 线性调试工具
python -m awp_rp_runtime_v3.testing.linear_persistent_rp_debug \
    --card "<角色卡路径>.json" --greeting-id g1 --verbose

# 实机 E2E (需要 ComfyUI 运行)
python -m awp_rp_runtime_v3.testing.playable_e2e_test --turns 8

# 持久化验收
python -m awp_rp_runtime_v3.testing.real_comfy_persistence_acceptance --restart-after-turn --turns 3

# 真实 DeepSeek (需要 DEEPSEEK_API_KEY)
$env:AWP_REAL_LLM_E2E = "1"
$env:AWP_ALLOW_EXTERNAL_CARD_CONTENT = "1"
$env:AWP_REAL_CARD_PATH = "<path>"
python -m awp_rp_runtime_v3.testing.real_provider_multiturn_acceptance --card-path $env:AWP_REAL_CARD_PATH --turns 8

# 离线长会话测试（fake，无需 API Key）
python -m awp_rp_runtime_v3.testing.user_simulation_harness \
    --turns 10 --restart-after-turn 5 --save-artifacts
```

---

## 14. 项目结构

```
awp_rp_runtime_v3/
├─ contracts/          # 数据合同 (schema_id + schema_version)
│   ├─ novel_*.py      # 小说模式合同 (project/chapter/draft/ledger 等)
│   └─ ...             # RP 模式合同
├─ policies/           # 纯策略 (无 I/O)
├─ storage/            # 存储接口 + SQLite 实现
│   ├─ novel_interfaces.py      # 小说存储接口
│   ├─ sqlite/novel_stores.py   # 小说 SQLite 实现
│   └─ ...             # RP 存储 (10 stores)
├─ runtime/            # 运行时编排 (~115 文件)
│   ├─ persistent_turn_engine.py    # RP 主引擎
│   ├─ novel_engine.py              # 小说章节生成引擎
│   ├─ novel_writer_adapter.py      # 小说 Writer LLM 适配器
│   ├─ novel_director_adapter.py    # 小说 Director LLM 适配器
│   ├─ novel_architect_adapter.py   # 小说 Architect LLM 适配器
│   ├─ novel_llm_factory.py         # 小说 LLM 工厂（DeepSeek/OpenCode 切换）
│   ├─ novel_quality_pipeline.py    # 小说质量管线
│   ├─ novel_ledger_curator.py      # 小说账本策展
│   ├─ turn_evolution_curator.py    # LLM 驱动状态+记忆策展
│   ├─ management_api.py            # REST API + SPA 路由（ComfyUI 插件模式）
│   └─ ...
├─ nodes/              # ComfyUI 节点 (122 个)
│   ├─ novel_nodes.py  # 小说模式节点 (8 个)
│   └─ ...             # RP 模式节点 (114 个)
├─ adapters/           # 外部接口
│   ├─ llm/
│   │   ├─ deepseek_adapter.py       # DeepSeek 适配器
│   │   ├─ openai_compatible.py      # OpenAI 兼容适配器（OpenCode 等网关）
│   │   └─ ...
│   ├─ character_card.py
│   ├─ worldbook.py
│   └─ preset.py
├─ services/           # 业务服务层
├─ web/                # 管理面板前端 (React + Vite + Antd)
├─ testing/            # 验收测试 + E2E + 调试工具
├─ tests/              # 单元测试 (981 个)
├─ presets/             # Writer 预设（仅 RP 模式）
├─ workflows/          # ComfyUI 工作流 JSON (14 个)
├─ scripts/            # 脚本工具
│   ├─ awp_server.py   # 独立 HTTP 服务器（不依赖 ComfyUI）
│   ├─ awp_console.py  # 终端控制台
│   └─ ...
├─ test_fixtures/      # 测试夹具
├─ frontend/           # 前端构建产物
└─ docs/               # 文档
   ├─ architecture/    # 架构文档
   ├─ handoffs/        # 阶段验收报告
   ├─ superpowers/     # 设计规格与计划
   ├─ decisions/       # 决策记录
   └─ ...
```

---

## 15. 环境要求

- Python ≥ 3.10
- pydantic ≥ 2.0
- openai ≥ 1.0 (DeepSeek OpenAI 端点)
- anthropic ≥ 0.100 (DeepSeek Anthropic 端点)
- pytest ≥ 7.0 (开发)
- Node.js ≥ 18 (管理面板前端构建)

---

## 16. 安装

```bash
git clone https://github.com/SDRTIO-bit/comfyui_awp_rp-v2.git
cd comfyui_awp_rp-v2
pip install -e ".[dev]"
```

作为 ComfyUI 插件：

```bash
cd /path/to/ComfyUI/custom_nodes/
ln -s /path/to/comfyui_awp_rp-v2 awp_rp_runtime_v3
```

管理面板前端构建（可选）：

```bash
cd web/
npm install
npm run build
```

---

## 17. 路线图

### 已完成里程碑

| 里程碑 | Tag | 测试 | 说明 |
|--------|-----|------|------|
| Card Import Normalization | `card-import-normalization-v1` | ~100 | 卡片导入规范化 |
| Card Session Bootstrap | `card-session-bootstrap-worldbook-binding-v1` | ~200 | 会话引导 + 世界书绑定 |
| D1 History Recall | `d1-history-recall-v1` | ~240 | 历史证据回查 Agent |
| D2 Opportunity | `d2-opportunity-agent-v1` | ~280 | 戏剧机会识别 Agent |
| D3 World-Life | `d3-world-life-agent-v1` | ~320 | 世界活性事件 Agent |
| D4 Emotion/Relationship | `d4-emotion-relationship-agent-v1` | ~400 | 情绪关系解读 Agent |
| D5 Continuity | `d5-continuity-agent-v1` | ~450 | 连续性约束 Agent |
| D6 Memory Curator | `d6-memory-curator-agent-v1` | ~500 | 记忆治理 Agent |
| D-Integration | `d-integration-dynamic-agent-conflict-governance-v1` | 566 | Wave 调度 + 冲突治理 |
| Observability | `observability-autonomous-harness-v1` | 680 | 自主测试框架 |
| CardSession Bootstrap | — | 711 | 确定性引导链 |
| First Turn Execution | `first-turn-execution-context-assembly-v1` | 764 | 首回合管线 |
| Real Provider | `real-provider-multiturn-playable-acceptance-v1` | 795 | DeepSeek 适配器 |
| Canonical Turn | — | 816 | TurnResultProbe + Continuation |
| Persistent Session | `persistent-session-roundsnapshot-integration-v1` | 831 | SQLite 会话存储 |
| Persistent E2E | — | 839 | 统一 Bootstrap/Turn1/Turn2+ |
| Idempotent Replay | `persistent-runtime-live-acceptance-idempotent-replay-v1` | 852 | 幂等重放 + 模型注册 |
| Playable Persistent | `playable-rp-runtime-persistent-v1` | 852 | 合入 main 的可玩里程碑 |
| Multi-Session | `comfy-multisession-long-context-acceptance-v1` | 960 | 多会话长上下文 |
| P1 Real RP Evolution | — | ~980 | TurnEvolutionCurator + 条件世界书 |
| P2 Management | `playable-rp-runtime-management-v1` | 981 | 管理面板 + 子 Agent LLM |

### 下一阶段

- **PromptCompiler V2**：L0/L1/L2/L3 分层缓存，提升 DeepSeek 前缀缓存命中率
- **子 Agent 接入**：DynamicSubAgentPool + Wave A/B + ToolGateway 真实接入
- **记忆系统修复**：强化 Curator prompt 或分离 D6 Memory Curator
- **Director 工具调用**：通过 ToolGateway 调用 worldbook/memory/timeline
- **缓存观测**：`prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` 记录
- **Chat Surface / Playable RP UI**：玩家直接交互界面
- **叙事质量与角色一致性**：长期优化目标

---

## 18. 独立服务器（不依赖 ComfyUI）

项目自带独立 HTTP 服务器，无需 ComfyUI 即可运行全部 RP 和小说功能。

### 启动

```bash
# 默认端口 8188，自动创建数据库
python scripts/awp_server.py

# 自定义端口和数据库路径
python scripts/awp_server.py --port 8189 --db-path ./my_data.db
```

启动后访问：
- **前端面板**: `http://localhost:8188/awp/`
- **API 前缀**: `http://localhost:8188/awp/api/v1/`

### 终端控制台

```bash
# REPL 模式（交互式）
python scripts/awp_console.py --session sess-xxx

# 单条命令
python scripts/awp_console.py --session sess-xxx transcript

# 流式回合
python scripts/awp_console.py --session sess-xxx stream "你好"

# 控制台命令列表
# help / context / cards / sessions / new / session / history /
# turns / transcript / state / send / continue / workflows / presets
```

### ComfyUI 插件模式

当作为 ComfyUI 插件加载时，管理面板自动在 `http://localhost:8189/awp/` 启动（后台守护线程，端口 8189）。

---

## 19. API 使用指南

### 会话管理

```bash
# 列出所有会话
curl http://localhost:8188/awp/api/v1/sessions

# 获取会话详情
curl http://localhost:8188/awp/api/v1/sessions/sess-xxx

# 从已有角色卡创建会话
curl -X POST http://localhost:8188/awp/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"card_id": "card-xxx", "greeting_id": "g0"}'

# 删除会话
curl -X DELETE http://localhost:8188/awp/api/v1/sessions/sess-xxx
```

### 角色卡管理

```bash
# 列出角色卡
curl http://localhost:8188/awp/api/v1/cards

# 导入角色卡（本地路径）
curl -X POST http://localhost:8188/awp/api/v1/cards/import \
  -H "Content-Type: application/json" \
  -d '{"source_path": "/path/to/card.json"}'

# 上传角色卡（文件上传，支持 .json 和 .png）
curl -X POST http://localhost:8188/awp/api/v1/cards/upload \
  -F "file=@/path/to/card.json"

# 获取角色卡的开场白列表
curl http://localhost:8188/awp/api/v1/cards/card-xxx/greetings

# 删除角色卡
curl -X DELETE http://localhost:8188/awp/api/v1/cards/card-xxx
```

### RP 回合

```bash
# 发送玩家输入（同步，等待完整回合）
curl -X POST http://localhost:8188/awp/api/v1/sessions/sess-xxx/turn \
  -H "Content-Type: application/json" \
  -d '{"player_input": "你好，这间房子有点奇怪"}'

# 流式回合（SSE，实时获取步骤和正文）
curl -N http://localhost:8188/awp/api/v1/sessions/sess-xxx/turn/stream \
  -H "Content-Type: application/json" \
  -d '{"player_input": "你好"}'

# 首回合（Bootstrap 后的第一个回合）
curl -X POST http://localhost:8188/awp/api/v1/sessions/sess-xxx/first-turn \
  -H "Content-Type: application/json" \
  -d '{"player_input": ""}'

# AI 自走续写（无玩家输入）
curl -X POST http://localhost:8188/awp/api/v1/sessions/sess-xxx/continue

# 获取回合历史
curl http://localhost:8188/awp/api/v1/sessions/sess-xxx/turns

# 获取开场白
curl http://localhost:8188/awp/api/v1/sessions/sess-xxx/opening

# 获取回合管线详情（含子 Agent、记忆、状态变更）
curl http://localhost:8188/awp/api/v1/sessions/sess-xxx/turns/turn-xxx/pipeline
```

### 执行模式参数

生成类端点支持 `?mode=` 和 `?workflow=` 查询参数：

```bash
# Python 直调模式（不经过 ComfyUI）
curl -X POST "http://localhost:8188/awp/api/v1/sessions/sess-xxx/turn?mode=python" \
  -H "Content-Type: application/json" \
  -d '{"player_input": "你好"}'

# 指定 workflow
curl -X POST "http://localhost:8188/awp/api/v1/sessions/sess-xxx/turn?mode=hybrid&workflow=send_turn" \
  -H "Content-Type: application/json" \
  -d '{"player_input": "你好"}'
```

| 模式 | 说明 |
|------|------|
| `python` | 直接调用 Python 运行时节点，不依赖 ComfyUI |
| `hybrid` | 通过 ComfyUI API workflow 排队执行（需要 ComfyUI 运行） |

环境变量 `AWP_EXECUTION_MODE` 设置默认模式，未设置时默认 `hybrid`。

### SSE 流式事件格式

`/turn/stream` 端点返回 Server-Sent Events：

```
event: started
data: {"turn_id": "turn-xxx", "steps": ["round_snapshot", "director", "writer", ...]}

event: step
data: {"step": "director", "payload": {...}, "duration_ms": 1234}

event: step
data: {"step": "writer", "payload": {...}, "duration_ms": 5678}

event: writer_text
data: {"turn_id": "turn-xxx", "writer_output": "正文内容..."}

event: done
data: {"success": true, "turn_id": "turn-xxx", "turn_index": 3, "writer_output": "..."}
```

### Python 调用示例

```python
import requests

BASE = "http://localhost:8188/awp/api/v1"

# 创建会话
resp = requests.post(f"{BASE}/sessions", json={
    "card_id": "card-xxx",
    "greeting_id": "g0",
})
session_id = resp.json()["data"]["session_id"]

# 发送回合
resp = requests.post(f"{BASE}/sessions/{session_id}/turn", json={
    "player_input": "你好",
})
result = resp.json()["data"]
print(result["writer_output"])  # AI 生成的 RP 正文
```

```python
# SSE 流式读取
import requests
import json

resp = requests.post(
    f"{BASE}/sessions/{session_id}/turn/stream",
    json={"player_input": "你好"},
    stream=True,
)
for line in resp.iter_lines(decode_unicode=True):
    if line.startswith("event: "):
        event_type = line[7:]
    elif line.startswith("data: "):
        data = json.loads(line[6:])
        if event_type == "writer_text":
            print(data["writer_output"], end="", flush=True)
        elif event_type == "done":
            print("\n--- 完成 ---")
```

---

## 20. 小说写作管线

项目包含独立的小说章节生成引擎 `NovelEngine`，与 RP 管线共享基础设施但完全独立运行。

### 架构

```
NovelEngine
  ├── Architect Agent   (LLM: 规划章节结构)
  ├── Director Agent    (LLM: 全局优化 + 情绪弧线)
  ├── Writer Agent      (LLM: 逐 beat 生成正文)
  ├── Quality Pipeline  (确定性检查 + 质量门控)
  └── Ledger Curator    (LLM: 更新伏笔/角色状态/时间线)
```

### 小说生成流程

```
1. plan_chapter()     → Architect 规划章节（细纲、beat、情绪弧线）
2. write_chapter()    → Director 指导 + Writer 逐 beat 生成 + 质量门控
3. revise_chapter()   → 修订（可选）
4. batch_write()      → 批量连续生成（串行，每章间隔 5 秒）
```

### Python 直调

```python
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from awp_rp_runtime_v3.storage.sqlite.database import Database
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter, CharacterRelationship

# 1. 初始化存储
db = Database("my_novel.db")
db.initialize()
reg = SessionRuntimeStoreRegistry(db)
engine = NovelEngine(reg)

# 2. 创建项目
project = NovelProject(
    project_id="my-novel",
    title="我的小说",
    genre="都市悬疑",
    target_platform="番茄长篇",
    target_reader="22-35岁",
    core_emotion="压抑→怀疑→接纳",
    one_sentence_pitch="失眠三年的插画师搬进廉租房，发现房东是三十年前复活的护士。",
    status="writing",
)
reg.novel_project_store.create(project)

# 3. 创建角色
protagonist = NovelCharacter(
    character_id="char-lin",
    project_id="my-novel",
    name="林知夏",
    role="protagonist",
    personality="28岁自由插画师，失眠三年，过目不忘。",
    voice_style="短句，自嘲优先。",
    pov_eligible=True,
    core_motivation="搞清楚每晚梦到废弃医院的原因。",
    current_state={"location": "403室", "emotion": "压抑"},
    arc_phase="setup",
    first_appearance=1,
)
reg.novel_character_store.save(protagonist)

# 4. 规划章节
plan = engine.plan_chapter(
    project_id="my-novel",
    chapter_index=1,
    task_description="开篇钩章，林知夏搬入403室",
)

# 5. 写章节
draft = engine.write_chapter(project_id="my-novel", chapter_index=1)
print(f"字数: {draft.char_count}, 状态: {draft.status}")
print(draft.text[:500])

# 6. 批量生成
drafts = engine.batch_write(
    project_id="my-novel",
    chapter_start=1,
    chapter_end=10,
    on_chapter_complete=lambda idx, d: print(f"第{idx}章完成: {d.char_count}字"),
)
```

### 小说 ComfyUI 节点

| 节点 | 功能 | 输出 |
|------|------|------|
| `AWPV2NovelProjectCreate` | 创建小说项目 | NOVEL_PROJECT, project_id |
| `AWPV2NovelVolumePlan` | 创建卷计划 | NOVEL_VOLUME, volume_id |
| `AWPV2NovelChapterPlan` | Architect 规划章节 | NOVEL_CHAPTER_PLAN |
| `AWPV2NovelChapterWrite` | Writer 生成章节正文 | NOVEL_DRAFT, text |
| `AWPV2NovelChapterRevise` | 修订章节 | NOVEL_DRAFT |
| `AWPV2NovelLedgerView` | 查看账本 | LEDGER_JSON |
| `AWPV2NovelExport` | 导出 Markdown | MARKDOWN_TEXT |
| `AWPV2NovelBatchWrite` | 批量写多章 | NOVEL_DRAFT[] |

### 小说模式环境变量

```powershell
# LLM 提供者选择（默认 deepseek）
$env:NOVEL_LLM_PROVIDER = "opencode"     # 走 OpenCode Zen 网关
$env:NOVEL_LLM_PROVIDER = "deepseek"     # 走 DeepSeek API（默认）

# OpenCode Zen 网关配置
$env:OPENCODE_API_KEY = "your-key"
$env:NOVEL_LLM_BASE_URL = "https://opencode.ai/zen/go/v1"  # 默认值

# 按角色覆盖模型（可选）
$env:NOVEL_LLM_MODEL_WRITER = "qwen3.7-plus"
$env:NOVEL_LLM_MODEL_DIRECTOR = "qwen3.7-plus"
$env:NOVEL_LLM_MODEL_ARCHITECT = "qwen3.7-plus"
$env:NOVEL_LLM_MODEL_CONTINUITY_CHECKER = "qwen3.7-plus"
$env:NOVEL_LLM_MODEL_STYLE_CLEANER = "qwen3.7-plus"
$env:NOVEL_LLM_MODEL_LEDGER_CURATOR = "qwen3.7-plus"
```

### 小说模式 LLM 角色配置

| 角色 | 模型（默认） | max_tokens | thinking |
|------|-------------|------------|----------|
| director | deepseek-v4-pro | 8000 | high |
| architect | deepseek-v4-pro | 6000 | high |
| writer | deepseek-v4-pro | 4000 | medium |
| continuity_checker | deepseek-v4-flash | 4000 | disabled |
| style_cleaner | deepseek-v4-flash | 2000 | disabled |
| ledger_curator | deepseek-v4-flash | 4000 | disabled |

OpenCode 模式下默认全部走 `qwen3.7-plus`。

### 小说数据存储

小说模式在 SQLite 中使用独立的表：

| 表 | 内容 |
|----|------|
| `novel_projects` | 项目元数据 |
| `novel_characters` | 角色设定与状态 |
| `novel_volumes` | 卷计划 |
| `novel_chapter_plans` | 章节细纲 |
| `novel_chapter_drafts` | 章节正文（含修订历史） |
| `novel_ledger_items` | 伏笔/时间线/角色状态/世界观 |
| `novel_batch_progress` | 批量生成进度 |

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/architecture/system-overview.md](docs/architecture/system-overview.md) | RP 系统架构总览 |
| [docs/architecture/turn-lifecycle.md](docs/architecture/turn-lifecycle.md) | RP 回合生命周期 |
| [docs/architecture/agent-boundaries-v1.md](docs/architecture/agent-boundaries-v1.md) | Agent 边界与权限 |
| [docs/architecture/state-and-memory.md](docs/architecture/state-and-memory.md) | 状态与记忆架构 |
| [docs/architecture/retry-and-replay.md](docs/architecture/retry-and-replay.md) | 重试与重放机制 |
| [docs/superpowers/specs/2026-07-02-independent-novel-runtime-design.md](docs/superpowers/specs/2026-07-02-independent-novel-runtime-design.md) | 小说模式设计规格 |
| [docs/superpowers/plans/2026-07-04-novel-runtime-adaptation-plan.md](docs/superpowers/plans/2026-07-04-novel-runtime-adaptation-plan.md) | 小说模式适配计划 |
| [docs/handoffs/2026-07-05-opencode-zen-novel-handoff.md](docs/handoffs/2026-07-05-opencode-zen-novel-handoff.md) | OpenCode Zen 接入交接 |
| [docs/contributing.md](docs/contributing.md) | 贡献指南 |
| [docs/security.md](docs/security.md) | 安全文档 |
| [docs/handoffs/](docs/handoffs/) | 全部阶段验收报告 |
| [docs/architecture/](docs/architecture/) | 架构文档 |
| [docs/reference/](docs/reference/) | 参考文档 |
| [docs/decisions/](docs/decisions/) | 决策记录 |
