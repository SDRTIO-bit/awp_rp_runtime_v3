# 小说模式：自主 NPC 与预设编译层设计

**状态：** 待用户复审
**范围：** 仅 Novel Mode；不改变 RP 模式。
**目标：** 让小说世界在主角视野外持续运转：关键 NPC 能依据各自目标、情报、资源和风险主动行动、布局，并留下可跨章节回收的后果。

## 1. 背景与取舍

《道渊》角色卡的可复用价值在于：NPC、规则、状态、信息差和动态事件共同构成了会自行推进的世界。梦鲸思客预设的可复用价值在于：按稳定顺序组织设定、历史、文风、场景与输出协议。

本项目不导入来源文件中的角色、世界观、HTML、酒馆宏、成人文本或试图改变系统边界的文本，只提炼：

1. **世界自主性：** 角色是有独立目标和行动能力的行动者，而非主角的被动响应器。
2. **预设编排：** 按消费者提供分层、最小化的上下文，绝不把巨大原始提示直接交给 Writer。

## 2. 成功标准

在两章连续生成验收中：

- 第 1 章即使主角未主动推动关键冲突，至少一名与当前章节主题或卷级主线存在利益关联的 NPC，仍会启动符合身份、已知情报与资源的行动。
- 第 2 章以主角可观察的后果、线索或局势变化体现该行动，而非以全知旁白泄露计划。
- 行动不违背 Architect 的卷/章大纲、已接受账本、角色信息边界或已接受正文。
- 质量门拒绝的章节不写入任何新的 NPC 议程、行动、语义角色状态或记忆。
- 正文保持 Writer 的纯文本输出，不夹带 XML、酒馆变量、JSON 或状态栏。

若两章真实模型验收连续失败，第一版不得默认发布；保留结构化诊断，修复候选筛选或可见性过滤后重新验收，不以静默伪造后果降级来宣称能力已实现。

## 3. 总体架构

```text
NovelProject.config 中的 Novel Profile
  ├─ 世界/角色/规则检索
  ├─ 已接受历史、账本、上一章结尾
  ├─ 文风、人称、节奏、字数
  └─ Agent 输出合约
          │
          ▼
Architect：章节结构与边界；读取活跃议程
          │
          ▼
NPC 幕后行动规划器：私密议程候选（仅本轮内存）
          │
          ▼
Director：选择最多两项可见后果
          │
          ▼
Writer：仅写可见后果、人物边界与正文
          │
          ▼
Quality + Continuity：质量、保密与跨章一致性
          │
          ▼
Ledger Curator：仅在接受后提交行动、事实与议程状态
```

Architect 是唯一的章节结构制定者；规划器不能修改其边界。Architect 在规划前显式读取所有 `active` 与 `advanced` 议程，该查询不受普通连续性账本“最近十条”截断影响。

## 4. 预设编译层与模式隔离

Profile 保存在 `NovelProject.config`，是经过审阅的结构化配置；不执行 SillyTavern 宏，不解析任意 HTML/JavaScript，也不将来源文件原始文本当作系统指令。

最小合约字段为：`schema_id`、`schema_version`、`mode`、`name`、`narrative`、`world`、`history`、`scene`、`agent_contracts`。`mode` 固定为 `novel`；缺失、不兼容或 mode 不匹配时拒绝加载并给出诊断，不采用隐式默认值继续生成。

| 层 | 内容 | 消费者 |
|---|---|---|
| 世界层 | 检索到的规则、地点、势力、物件 | Architect、规划器、Director |
| 角色层 | 当前角色的动机、弱点、关系、人工确认状态 | 规划器、Director、Writer |
| 历史层 | 已接受摘要、有效账本、上一章结尾 | 全部小说角色 |
| 叙事层 | 文风、人称、节奏、目标字数、禁止事项 | Architect、Director、Writer |
| 场景层 | 时间、地点、在场人物、即时冲突、可见线索 | Director、Writer |
| 合约层 | JSON 合约、可见性规则和正文纯文本规则 | 对应角色 |

第一版提供一个“自主剧情”内置 Profile，默认中文创作规则。只有 `NovelEngine` 与小说预设编译器可读取 Novel Profile；RP 调用链不得引用它，防止配置污染。

## 5. NPC 幕后行动规划器

规划器是无工具的小说角色任务：不写正文、不更新数据库、不替代 Architect 或 Director。

输入为：章节计划与卷级边界；上一章结尾加 Architect 已定义的本章单场景节拍；已出现角色；已接受账本；以及相关世界规则与信息边界。它只能使用该角色已知事实，不能凭空生成资源、让角色全知，或把主角意志写成角色目标。

每章最多返回五名候选 NPC，每名至多一条议程。输出必须是 Pydantic `NpcAgenda` 的严格 JSON，不接受自由散文或宽松解析。示例：

```json
{
  "schema_id": "novel.npc_agenda",
  "schema_version": 1,
  "agenda_id": "agenda-...",
  "thread_key": "npc-name:goal-domain",
  "npc": "角色名",
  "private_goal": "私密目标",
  "known_facts": ["已接受账本中的事实 ID 或摘要"],
  "resources": ["现有资源"],
  "resource_cost": "本次消耗",
  "next_step": "下一步行动",
  "trigger": "触发条件",
  "risk": "失败风险",
  "expected_consequence": "预期的可观察后果",
  "consequence_visibility": "trace",
  "deadline_chapter": 15
}
```

`consequence_visibility` 仅描述后果在正文中可被谁观察，枚举为 `hidden`、`trace`、`investigable`、`public`；议程原始数据始终是内部数据。

Director 最多选择两条进入本章，优先选择：能改变局势但不替代主线、与既有动机和资源吻合、资源成本可承担、能形成信息差或阻力、且能在一至三章留下可回收后果的行动。不选择噪声、大纲无关、人物降智或越过主角行动权的议程。

## 6. 数据、状态与持久化

第一版不新建平行数据库表，复用 `LedgerItem`：

| section | 含义 | 可见性 |
|---|---|---|
| `npc_agenda` | 尚未完成的私密行动计划 | 仅内部 Agent 与调试视图 |
| `npc_action` | 已被接受正文确认的 NPC 行动及其获得事实 | 内部；可派生公开事实 |
| `foreshadowing` | 行动留下、尚未回收的线索 | 正常账本 |
| `open_threads` | 行动造成的待解决问题 | 正常账本 |

`npc_agenda.content` 直接保存上述 Pydantic 序列化 JSON；`entity` 是 NPC 名称，`status` 取 `active`、`advanced`、`resolved`、`stale`。Ledger Curator 的 section 白名单必须显式识别 `npc_agenda` 和 `npc_action`，不能降级为 `character_state`。

### 语义角色状态

`npc_action` 是行动结果、资源消耗与新获知情报的唯一自动事实来源，且只能在质量门接受后由 Curator 从正文提取并保存。规划器的 `known_facts` 仅从已接受的 `npc_action`、其他已接受账本事实与人工确认状态派生，绝不使用草稿或候选议程。

第一版不自动把“受伤、获得物品、关系变化、长期已知情报”等语义写入 `NovelCharacter.current_state`；这些变化由作者在审核已接受账本后手动提升。现有的章节索引、摘要和来源等元数据更新不构成语义状态更新。这样可避免错误提取污染后续议程。

### 容量、期限与提交

项目最多保留八条活跃议程。超过 `deadline_chapter` 的议程自动标记为 `stale` 并记录诊断；未过期议程不做 FIFO 或 LRU 自动淘汰。达到上限时不新建议程，只能推进、修改、解决或关闭既有议程；合并仅限同一 NPC 且相同 `thread_key`，必须记录合并/关闭原因。

为保证质量门拒绝零副作用：

1. 规划器与 Director 只在本轮内存处理候选；
2. Writer 与 Quality 结束前不写入新议程；
3. 只有草稿接受后，Curator 才提交 `npc_action`、仍有效的 `npc_agenda` 与派生账本事实；
4. 拒绝、取消、超时或 JSON 解析失败时丢弃本轮候选。

第一版假定单进程同步生成，候选议程只存在于本轮内存；多 worker 的临时状态协调不在本次范围。前端、CLI 导出与普通账本视图默认隐藏 `npc_agenda` 原文，仅显示“本章存在 N 条幕后行动”。

## 7. Agent 边界与可见性

- **Architect：** 制定主题、关键事件、出场边界与不可突破约束，并读取活跃议程避免冲突。
- **规划器：** 提出角色级候选，不编造既成事实、不写正文、不持久化。
- **Director：** 将选中议程转成节拍级 `VisibleConsequence`，如异常缺席、障碍、资源被截获、带条件合作、误导痕迹；可以延后揭示原因，不能删除后果。
- **Writer：** 只接收 `VisibleConsequence` 与人物行为边界，不接收原始 `npc_agenda`。WriterPacket 采用允许列表，而非仅靠约定：禁止传递 `private_goal`、`known_facts`、`resources`、`resource_cost`、`next_step`、`trigger`、`risk`、`expected_consequence`、`consequence_visibility`、`deadline_chapter`、`thread_key` 及 Director 私密选择理由；只允许可见后果描述进入正文上下文。
- **Quality / Continuity：** 检查是否体现独立决策、是否泄露私密计划、后果是否与动机/资源/已知信息/账本一致、跨章节的资源消耗与议程转折是否连续，以及 NPC 行动是否被误写为主角功劳。

## 8. 故障降级

- 没有合格候选：正常生成章节，不强造暗线。
- JSON 不合法或调用失败：记录诊断，Director 仅按既有大纲工作。
- 选择结果与大纲冲突：丢弃该行动，不改 Architect 计划。
- Quality 发现泄露或逻辑冲突：定向修订；仍不通过则按现有拒绝策略处理且不提交本轮行动。
- 到达议程上限：不新建；先处理已过期条目，再推进、显式关闭或按 `thread_key` 合并既有条目。

## 9. 测试与验收

1. **规划器与性能：** 仅选择已出现且相关的角色；未知情报/不存在资源不可用；每章候选和选中数量受限；五十名以上角色时先确定性筛选为有界候选集合。
2. **合约与账本：** JSON 序列化、状态迁移、期限过期、容量规则、拒绝时零写入、导出隐藏私密内容、白名单正确识别新 section。
3. **状态来源：** 草稿与候选不得进入 `known_facts`；只有接受后的 `npc_action` 可派生事实；语义 `current_state` 不自动改写。
4. **Director / Writer：** Writer 只收到可见后果；所有禁止字段和原始议程内容均不在 WriterPacket 中。
5. **质量与连续性：** 检出自主性不足、全知泄露、动机冲突、资源不连续、议程无过渡转向及将 NPC 行动归功主角。
6. **两章端到端与真实模型：** 第 1 章主角未推动关键事件时，关键 NPC 启动行动；第 2 章后果影响主线。使用 DeepSeek V4 Pro 时人工核查主动性、无全知泄露、后果链、接受后才变更账本、期限处理和人工状态提升流程。

## 10. 实施顺序

1. 定义带 `mode: novel` 的版本化 Profile、`NpcAgenda`/`VisibleConsequence` 合约、`thread_key`、账本 section 白名单、容量与期限规则。
2. 实现 Novel Profile 编译器、确定性候选筛选和 WriterPacket 允许列表过滤；为 RP 调用链增加“不读取 Novel Profile”的回归测试。
3. 让 Architect 显式读取活跃议程；扩展 DirectorGuidance，使其按资源可行性选择并只输出可见后果。
4. 实现无副作用的规划器及 Pi 角色资源，并接入章节流水线。
5. 扩展 Curator、Quality 与 Continuity：接受后账本提交、事实派生、人工状态提升接口、保密与跨章一致性检查。
6. 增加 CLI/前端最小可观测性、完整单元/集成/性能测试和可选真实模型验收。
