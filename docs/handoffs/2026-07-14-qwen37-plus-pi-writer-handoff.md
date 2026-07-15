# 交接报告：Qwen 3.7 Plus × Pi 小说 Writer 空输出排障

日期：2026-07-14  
状态：**未完成；已停止修改，等待后续 Agent 接手。**

## 1. 当前目标

用户已决定不再使用 Kimi，小说 Pi 管线改用 OpenCode 的 `qwen3.7-plus`。正文目标为：

- 单场景、单次 Writer 调用；不拼接多 beat；
- 目标约 2000 字符；
- Pi Writer 能稳定返回正文；
- 上下文窗当前为 131,072 tokens，低于 Qwen 3.7 Plus 的 256K 价格分界线。

## 2. 工作区与 Git 状态

- 工作树：`F:\12\语英\awp_rp_runtime_v3\.worktrees\pi-novel-role-agents`
- 分支：`codex/pi-novel-role-agents`
- 最新已提交：`ec061fd4 fix: reserve kimi writer output budget`
- **尚未合并到 main。**
- 当前有且仅有 3 个未提交文件：

  - `runtime/novel_llm_factory.py`
  - `tests/test_novel_llm_factory.py`
  - `tests/test_novel_pi_role_e2e.py`

这些未提交改动的意图是把验收模型从 Kimi 改为 Qwen，并在 Qwen Writer 上将 Pi thinking level 设为 `off`。不要把它们误认为已验收完成。

## 3. 已确认事实（带证据）

### 3.1 第一次真实 Qwen 验收：请求在服务端被拒绝

运行命令：

```powershell
$env:NOVEL_AGENT_RUNTIME='pi'
$env:NOVEL_LLM_PROVIDER='opencode'
$env:NOVEL_LLM_MODEL='qwen3.7-plus'
$env:NOVEL_PI_ROLE_E2E='1'
python -m pytest tests/test_novel_pi_role_e2e.py -vv -s
```

结果：约 2 分 47 秒失败。Architect/Director 已正常返回，Writer 连续重试后为空。

Writer Pi session 的真实错误：

```text
400: Error from provider (Alibaba):
max_completion_tokens [4000] must be greater than thinking_budget [32768]
```

会话文件位于：

```text
C:\Users\zhao\AppData\Local\Temp\pytest-of-zhao\pytest-568\test_real_qwen_plan_write_audi0\.awp\pi-role-sessions\4cbbdcb14206c3d36004fee0\*.jsonl
```

结论：Writer 的 4000 token 输出上限和 Qwen 的默认 32768 thinking budget 不兼容；此时不是正文质量问题，也不是桥接丢文本。

### 3.2 已做的最小修复：Factory 将 Qwen Writer 标记为 off

未提交的 `runtime/novel_llm_factory.py` 包含：

```python
if role == "writer" and "qwen3.7-plus" in model.lower():
    thinking_level = "off"
```

对应测试已按 TDD 执行：先将断言改为 `off`，观察失败；加入以上最小改动后执行：

```text
python -m pytest tests/test_novel_llm_factory.py -q
2 passed
```

### 3.3 第二次真实 Qwen 验收：400 消失，但 Writer 仍耗尽输出在思考中

同一命令重跑后，约 4 分 53 秒失败，仍然是 `Writer returned empty output`，但已**没有** 400 参数错误。

Writer session 真实最后一条结果：

```text
stopReason = length
content = [('thinking', 11787 chars)]
usage.output = 4002
usage.reasoning = 4000
text blocks = 0
```

会话文件位于：

```text
C:\Users\zhao\AppData\Local\Temp\pytest-of-zhao\pytest-569\test_real_qwen_plan_write_audi0\.awp\pi-role-sessions\4cbbdcb14206c3d36004fee0\*.jsonl
```

结论：Pi session 元数据虽然已记录 `thinking_level=off`，但 OpenCode 上的 Qwen 仍默认启用了思考。Pi 对此模型目前没有发送 Qwen 原生控制字段，因此模型将全部 4000 completion tokens 用于 thinking，最终没有正文。

## 4. 唯一建议的下一步（尚未实施）

不要继续增加 Writer 的 `max_tokens`，这会掩盖问题、增加成本，也违反 2000 字单章的目标。

最小待验证假设：在 `agent_harness/src/novel_role_host.mjs` 为 `qwen3.7-plus` 注册 Pi 的 Qwen 兼容格式。

Pi 依赖的本地实现已经显示：当模型配置为 `compat.thinkingFormat === "qwen"` 且 `model.reasoning === true` 时，会发送：

```json
{"enable_thinking": false}
```

对应依赖位置：

```text
agent_harness/node_modules/@earendil-works/pi-coding-agent/node_modules/
@earendil-works/pi-ai/dist/api/openai-completions.js:480-482
```

建议的实施顺序：

1. 先在 `agent_harness/test/novel_role_host.test.mjs` 写一个失败测试：使用本地 HTTP mock 捕获 Pi 请求体，断言 Qwen Writer 的 off 模式请求含 `enable_thinking: false`。
2. 仅在 host 的动态模型规格中加入 Qwen 3.7 Plus 专用配置：`reasoning: true`、`compat: { thinkingFormat: "qwen", supportsReasoningEffort: false }`；其余模型行为不变。
3. 跑 Node 请求体测试，再跑 `tests/test_novel_llm_factory.py`。
4. 使用第 3.1 节命令重新跑真实 E2E，验收条件：
   - Writer 产生 text block；
   - `draft.text` ≥ 1600 字符；
   - `plan.target_chars == 2000`；
   - Architect、Director、Writer、ContinuityChecker、LedgerCurator 均参与；
   - 会话日志中 Writer 不再只有 thinking block。
5. 通过后才跑完整 `python -m pytest tests -q`、提交并合并。

如果 OpenCode 网关不识别/不透传 `enable_thinking`，应停止继续猜测参数，记录网关响应并改为支持该参数的 Qwen 原生/兼容端点；当前尚未证明这一点。

## 5. 已验证测试与未验证项

已通过：

```text
agent_harness: npm test  -> 14 passed
tests/test_novel_llm_factory.py -> 2 passed（Qwen Writer off 的 Factory 断言）
```

未完成：

- Qwen 真正 E2E（两次均失败，原因见上）；
- 全量 `python -m pytest tests -q`（此前运行被用户中断，不应声称通过）；
- 提交、合并。

## 6. 相关文件

- `runtime/novel_llm_factory.py`：角色模型、token、thinking level 的来源。
- `agent_harness/src/novel_role_host.mjs`：Pi 模型注册；后续 Qwen 请求参数映射应在此处实现。
- `tests/test_novel_llm_factory.py`：当前 Qwen Factory 的未提交回归断言。
- `tests/test_novel_pi_role_e2e.py`：已改名为 Qwen 的真实外部验收测试。
- `runtime/novel_engine.py:307`：Writer 空输出最终抛出的统一异常；这里不是根因。

## 7. 避免重复踩坑

- `thinking_level="off"` 仅改变 Pi 内部级别，不保证 OpenCode/Qwen 端收到关闭思考的 provider 参数。
- 不要仅从 session metadata 的 `thinking_level_change=off` 判断模型思考已关闭；必须检查实际请求体或返回 content blocks。
- 不要为绕过 32K thinking budget 直接把 4K Writer cap 提到 32K 以上；先尝试显式关闭 thinking。
- Kimi 已被用户明确弃用；本轮不要重新切回 Kimi。
