# AWP RP Runtime V2

ComfyUI RP Runtime V2：双主 Agent + 受控动态子 Agent + 确定性 CardState + 三层记忆

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

## 2. 当前 Alpha 状态

**版本：** `v0.1.0-alpha`

这是一个 **ComfyUI RP Runtime V2 的 Alpha 架构实现**。

### 已完成

- 确定性 CardState（SQLite + 事务提交 + revision + patchId + 幂等）
- 三层记忆系统（L1 近忆窗口 + L2 活跃记忆 + L3 RAG）
- 双主 Agent 的职责边界（Director / Writer）
- D1～D5 Writer 前受控动态 Agent（Wave A / Wave B）
- D6 accepted-turn 后记忆治理
- 动态 Agent 调度、预算、冲突治理、降级、Trace
- ComfyUI 节点与官方 workflow JSON
- Fake Adapter 集成测试（566 测试全部通过）

### 尚未承诺

- 生产级真实模型接入体验
- 一键安装即玩的完整 RP 产品
- 完整前端 UI
- 自动世界事件系统
- 无限制多 Agent 自主协作
- 稳定的第三方插件生态兼容性

> 当前版本使用 Fake Adapter 进行测试，真实 LLM 调用属于未来接入能力。

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

## 4. 完整回合生命周期

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

## 5. D1～D6 Agent 总览

| Agent | 代号 | 职责 | 运行位置 |
|-------|------|------|----------|
| D1 History/Recall | history-recall | 历史证据回查 | Wave A（Writer 前） |
| D2 Opportunity | opportunity | 戏剧机会识别 | Wave A（Writer 前） |
| D3 World-Life | world-life | 世界活性事件 | Wave A（Writer 前） |
| D4 Emotion/Relationship | emotion-relationship | 情绪与关系解读 | Wave A（Writer 前） |
| D5 Continuity | continuity | 连续性约束 | Wave B（Continuity Barrier 后） |
| D6 Memory Curator | memory-curator | accepted-turn 后记忆治理 | Post-Commit（Writer 后） |

所有 Agent 只读、不可委托、不可写状态/记忆。产出标准化为建议（Suggestion），不是既成事实。

---

## 6. 执行拓扑：Wave A / Continuity Barrier / D6

```
Wave A (并发):
  D1 History / Recall
  D2 Opportunity
  D3 World-Life
  D4 Emotion / Relationship
        ↓
  Normalized Candidate Suggestion Set
        ↓
  Continuity Barrier
        ↓
  Wave B:
  D5 Continuity Agent
        ↓
  Conflict Governance (SuggestionConflictGovernor)
        ↓
  Director Suggestion Resolution
        ↓
  FinalTurnBrief → Writer

  ... Writer 产出正文 ...

QualityGate(ACCEPT) → CardStateCommit → TurnRecordCommit
        ↓
  D6 Memory Curator (Post-Commit)
        ↓
  ActiveMemoryCommit + RagMemoryCommit
        ↓
  Completed Turn
```

---

## 7. 卡状态与三层记忆

### CardState

世界变量、事件标志、场景状态的唯一真实来源。

- 只有 `CardStateCommitRuntime` 可以写入
- 所有写入需要：Gate 通过 + Revision 匹配 + 唯一 patchId + 事务原子性

### 三层记忆

| 层级 | 内容 | 上限 | 描述 |
|------|------|------|------|
| L1 近忆窗口 | 最近 accepted TurnRecord | 5 条 | 完整回合记录，永不截断 |
| L2 活跃记忆 | 剧情注意力卡片 | 15 条 | 30-80 字符，高优先级优先保留 |
| L3 RAG 记忆 | 长期可搜索记忆 | 每轮 ≤10 条 | FTS5 + LIKE fallback |

优先级顺序（硬约束）：CardState > accepted Turn > ActiveMemory > RAG > 世界书

---

## 8. 安全边界与不可越权规则

- **Agent 不直接写 CardState**
- **Agent 不直接写记忆**
- **Writer 不用工具、不直接写状态**
- **Director 不输出玩家正文**
- **D6 不参与 Writer 前 SuggestionMerge**
- **只有 Commit Runtime 可以产生副作用**
- **玩家代理权约束不能被 Agent 覆盖**
- **World-Life / Opportunity / Emotion 的建议不能自动变成既成事实**

---

## 9. 当前实现范围

### 核心架构

- 确定性 CardState（SQLite + 事务提交）
- 三层记忆系统（L1 + L2 + L3）
- 双主 Agent 职责边界
- 合同驱动架构（所有数据结构带 schema_id + schema_version）

### 动态 Agent 系统

- D1～D6 六个受控动态子 Agent
- Dynamic Agent Scheduler（Wave A / Wave B）
- Continuity Barrier
- Suggestion Conflict Governor
- Director Suggestion Resolution
- 预算策略（Simple / Normal / Complex 三档）

### ComfyUI 节点

- 80+ ComfyUI 节点
- 11 个官方 workflow JSON
- 中英文节点显示名称

### 测试

- 566 个测试全部通过
- 覆盖：合同、策略、存储、运行时、集成、端到端
- Fake Adapter 用于所有测试

---

## 10. 尚未实现或未承诺能力

- 真实 LLM 调用（OpenAICompatibleAdapter 仅检查 API key，实际调用抛出 NotImplementedError）
- 一键安装即玩的完整 RP 产品
- 完整前端 UI（Agent 执行状态观察、记忆管理、冲突确认）
- 自动世界事件系统
- 无限制多 Agent 自主协作
- 稳定的第三方插件生态兼容性
- 多会话并发支持
- 持久化会话管理

---

## 11. 项目结构

```
awp_rp_runtime_v2/
├─ contracts/          # 数据合同（dataclasses，带 schema_id + schema_version）
├─ policies/           # 纯策略（无 I/O）
├─ storage/            # 存储接口 + SQLite 实现
├─ runtime/            # 运行时编排逻辑
├─ nodes/              # ComfyUI 节点实现
├─ adapters/           # 外部系统接口（LLM、角色卡、世界书）
├─ services/           # 服务协调
├─ testing/            # Fake Adapter 与测试 fixtures
├─ tests/              # 测试套件
├─ workflows/          # 官方 ComfyUI workflow JSON
└─ docs/               # 文档
   ├─ architecture/    # 架构文档
   ├─ handoffs/        # 阶段验收报告
   ├─ reference/       # 原始架构记录
   └─ decisions/       # 架构决策记录
```

---

## 12. 环境要求

- Python ≥ 3.10
- pydantic ≥ 2.0
- pytest ≥ 7.0（开发）
- pytest-asyncio ≥ 0.21（开发）

不需要 API Key，不需要网络连接，不需要外部服务。

---

## 13. 安装与测试

### 安装

```bash
# 克隆仓库
git clone https://github.com/SDRTIO-bit/comfyui_awp_rp-v2.git
cd comfyui_awp_rp-v2

# 安装依赖（可选，用于开发）
pip install -e ".[dev]"
```

### 测试

```bash
# 运行全部测试
python -m pytest tests/ -q

# 运行详细测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_d_integration.py -v
```

当前测试结果：**566 passed in 2.10s**

### 作为 ComfyUI 插件

将仓库克隆或链接到 ComfyUI 的 `custom_nodes/` 目录：

```bash
cd /path/to/ComfyUI/custom_nodes/
ln -s /path/to/comfyui_awp_rp-v2 awp_rp_runtime_v2
```

重启 ComfyUI 后，节点将出现在工作流编辑器中。

> **注意：** 当前版本为 Alpha 架构实现，节点需要配合 Fake Adapter 使用。真实 LLM 调用属于未来接入能力。

---

## 14. 官方 Workflow

| 文件 | 用途 | 类型 |
|------|------|------|
| `official_stateful_turn_v2.json` | 完整有状态回合流程 | 示例工作流 |
| `official_director_delegation_v2.json` | Director 委派流程 | 示例工作流 |
| `official_memory_runtime_v2.json` | 记忆运行时流程 | 示例工作流 |
| `official_dual_main_tool_gateway_v2.json` | 双主 Agent + 工具网关 | 示例工作流 |
| `official_history_recall_agent_v2.json` | D1 历史回查 Agent | 观察工作流 |
| `official_opportunity_agent_v2.json` | D2 戏剧机会 Agent | 观察工作流 |
| `official_world_life_agent_v2.json` | D3 世界活性 Agent | 观察工作流 |
| `official_continuity_agent_v2.json` | D5 连续性 Agent | 观察工作流 |
| `official_emotion_relationship_agent_v2.json` | D4 情绪关系 Agent | 观察工作流 |
| `official_memory_curator_agent_v2.json` | D6 记忆治理 Agent | 观察工作流 |
| `official_dynamic_agent_integration_v1.json` | 完整动态 Agent 集成 | 观察工作流 |

> **说明：** 这些工作流 JSON 已完成结构校验，但普通用户尚不能一键打开并获得真实模型 RP 体验。当前需要配合 Fake Adapter 使用，真实模型接入属于未来能力。

---

## 15. 开发与贡献说明

请参阅 [docs/contributing.md](docs/contributing.md)。

核心要求：

1. 创建分支
2. 运行测试（所有测试必须通过）
3. 保持合同 schema 版本兼容
4. 新增 Agent 时必须声明权限
5. 新增副作用时必须通过 Commit Runtime
6. 新增 workflow 时必须补 JSON 校验
7. 提交前不得包含密钥、数据库、日志、缓存

---

## 16. 路线图

### 当前：v0.1.0-alpha

- ✅ 核心架构（CardState、三层记忆、双主 Agent）
- ✅ 动态 Agent 系统（D1～D6）
- ✅ 调度与治理（Wave A/B、冲突治理、预算、降级）
- ✅ ComfyUI 节点与官方 workflow
- ✅ Fake Adapter 集成测试

### 下一阶段候选

- 真实 LLM Adapter 接入
- ComfyUI 安装验证
- 前端可观测性
- Wave A 并发执行
- 产品化集成

---

## 17. License 状态

License 尚未确定；除非另有明确授权，代码版权归项目作者所有。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/architecture/overview-v1.md](docs/architecture/overview-v1.md) | 架构总览 |
| [docs/architecture/turn-lifecycle-v1.md](docs/architecture/turn-lifecycle-v1.md) | 完整回合生命周期 |
| [docs/architecture/agent-boundaries-v1.md](docs/architecture/agent-boundaries-v1.md) | Agent 权限边界 |
| [docs/architecture/memory-governance-v1.md](docs/architecture/memory-governance-v1.md) | 记忆治理架构 |
| [docs/architecture/conflict-governance-v1.md](docs/architecture/conflict-governance-v1.md) | 冲突治理架构 |
| [docs/alpha-status-v0.1.md](docs/alpha-status-v0.1.md) | Alpha 状态报告 |
| [docs/contributing.md](docs/contributing.md) | 贡献指南 |
| [docs/security.md](docs/security.md) | 安全政策 |
| [docs/reference/](docs/reference/) | 原始架构记录 |
| [docs/handoffs/](docs/handoffs/) | 阶段验收报告 |
