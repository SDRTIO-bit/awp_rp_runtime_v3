# Refactoring Plan: 模块权限重新分配 (v2 — 已修正结构冲突)

> 目标：Writer 负责创作，Mechanical Gate 负责纠错，Reviewer 负责提问，作者负责决定。
> 核心策略：**拆而不是砍**。P0 只重分配代码归属，不改变运行行为。
>
> 修正记录（2026-07-25）：
> 1. `_style_cleaner` 兼容属性与旁路 CLI 冲突 → 移除别名，CLI 直接实例化旧类
> 2. `_run_audit()` 双重归属 → HARD 归 Mechanical，STYLE 留旧类，旧类继承新类
> 3. P0.2 措辞歧义 → 改为"保留但冻结"
> 4. 按调用图提取而非按行数 → 从公共入口向下追踪
> 5. 新增"行为零变化"测试标准
> 6. 弃用警告不污染正常写章路径
> 7. P3 触发条件增加分布约束
> 8. 最终文件关系 → 单向继承，无循环依赖
> 9. P0 完成标准 → 9 项硬性条件

---

## 最终 P0 文件关系

```
runtime/
├── novel_mechanical_gate.py          # NEW — 机械层核心
│   └── NovelMechanicalGate
│       ├── polish_chapter_text()     # 公共入口（HARD-only）
│       ├── _run_hard_loop()          # HARD 审计回路
│       ├── _run_hard_audit()         # → 原 _run_audit(HARD)，已重命名
│       ├── _run_patch_gen()          # 精确补丁生成
│       ├── _run_verify()             # 对抗性验收
│       ├── _apply_patches()          # 确定性补丁应用
│       ├── _build_constraint_prompt()
│       ├── _call_llm_json()          # 共享 LLM 调用
│       ├── _strip_boilerplate()      # COT/状态表清除
│       ├── _looks_truncated_or_broken()
│       ├── clean_plan()              # static: Plan 文本清理
│       ├── check_metadata_leak()     # 确定性检测
│       ├── check_degeneration()      # 复读/截断/AI拒绝
│       ├── check_scene_repeat()      # 开场指纹
│       ├── check_chapter_structure() # 结构检查
│       ├── normalize_punctuation()   # 标点规范化
│       ├── full_check()              # 综合确定性检查
│       └── 常量：_AUDIT_SYSTEM_PROMPT, _PATCH_SYSTEM_PROMPT,
│                   _VERIFY_SYSTEM_PROMPT, _FOCAL_CHARACTER,
│                   _POV_MODE, _PATCH_BUDGET, _PATCH_BUDGET_STYLE, etc.
│
├── novel_style_cleaner.py            # MODIFIED — deprecated, 保留旁路工具
│   └── NovelStyleCleaner(NovelMechanicalGate)  # 继承新类
│       ├── __init__() → warn(DeprecationWarning)
│       ├── _run_style_audit()        # → 原 _run_audit(STYLE)，已重命名
│       ├── _run_design_audit()       # 设计过载审计 (D1-D5)
│       ├── check_banned_words()      # 已冻结，仅旁路
│       ├── check_banned_patterns()   # 已冻结，仅旁路
│       ├── check_drumbeat_density()  # 已冻结，仅旁路
│       ├── find_drumbeat_regions()   # 已冻结
│       ├── rewrite_drumbeat_snippets()     # 已冻结
│       ├── rewrite_for_issues()        # 已冻结
│       ├── _run_style_loop()          # 已冻结
│       └── _run_style_role()          # 共享（Pi role 调用）
│
├── novel_engine.py                   # MODIFIED — 只构造 NovelMechanicalGate
│   └── NovelEngine
│       ├── self._mechanical_gate = NovelMechanicalGate(registry)
│       └── @property _style_cleaner → warned compat alias
│
└── novel_quality_pipeline.py         # MODIFIED — import 切换

依赖方向（单向，无循环）：
  novel_style_cleaner → imports → novel_mechanical_gate
```

**CLI 调用关系：**

```
write / write-stream
    ↓
NovelEngine._mechanical_gate (NovelMechanicalGate)

audit-style / audit-design
    ↓
NovelStyleCleaner(registry)  ← 直接实例化旧类
```

---

## Phase 0: 冻结与拆分

### 0.0 预检：仓库级搜索（执行前必须运行）

```bash
rg -n "NovelStyleCleaner|_style_cleaner|novel_style_cleaner" .
rg -n "_run_hard_loop|_run_audit|_run_patch_gen|_run_verify|_apply_patches" .
rg -n "clean_plan|clean_drumbeat_text|full_check|normalize_punctuation" .
rg -n "check_metadata_leak|check_degeneration|check_scene_repeat|check_chapter_structure" .
rg -n "_strip_boilerplate|_looks_truncated|BANNED_WORDS|BANNED_PATTERNS|_DRUMBEAT" .
```

**提取规则：** 从以下 Mechanical 公共入口向下追踪调用图，只有**从这些入口可达的方法和常量**才移入新文件：

```
polish_chapter_text()
full_check()
clean_plan()
check_metadata_leak()
check_degeneration()
check_scene_repeat()
check_chapter_structure()
normalize_punctuation()
```

特别注意 `clean_drumbeat_text()`：先看调用关系。如果只被 deprecated 旁路调用，不移入 Mechanical Gate。

### 0.1 创建 `runtime/novel_mechanical_gate.py`

封装为 `NovelMechanicalGate` 类。所有从 Mechanical 公共入口可达的方法和常量纳入。

**常量重命名（避免与旧类冲突）：** 所有移入常量保持原名，由继承关系确保旧类可访问。

**方法重命名（消除 _run_audit 双重归属）：**

| 原方法名 | 新归属 | 新方法名 |
|---|---|---|
| `_run_audit(HARD)` | `NovelMechanicalGate` | `_run_hard_audit()` |
| `_run_audit(STYLE)` | `NovelStyleCleaner` | `_run_style_audit()` |

`_run_hard_loop()` 内部调用 `self._run_hard_audit()`。

### 0.2 更新 `novel_style_cleaner.py` — 继承新类，标记 deprecated

```python
# DEPRECATED since 2026-07-25.
# Use novel_mechanical_gate.py for HARD audit in the write path.
# This module remains for offline audit tools (audit-design, audit-style).

import warnings
from .novel_mechanical_gate import NovelMechanicalGate


class NovelStyleCleaner(NovelMechanicalGate):
    """Deprecated — offline analysis tools only."""

    def __init__(self, registry, model="deepseek-v4-pro"):
        warnings.warn(
            "NovelStyleCleaner is deprecated. Use NovelMechanicalGate for "
            "the write path. This class is retained for audit-design / "
            "audit-style CLI tools only.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(registry)

    def _run_style_audit(self, text, *, plot_beats=()):
        """STYLE audit — offline only."""
        return self._run_hard_audit.__wrapped__  # ... 实际实现
        
    def _run_design_audit(self, text, *, plot_beats=()):
        """DESIGN audit — offline only."""
        ...

    # 以下方法全部保留但冻结，不进入 write_chapter() 热路径：
    # check_banned_words, check_banned_patterns, check_drumbeat_density,
    # find_drumbeat_regions, rewrite_drumbeat_snippets, rewrite_for_issues,
    # _run_style_loop
```

**保留但冻结所有 V1-V3 降级能力**，包括 banned words、drumbeat、rewrite 和 STYLE loop。不得从 `write_chapter()` 或 Mechanical Gate 调用，仅供历史兼容和旁路 CLI 使用。

### 0.3 更新 `novel_engine.py` — 切换到新模块

```python
# import 变更
from .novel_mechanical_gate import NovelMechanicalGate

# __init__ 变更
self._mechanical_gate = NovelMechanicalGate(registry)

# 向后兼容属性（仅保证机械调用不炸）
@property
def _style_cleaner(self):
    import warnings
    warnings.warn(
        "engine._style_cleaner is deprecated; use engine._mechanical_gate",
        DeprecationWarning,
        stacklevel=2,
    )
    return self._mechanical_gate
```

所有 `self._style_cleaner.polish_chapter_text(...)` → `self._mechanical_gate.polish_chapter_text(...)`
所有 `NovelStyleCleaner.clean_plan(...)` → `NovelMechanicalGate.clean_plan(...)`

### 0.4 更新 `novel_quality_pipeline.py`

import 切换到 `novel_mechanical_gate`。

### 0.5 更新 CLI — `audit-design` / `audit-style`

直接实例化旧类，不再经过 `engine._style_cleaner`：

```python
# cmd_audit_design
from runtime.novel_style_cleaner import NovelStyleCleaner
legacy_cleaner = NovelStyleCleaner(registry)
report = legacy_cleaner._run_design_audit(text)

# cmd_audit_style
from runtime.novel_style_cleaner import NovelStyleCleaner
legacy_cleaner = NovelStyleCleaner(registry)
report = legacy_cleaner._run_style_audit(text)
```

### 0.6 更新测试文件

测试文件 import 切换到 `novel_mechanical_gate`。同时新增迁移同值测试：

```python
# tests/test_novel_mechanical_gate_migration.py (新增)

def test_mechanical_apply_patches_behavior_is_preserved():
    ...

def test_mechanical_strip_boilerplate_behavior_is_preserved():
    ...

def test_mechanical_clean_plan_behavior_is_preserved():
    ...

def test_mechanical_full_check_behavior_is_preserved():
    ...

def test_engine_write_path_uses_mechanical_gate():
    ...

def test_normal_write_path_does_not_construct_legacy_style_cleaner():
    ...

def test_legacy_design_audit_remains_callable():
    ...

def test_legacy_style_audit_remains_callable():
    ...

def test_engine_init_does_not_emit_style_cleaner_deprecation():
    # 关键：正常写章路径不应出现弃用警告
```

测试验收标准：**相同输入 + 相同 mock LLM 响应 = 相同正文 + 相同报告 + 相同回退行为。** 除类名、实例属性名、import 路径和 deprecation warning 外，不得出现任何可观察行为变化。

### 0.7 编译与测试验证

```bash
python -c "import py_compile; py_compile.compile('runtime/novel_mechanical_gate.py', doraise=True)"
python -c "import py_compile; py_compile.compile('runtime/novel_engine.py', doraise=True)"
python -c "import py_compile; py_compile.compile('runtime/novel_quality_pipeline.py', doraise=True)"
python -m pytest tests/ -q  # 确保全部测试通过
```

### 0.8 P0 完成标准

- [ ] `novel_engine.py` 热路径不再 import 或实例化 `NovelStyleCleaner`
- [ ] Mechanical 公共行为与拆分前一致（迁移同值测试通过）
- [ ] 旧 `audit-design` 和 `audit-style` 仍可运行
- [ ] 仓库内所有旧引用均经过人工确认
- [ ] 不存在循环依赖（`novel_style_cleaner` → `novel_mechanical_gate`，单向）
- [ ] 正常写章不触发弃用警告
- [ ] 981 项现有测试通过
- [ ] 新增 9 项迁移同值测试通过
- [ ] `git diff` 中没有 Prompt 内容、阈值、预算或控制流变化

---

## Phase 1: Reader Comfort Reviewer (P1 — 依赖 P0 完成)

### 1.1 Friction type 定义

```python
# 8 类摩擦，4 类 Micro-Causal + 4 类 Creative

class FrictionType:
    # Micro-Causal (读者能否理解人物为什么这么做)
    UNCLEAR_IMMEDIATE_GOAL = "C01_UNCLEAR_IMMEDIATE_GOAL"
    UNSUPPORTED_ACTION = "C02_UNSUPPORTED_ACTION"
    IGNORED_SIMPLE_ALTERNATIVE = "C03_IGNORED_SIMPLE_ALTERNATIVE"
    CAUSAL_JUMP = "C04_CAUSAL_JUMP"
    # Creative (读者是否愿意接受这个人/这段关系)
    CHARACTER_BOUNDARY_RISK = "C05_CHARACTER_BOUNDARY_RISK"
    RELATIONSHIP_FORCING = "C06_RELATIONSHIP_FORCING"
    SCENE_OVERLOAD = "C07_SCENE_OVERLOAD"
    NARRATIVE_READER_MISMATCH = "C08_NARRATIVE_READER_MISMATCH"
```

### 1.2 创建 `runtime/novel_reader_comfort_reviewer.py`

只读模块，`NovelReaderComfortReviewer` 类。不修改正文。

**输出字段：**

```json
{
  "friction_id": "F-001",
  "text_span": "...",
  "location": {"paragraph": 47, "start_offset": 12, "end_offset": 27},
  "likely_reader_question": "...",
  "missing_support": "...",
  "friction_type": "C02_UNSUPPORTED_ACTION",
  "reader_effect": "...",
  "intentionality": "unclear",
  "narrative_acknowledgement": "absent",
  "productive_or_blocking": "blocking",
  "mechanical_or_creative": "creative",
  "severity": "high",
  "confidence": 0.88,
  "author_questions": ["...", "..."],
  "author_decision_needed": true
}
```

**Reviewer 只能输出 `likely_reader_question` 和 `author_questions`，不能输出 `replacement_text` 或 "正确写法"。**

### 1.3 新增 CLI 命令

```bash
python scripts/novel_cli.py review-comfort <dir> <chapter>
python scripts/novel_cli.py review-comfort <dir> <chapter> --output report.json
```

---

## Phase 2: 人工确认体系 (P2 — 依赖 P1 完成)

### 2.1 样本文件结构

```
data/friction_samples/
├── pending.jsonl
├── confirmed.jsonl
├── rejected.jsonl
└── uncertain.jsonl
```

### 2.2 新增 CLI 命令

```bash
python scripts/novel_cli.py review-confirm <dir> <report_id> --verdict blocking --note "..."
python scripts/novel_cli.py review-stats <dir> [--writer-model MODEL]
```

---

## Phase 3: Architect 校准 (P3 — 依赖 P2 完成)

### 3.1 触发条件（已增加分布约束）

同一摩擦类型必须同时满足：

```
- confirmed ≥ 10
- 来自至少 3 个不同章节
- 来自至少 2 种不同场景类型
- Reviewer 在该类型上的人工确认率 ≥ 预设门槛
```

例：

```json
{
  "friction_type": "C03_IGNORED_SIMPLE_ALTERNATIVE",
  "confirmed_count": 12,
  "distinct_chapters": 5,
  "distinct_scene_types": 3,
  "precision": 0.81,
  "architect_calibration_eligible": true
}
```

### 3.2 调整方式

- **不**给 Writer 加禁令
- **不**把样本库塞进提示词
- 只调整 Architect 的路径规划约束

---

## 文件清单

| 操作 | 文件 | 说明 |
|---|---|---|
| **新增** | `runtime/novel_mechanical_gate.py` | Mechanical Gate 核心 |
| **新增** | `runtime/novel_reader_comfort_reviewer.py` | P1: Reviewer |
| **新增** | `tests/test_novel_mechanical_gate_migration.py` | P0 迁移同值测试 |
| **新增** | `data/friction_samples/` 目录 | P2: 样本目录 |
| **修改** | `runtime/novel_style_cleaner.py` | 继承新类 + deprecated 标记 |
| **修改** | `runtime/novel_engine.py` | import 切换 + compat @property |
| **修改** | `runtime/novel_quality_pipeline.py` | import 切换 |
| **修改** | `scripts/novel_cli.py` | 3 个新命令 + audit 直接实例化旧类 |
| **修改** | `tests/test_novel_*.py` (3 文件) | import 切换 |

---

## 实施顺序

```
P0.0  预检：仓库级搜索，确认调用图
  ↓
P0.1  创建 novel_mechanical_gate.py（按调用图提取）
  ↓
P0.2  重写 novel_style_cleaner.py（继承新类 + deprecated）
  ↓
P0.3  novel_engine.py import 切换 + compat @property
  ↓
P0.4  novel_quality_pipeline.py import 切换
  ↓
P0.5  CLI audit 命令直接实例化旧类
  ↓
P0.6  更新测试文件 + 新增迁移同值测试
  ↓
P0.7  编译 + 全部测试通过
  ↓
P0.8  对照 9 项完成标准逐条确认
  ↓
P1    创建 Reviewer + review-comfort CLI
  ↓
P2    人工确认体系 + review-confirm / review-stats CLI
  ↓
P3    Architect 校准（需积累样本后触发）
```
