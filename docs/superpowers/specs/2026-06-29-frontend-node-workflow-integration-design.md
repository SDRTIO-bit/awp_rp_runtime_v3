# 前端功能对接节点/工作流 — 双轨执行引擎设计

**日期**: 2026-06-29
**状态**: 已批准（待实现）
**主题**: 把管理面板前端缺失的功能（聊天交互、角色卡管理、会话管理）对接到节点/工作流，采用双轨执行引擎 + 工作流选择器

---

## 1. 背景与动机

当前管理面板（`web/src`，React + Vite + Antd）只实现了**只读浏览**：

- `pages/Sessions.tsx` — 会话列表（只读）
- `pages/SessionsChat.tsx` — 回合历史展示 + 一个"续写"按钮
- `pages/Cards.tsx` — 角色卡表格（只读）

后端 `runtime/management_api.py` 提供 6 个 REST 端点，其中 `POST /sessions/{id}/continue` 直接实例化 `AWPV2ContinueTurn` 节点调 `execute()`，参数写死在 Python 里。

**核心问题**：
1. 没有"聊天交互"——"续写"按钮调的是 AI 自走（固定 `CONTINUE_INSTRUCTION`），玩家**无法输入消息**，所以不像微信聊天。
2. 没有"管理"动作——导入卡、删除卡、新建会话、删除会话都没有。
3. 续写节点 `AWPV2ContinueTurn` 不接收 `player_input`，无法支撑玩家对话回合。
4. 现有调用是"绕过 ComfyUI 图"的硬编码直调，不走工作流。

**目标**：把前端缺失动作对接到节点/工作流，采用**混合双轨 + 开关**模式，让生成类动作能真正走 ComfyUI 工作流，同时保留全程 Python 直调的能力。

---

## 2. 关键调查结论

### 2.1 现有节点已足够，无需外部插件

| 能力 | 现成节点 | 接收 player_input | LLM |
|---|---|---|---|
| 玩家对话回合 | `AWPV2PersistentContinuationTurn` | ✅ 必需参数 | ✅ via PersistentTurnEngine |
| AI 自续写 | `AWPV2ContinueTurn`（P1） | ❌ 固定指令 | ✅ |
| 首回合 | `AWPV2PersistentFirstTurn` | ✅ | ✅ |
| 导入/bootstrap | `AWPV2PersistentBootstrap` | — | — |

`AWPV2PersistentContinuationTurn` 已是完整持久化流水线（Director→Writer→Quality→State→记忆→TurnRecord），正是为玩家回合设计。**不需要引入外部插件节点**。

### 2.2 黑盒引擎 vs 完整图

- `03_send_turn.api.json`（4 节点）：一个 `AWPV2PersistentContinuationTurn` 黑盒，内部委托 `PersistentTurnEngine`。
- `full_architecture_turn.api.json`（38 节点）：把 C1 双主 Agent、D 系 5 子 Agent、三层记忆、质量管线全显式铺开成图。

**调查结论**：`PersistentTurnEngine` 覆盖了 `full_architecture_turn` **约 89% 的能力**——5 个动态子 Agent、三层记忆、D6 记忆治理（由 `TurnEvolutionCurator` 整合实现）、双主 Agent 全部真实执行（非桩）。**唯一缺失：Reviser 修订重试**——质量不通过时引擎直接拒绝，而 full 图会让 Reviser 重试。

**决策**：选 C 路径——用 `03_send_turn` 黑盒（稳定、简洁），把 Reviser 补进 `PersistentTurnEngine`，使其达到 100% 覆盖。不依赖 `full_architecture_turn` 作为主路径，但通过工作流选择器保留切换到它的能力。

### 2.3 现成工作流 JSON 已就绪

`workflows/awp_v2_playable_workflows/` 下已有完整可玩流程：
- `01_bootstrap_session.json` — 导入/bootstrap
- `02_first_turn.json` — 首回合
- `03_send_turn.json` — 玩家回合
- `04_continue_world.json` — AI 续写

hybrid 轨要走的工作流 JSON **已存在**，无需新建。

### 2.4 Writer 预设基础已就绪

`presets/writer_preset_loader.py` 提供 `WriterPresetLoader`，含 `list_presets()` / `load(name)` / `get_preset_path(name)`。预设文件在 `presets/writer/`（如 `kedai_heavy_v1.txt`）。预设可见功能后端基础完整。

---

## 3. 总体架构：双轨执行引擎

前端统一经 `management_api.py` 的**执行调度层**，按 **动作重量 + 执行模式开关** 分轨：

```
前端 ──HTTP──▶ management_api 执行调度层
                    │
        ┌───────────生成类─────────┐
        │                          │
   mode=hybrid                 mode=python
   读选中工作流 .json           直接 node.execute()
   填参 → POST /prompt 入队      同步返回结果
   轮询 /history 取结果
        │                          │
        └───────────管理类──────────┘
                    │
              始终 Python 直调（无论开关）
              导入卡/删除卡/新建会话/删除会话/列表查询
```

### 3.1 双轨开关

- **全局配置** `AWP_EXECUTION_MODE`（环境变量或配置文件，默认 `hybrid`）
- **请求级覆盖** `?mode=python|hybrid`（仅对生成类生效；管理类恒走 Python）
- 开关只影响生成类动作；管理类永远直调

### 3.2 工作流选择器（新增）

- **粒度**：每个生成类动作（玩家回合/首回合/AI续写）**各选各的**工作流，默认分别选中 `03_send_turn` / `02_first_turn` / `04_continue_world`。
- **扫描范围**：扫描 `workflows/` 下所有 `.json` 文件（不强制 `.api.json` 命名）。
- **UI**：默认**收起**，展开后列出所有工作流，每条显示：文件名、节点数、用途说明、当前是否选中。选中后该次生成走那张图。
- **扩展性**：后来者把自己的工作流 `.json` 丢进 `workflows/` 目录，刷新即在列表出现，可直接选用——这是"工作流可发现、可替换"的入口。
- **后端端点**：`GET /awp/api/v1/workflows` 返回工作流清单（扫描目录 + 解析节点类型统计）。

---

## 4. 前端动作与端点映射

### 4.1 生成类（受开关 + 工作流选择器影响）

| 前端动作 | 端点 | 默认工作流 | python 轨节点 |
|---|---|---|---|
| 玩家发消息 | `POST /sessions/{id}/turn` body:`{player_input}` | `03_send_turn.json` | `AWPV2PersistentContinuationTurn` |
| 首回合 | `POST /sessions/{id}/first-turn` body:`{player_input}` | `02_first_turn.json` | `AWPV2PersistentFirstTurn` |
| AI 续写 | `POST /sessions/{id}/continue`（改造） | `04_continue_world.json` | `AWPV2ContinueTurn` (P1) |

每个生成端点接收可选查询参数：
- `?workflow=<name>` — 指定用哪张图（覆盖选择器默认）
- `?mode=python` — 强制直调

**续写的语义**（保留，非主入口）：续写是"无玩家输入、AI 自走推进剧情"的辅助动作，用固定 `CONTINUE_INSTRUCTION`。改造后聊天主体是"玩家发消息"（玩家回合），续写退回为可选的"让世界自己走一段"按钮。

### 4.2 管理类（恒 Python 直调，不受开关影响）

| 前端动作 | 端点 | 直调节点/操作 |
|---|---|---|
| 导入角色卡 | `POST /cards/import` body:`{source_path}` 或上传文件 | `AWPV2PersistentBootstrap` |
| 删除角色卡 | `DELETE /cards/{id}` | 存储层直删 |
| 新建会话 | `POST /sessions` body:`{card_id, greeting_id}` | CardSessionBinding 提交 |
| 删除会话 | `DELETE /sessions/{id}` | 存储层直删 |
| 角色卡 greetings 列表 | `GET /cards/{id}/greetings` | 读卡定义的 greetings |

### 4.3 新建会话：开场白可选（一体化流程）

新建会话弹窗流程：
1. 选角色卡（下拉，来自 `GET /cards`）
2. 自动拉出该卡 greetings 列表（`GET /cards/{id}/greetings`）
3. 选一个 greeting 作为开场白
4. 创建会话（`POST /sessions` body:`{card_id, greeting_id}`）

### 4.4 Writer 预设可见

- **展示**：生成类页面显示当前 Writer 用的预设文件名/路径。
- **查看内容**：点开可看预设文件实际内容（文本）。
- **编辑跳转**：想编辑则提供链接/按钮，跳转到该预设文件所在目录（`presets/writer/`），不在前端内联编辑。
- **后端端点**：
  - `GET /awp/api/v1/presets/writer` — 列出所有预设（`WriterPresetLoader.list_presets()`）
  - `GET /awp/api/v1/presets/writer/{name}` — 返回预设内容 + 路径（`load()` + `get_preset_path()`）

---

## 5. Reviser 补丁（C 路径核心改动）

把 Reviser 修订重试补进 `PersistentTurnEngine`，让 `03_send_turn` 黑盒具备完整能力：

- **位置**：在 `_quality_check` 之后。
- **逻辑**：质量不通过时，不再直接拒绝，而是复用 Reviser 运行时逻辑（`AWPV2Reviser` 节点背后的同一个 runtime 类，而非节点本身）生成修订稿；修订稿再过一次 `QualityPipeline`；通过则接受，仍不通过才拒绝。
- **最大重试次数**：默认 **1 次**，可配置，避免无限循环。
- **效果**：`03_send_turn` 黑盒从 89% → 100% 覆盖 `full_architecture_turn` 能力。

---

## 6. hybrid 轨异步执行流程

1. 前端调生成端点，带 `player_input` + 可选 `workflow` + `mode`
2. 后端读选中工作流 JSON，定位需要外部输入的节点（`session_id` / `player_input`），填参
3. `POST /prompt` 提交到 ComfyUI 队列，拿 `prompt_id`
4. 后端**轮询** `/history/{prompt_id}` 等执行完成（不用 WebSocket，实现简单，前端已有异步基础）
5. 从执行结果提取 `TURN_RECORD`（含 `writer_output`），返回前端
6. 前端刷新回合列表，新回合以聊天气泡呈现

**python 轨**：同步 `node.execute()`，直接返回结果，不进队列。

---

## 7. 前端 UI 改动

- **SessionChat 页**：
  - 新增玩家输入框 + 发送按钮（发消息走 `POST /turn`）— 聊天主体
  - 保留"续写"按钮（走 `POST /continue`）— 辅助
  - 顶部加"执行模式"与"工作流选择器"折叠面板（默认收起）
  - Writer 预设展示区（文件名/路径 + 查看内容 + 跳转编辑）
- **Cards 页**：
  - "导入角色卡"按钮（上传/路径）
  - 删除按钮
  - 行点击看详情（含 greetings 列表）
- **Sessions 页**：
  - "新建会话"按钮（弹窗：选卡 → 选 greeting → 创建）
  - 删除按钮
- **工作流选择器组件**：可复用，挂在生成类页面，每个动作独立选中。

---

## 8. 测试

- **Reviser 补丁**：单测质量不通过→修订→通过 / 仍不通过 两条路径；最大重试次数边界。
- **执行调度层**：hybrid/python 两轨分支、`?mode` 覆盖、`?workflow` 选择、管理类恒直调。
- **工作流清单端点**：扫描 `workflows/` 目录、解析节点统计、`.json` 命名不强制。
- **Writer 预设端点**：列出预设、返回内容+路径。
- **开场白可选**：新建会话弹窗选卡→拉 greetings→选 greeting→创建的完整流程。
- **端到端**：玩家发消息 → 新回合落库 → 前端展示气泡。

---

## 9. 决策汇总

| 决策点 | 选择 |
|---|---|
| 对接方式 | C 混合 + 开关可切全程 Python |
| 功能范围 | C 全部三类（聊天+卡管理+会话管理） |
| 动作分轨 | A 按重量（生成类走工作流，管理类直调） |
| 玩家回合入口 | A `AWPV2PersistentContinuationTurn` |
| 双轨开关 | A 全局配置 + 请求级覆盖 |
| hybrid 执行方式 | A 提交工作流 JSON 到 `/prompt` 队列 |
| 工作流图选择 | C 用 `03_send_turn` 黑盒 + 补 Reviser |
| 工作流选择器 | C 可查看 + 可切换，默认收起，便于后来者定制 |
| Reviser 最大重试 | 1 次 |
| 选择器粒度 | 每个动作各选各的 |
| 取结果方式 | 轮询 `/history` |
| 工作流文件命名 | 所有 `.json`，不强制 `.api.json` |
| 开场白可选 | A 一体化弹窗流程 |
| Writer 预设可见 | B 展示+查看内容，编辑跳转目录 |

---

## 10. 不做（YAGNI）

- 不引入外部插件节点（现有节点已足够）。
- 不在前端内联编辑 Writer 预设（跳转目录即可）。
- 不把 `full_architecture_turn` 作为主路径（仅作为选择器里可切换的备选）。
- 不做 WebSocket 实时推送（轮询已够）。
- 不做会话搜索/筛选（YAGNI，后续可加）。
