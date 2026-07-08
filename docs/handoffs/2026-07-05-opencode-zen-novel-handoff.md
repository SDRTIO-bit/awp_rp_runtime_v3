# 交接报告：AWP RP Runtime V2 — OpenCode Zen 网文输出质量改造

> 创建时间：2026-07-05
> 作者：上一轮会话
> 目的：让后来者快速接手"将 novel engine 接入 OpenCode Zen 下调出可用网文输出"的工作

---

## 一、项目目标

把 `NovelEngine` 从原本仅走 DeepSeek 自有 API 改造为可走 OpenCode Zen 网关（`https://opencode.ai/zen/go/v1`），并验证 qwen3.7-* 在网文章节生成上的写作质量实测。不破坏原 DeepSeek 路径与既有测试。

---

## 二、已完成改动

### 2.1 新增：OpenAI-compatible adapter
- 文件：`adapters/llm/openai_compatible.py`
- 与 `DeepSeekAdapter` 签名兼容：`generate_text` / `generate_structured`
- 关键点：调用前会把 DeepSeek 专用的 `thinking` extra_body key 剥掉，避免 OpenCode 网关 400
- `is_available` 依赖 `OPENCODE_API_KEY` env var

### 2.2 工厂路由
- 文件：`runtime/provider_adapter_factory.py`
- 新增 `_select_adapter()`，`provider="openai"` 路由到 `OpenAICompatibleAdapter`，deepseek 保持原路径

### 2.3 NovelLLMFactory 环境切换
- 文件：`runtime/novel_llm_factory.py`
- 加了 `_provider_choice()`：读 `NOVEL_LLM_PROVIDER` env，默认 `deepseek`（保护测试）
- `opencode` 模式下，模型名走 `_role_config()` 覆写。**当前默认全部走 `qwen3.7-plus`**（max 单价贵数倍，且 8K 输出窗口内有同句重复问题，见 §五）
- 覆盖路径：`NOVEL_LLM_MODEL_{ROLE}` env 可强制指定（如 `NOVEL_LLM_MODEL_WRITER=qwen3.7-max`）

### 2.4 模型 profile 注册
- 文件：`adapters/llm/model_profile_registry.py`
- 注册了 6 个 opencode profile：`opencode-qwen-max-writer` / `opencode-qwen-plus-writer` / `opencode-glm-52-writer` / `opencode-kimi-code-writer` / `opencode-mimo-pro-writer` / `opencode-minimax-m3-writer`
- 网关实际可用模型共 20 个（接口 `/v1/models` 可拉）

### 2.5 Writer preset 重写（针对 RP 模式，非 novel 模式）
- 文件：`presets/writer/kedai_heavy_v1.txt`（5923B v2，旧版 backup 在 `kedai_heavy_v1.bak.txt` 17701B）
- 但注意：**Novel 模式不读取 preset**，走 `novel_writer_adapter.py::WRITER_SYSTEM_PROMPT`（59 行硬编码）。preset 改动只影响 RP 模式。**如果你要改 novel 写作质量，改 `WRITER_SYSTEM_PROMPT`，不要动 preset**。这一段重复一遍，避免后来者绕弯。

### 2.6 运行脚本
- 文件：`scripts/run_empty_rooms.py`——实战脚本模板，含项目+角色+三章 batch_write。
- 文件：`scripts/dump_reject.py`——DB 排障脚本

### 2.7 测试状态
- 1076 passed / 1 skipped（排除 novel 子系统的 4 个 e2e 文件，它们要真 LLM 调用，已超时）
- DeepSeek 路径未受影响

---

## 三、得分点（端到端通了）

1. 真实 LLM 调用：OpenCode Zen + `qwen3.7-max` 实测通过，token 账单正常
2. `NovelEngine.batch_write` 走 OpenCode 路径跑通，Ch01 实际产出 8181 字
3. 章节规划 → director 指导 → beat 生成 → 质量门 → 持久化 全链路打通
4. 角色 file（林知夏/袁护士/404 小孩）正确加载、写入 character_store

---

## 四、卡点（用户判定：质量不达标）

### 4.1 Chapter 1 用户反馈
> "很可惜，刚看了开头就知道，写的不行。"

具体不达标项尚未点明。后面接手者需要做的第一件事：**让用户具体说不行的点**（开篇节奏？画面密度？对白腔？氛围？情节钩子？）。不要凭猜继续改。

可参考的客观瑕疵（来自 Chapter 1 全文 380 行的检查）：

| 瑕疵 | 位置 | 性质 |
|---|---|---|
| "连续四十八小时没合眼"同句两次出现 | 段 10 内 | max 长程一致性失误 |
| "四十八小时" → "七十二小时" 自相矛盾 | 段 38 / 段 354 | 同章内失眠时长翻倍 |
| 主角性别错配 | 全章 | 设定女插画师，正文全用"他"。`WRITER_SYSTEM_PROMPT` 没有性别约束条款 |
| 灰衣人/镜中无脸人/画中无脸人在同一章重复 4 次 | 段 28-100 | 恐怖意象透支，建议一章 2 次 |

### 4.2 Chapter 2 = 0 字 reject，Chapter 3 没生成

**根因已定位（不是质量门拒绝，是 LLM 空返回）**：

```
NovelEngine.write_chapter
  → _generate_with_beats (novel_engine.py:194)
  → if not plan.scene_beats:                  # 容错分支
      try: return self._call_writer(packet)
      except RuntimeError: return ""          # ← 这里吞了空返回
    # 空 text 进入质量门
  → quality_pipeline.run_chapter(text="", ...)
  → 字数门直接判 reject
  → 状态写"rejected" 但 text=""

NovelEngine.batch_write (novel_engine.py:413)
  → ch2 成功落盘 rejected
  → ch3 抛异常（极可能是 plan_chapter 的 LLM 调用也返回空）
  → except Exception as e: continue           # ← 异常被吞
  → batch_progress 末尾被覆写为 "completed"，error_message 丢失
```

修复建议（不要立刻修，先看用户要不要继续这条路线）：

```python
# novel_engine.py:205
# 不要返回 ""，让它抛 RuntimeError 让上层捕获 + 记录错误
try:
    return self._call_writer(packet)
except RuntimeError:
    raise  # 让 batch_write 记到 error_message

# novel_engine.py:449
# 不要无脑 continue + 末尾覆写 completed
# 改成保留 failed 状态、停止后续章节、附带 LLM 返回的 receipt
```

### 4.3 max_tokens=4000 可能不够

`ROLE_CONFIGS["writer"]` 的 `max_tokens=4000`。qwen3.7-max 在 reasoning_effort=medium 时 thinking 会吃掉一部分 token 配额，可能导致 content 字段为空。**建议**：

- 对 OpenCode qwen 路径，把 writer 的 `max_tokens` 提到 8000-12000
- 或者把 `THINKING_MEDIUM` 改成 `THINKING_LOW` / disabled（qwen 系的 thinking 是它自己的 ReSim，跟 DeepSeek 不是一个机制）

### 4.4 小说模式 system prompt 缺性别约束

`novel_writer_adapter.py:17-80` 的 `WRITER_SYSTEM_PROMPT` 没有强约束角色性别/代词的条款。导致 max 在生成时默认"他"。需要加一条：

```
=== 角色代词 ===
严格按角色设定的性别使用代词。不得默认男他。女角色用"她"，未知用"其"。
```

---

## 五、关键发现

### 5.1 qwen3.7-max 的问题

- 单价是 plus 的数倍
- 8K 输出窗口内同句重复（"连续四十八小时没合眼"出现两次），说明长程一致性失守
- 同章内失眠时长 48h→72h 自相矛盾
- thinking 吃掉 max_tokens=4000 的全部配额，content 字段直接为空（这就是 ch02/ch03 失败的可疑元凶，虽然没拿到日志直接证实）

### 5.2 qwen3.7-plus 的预期

- 单价便宜
- thinking 更短，output 留得多
- 短篇/中篇一致性理论上比 max 更稳（未实测）
- **已切默认**（见 §2.3），但**还没跑过**

### 5.3 OpenCode 网关全 20 模型

```
deepseek-v4-pro, deepseek-v4-flash,
glm-5, glm-5.1, glm-5.2,
qwen3.5, qwen3.6, qwen3.7-plus, qwen3.7-max,
kimi-k2.5, kimi-k2.6, kimi-k2.7-code,
mimo-v2.0-flash, mimo-v2.5-pro, mimo-v2.5-flash,
minimax-m3, minimax-m3-flash, hy3-preview,
（部分以此为准，以 /v1/models 实时返回为准）
```

- 网文创作建议优先试 `qwen3.7-plus` / `glm-5.2` / `kimi-k2.6`，三者中文写作风格各有偏重，建议做 A/B 实测
- 不要用 `kimi-k2.7-code`，coding 模型写小说容易过于结构化

### 5.4 端到端调用流程

```bash
$env:NOVEL_LLM_PROVIDER = "opencode"
# OPENCODE_API_KEY 已在 env
# 可选：$env:NOVEL_LLM_MODEL_WRITER = "qwen3.7-plus"
python scripts/run_empty_rooms.py
```

后台跑（避免工具 timeout 把脚本杀掉）：

```bash
$p = Start-Process python -ArgumentList "scripts/run_empty_rooms.py" `
    -RedirectStandardOutput "qingmei_out/empty_rooms/run.log" `
    -RedirectStandardError "qingmei_out/empty_rooms/run.err.log" `
    -PassThru
$p.Id | Out-File qingmei_out/empty_rooms/pid.txt
```

输出：
- `qingmei_out/empty_rooms/chapter_0X.txt` 每章独立文件（实时落盘）
- `qingmei_out/empty_rooms/all_3_chapters.txt` 三章汇总
- `qingmei_out/empty_rooms/empty_rooms.db` SQLite 持久化全量
- `qingmei_out/empty_rooms/run.log` 标准输出日志

---

## 六、给后来者的优先级清单

按推荐顺序：

1. **跟用户对齐"不行"的具体维度**——节奏？对白腔？意象？还是单纯"读起来像 AI"？这一步不做，后面所有改都是猜。
2. **用 plus 重跑 3 章**（已经切好默认了），看 plus 是否也"不行"。如果 plus 也"不行"，根因是 system prompt / pipeline 设计而不是模型。
3. **若用户认可某种风格样本**（比如指定一个网文作家或一篇样章），把它喂给 `WRITER_SYSTEM_PROMPT` 做风格锚定。当前 prompt 是 oh-story 风格规则集，没有具体作者锚点。
4. **修 `_generate_with_beats` 吞 RuntimeError 的问题**（§4.2）——这跟质量无关，是个静默失败 bug，但修之前先问用户是否还要继续这条 novel 路线，否则白改。
5. **链路问题**：plan_chapter → write_chapter 之间没有"剧情梗概评审"。Architect 直接出 beat，Director 出指导，Writer 出正文，三者独立 LLM 调用，没有人审过"这一章在整本书的位置合理吗"。如果质量持续不达标，考虑加一层"剧情 review"或把 Architect 拆成"全书节奏 + 本章梗概"两段。

---

## 七、关键文件索引

```
adapters/llm/openai_compatible.py     新增 OpenAI 兼容 adapter
adapters/llm/model_profile_registry.py  6 个 opencode profile 注册
runtime/provider_adapter_factory.py   provider 路由
runtime/novel_llm_factory.py           novel 模式工厂（env 切换 / 模型覆盖）
runtime/novel_engine.py                NovelEngine 主体（batch_write 在 line 378）
runtime/novel_writer_adapter.py        Novel 模式 system prompt（line 17-80）+ LLM 调用（line 184）
runtime/novel_director_adapter.py       Novel Director
runtime/novel_architect_adapter.py     Novel Architect
scripts/run_empty_rooms.py             实战脚本模板
scripts/dump_reject.py                 DB 排障脚本
qingmei_out/empty_rooms/               空房间实战全部产物（ch01 8181 字 + ch02 空稿）
presets/writer/kedai_heavy_v1.txt      RP 模式 preset（与 novel 模式无关，别改这个找网文质量）
```

## 八、未提交

所有改动**没有 commit**。分支状态需自行 `git status` 确认。如果要继续：
1. ddl 改动应该有 commit 价值（OpenAICompatibleAdapter / 工厂路由 / NovelLLMFactory env 切换）
2. preset 重写是独立改动，单独 commit
3. 实战脚本和 `qingmei_out/` 路径不入库

---

## 九、一句话交接

> OpenCode Zen 接入打通了，调用流程也通了，但用 qwen3.7-max 写出的 Chapter 1 被用户判定"不行"。下一步先跟用户对齐具体不行的点，再用 plus 重跑验证；如果还是不行，根因在 `novel_writer_adapter.py::WRITER_SYSTEM_PROMPT` 的设计，不在网关或代码层面。