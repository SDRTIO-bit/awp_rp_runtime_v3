# Daily High School Opening Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Strengthen the pure-realistic campus-romcom opening and generate validated chapters 1—3 through the Novel Pipeline.

**Architecture:** \`outline.md\` supplies Architect tasks; concise \`guidance/chapter_NN.md\` files give both Architect and Writer non-negotiable chapter boundaries. \`project.json\` remains canonical for volume-level facts. The CLI synchronizes these sources to SQLite, then sequentially runs Architect → Director → Writer → Quality.

**Tech Stack:** Markdown, JSON, Python 3.10+, SQLite, \`scripts/novel_cli.py\`.

## Global Constraints

- No system, superpower, affinity mechanic, or hidden all-round genius.
- Each chapter targets 2,000—2,600 Chinese characters and contains no inner headings.
- Chen Mo succeeds through observation, empathy, humour and action that preserves others' dignity.
- Chapters 1—3 focus on Shen Xi; Zhao Xiaomai is not named or romantically foregrounded.
- Zhao Xiaomai is a same-class PE representative: functional presence starts in chapter 5 and sports responsibility in chapter 10.
- Shen Xi remains competent; chapter 12 uses a teammate withdrawal rather than a clerical mistake.

---

### Task 1: Rewrite first-volume source data

**Files:**

- Modify: \`novels/daily_high_school/outline.md\`
- Modify: \`novels/daily_high_school/project.json\`
- Modify: \`novels/daily_high_school/story_bible.md\`
- Modify: \`novels/daily_high_school/world.md\`
- Test: inline Markdown and JSON assertions

**Interfaces:**

- Consumes: \`docs/superpowers/specs/2026-07-12-daily-high-school-volume-1-opening-design.md\`
- Produces: chapter \`任务描述\` values parsed by \`scripts/novel_cli.py::_parse_outline()\`.

- [ ] **Step 1: Record the pre-change failure**

Run:

\`\`\`powershell
@'
from pathlib import Path
assert "教材危机闭环" in Path("novels/daily_high_school/outline.md").read_text(encoding="utf-8")
'@ | python -
\`\`\`

Expected: \`AssertionError\`.

- [ ] **Step 2: Rewrite chapters 1—15 in \`outline.md\`**

Replace chapter tasks with the approved structure: chapters 1—3 are a continuous textbook-crisis loop; chapter 1 ends with Chen Mo deciding to find the wrong box, chapter 2 ends one book short after he returns the bundle without embarrassing the other class, and chapter 3 closes the crisis when Shen Xi nominates him as her helper. Preserve chapters 4—14 events but encode the three escalation blocks: \`搭档变默契（4—6）\`, \`恋爱喜剧首次兑现（7—9）\`, and \`运动会危机与奶茶条约（10—14）\`. Rename chapter 12 to \`临时退出的人\`; end chapter 14 with Zhao Xiaomai placing a stopwatch and test sign-up sheet on Chen Mo's desk. Make chapter 15 the formal test where Zhao Xiaomai notices he is holding back.

- [ ] **Step 3: Update volume metadata**

In \`project.json\`, retain all IDs and set Zhao Xiaomai's \`first_appearance\` from \`2\` to \`5\`. Add \`教材危机闭环\` and \`赵小麦秒表交接\` to the first chapter block anchors, replace the second block's first anchor with \`正式测试与放水\`, and revise \`volume.core_conflict\` to include Chen Mo using jokes to avoid seriousness while preserving others' dignity. Make matching chapter 1—15 and Zhao Xiaomai timing changes in \`story_bible.md\` and \`world.md\`, because the Plan Agent reads both files as higher-level context.

- [ ] **Step 4: Run source acceptance checks**

\`\`\`powershell
@'
import json
from pathlib import Path
outline = Path("novels/daily_high_school/outline.md").read_text(encoding="utf-8")
for phrase in ("教材危机", "第3章 班长抓了个壮丁", "临时退出的人", "第15章", "正式测试"):
    assert phrase in outline, phrase
data = json.loads(Path("novels/daily_high_school/project.json").read_text(encoding="utf-8"))
zhao = next(item for item in data["characters"] if item["name"] == "赵小麦")
assert data["project"]["id"] == "daily-high-school"
assert zhao["first_appearance"] == 5
assert "教材危机闭环" in data["volume"]["chapter_blocks"][0]["anchor_events"]
'@ | python -
\`\`\`

Expected: process exits \`0\`.

- [ ] **Step 5: Commit source data**

\`\`\`powershell
git add novels/daily_high_school/outline.md novels/daily_high_school/project.json
git commit -m "feat: strengthen daily high school opening arc"
\`\`\`

### Task 2: Add chapter-local pipeline guidance

**Files:**

- Create: \`novels/daily_high_school/guidance/chapter_01.md\`
- Create: \`novels/daily_high_school/guidance/chapter_02.md\`
- Create: \`novels/daily_high_school/guidance/chapter_03.md\`
- Test: \`tests/test_novel_writer_context.py\`

**Interfaces:**

- Consumes: \`scripts/novel_cli.py::_load_plan_guidance()\` and \`_load_writer_guidance()\`.
- Produces: compact non-negotiable constraints shared by Plan and Writer agents.

- [ ] **Step 1: Record the pre-change failure**

\`\`\`powershell
Test-Path novels/daily_high_school/guidance/chapter_01.md
\`\`\`

Expected: \`False\`.

- [ ] **Step 2: Create bounded guidance**

\`chapter_01.md\` requires the opening within 100 characters, only the discovery that a full box was sent wrongly, no Zhao Xiaomai name/romance, and an ending at Chen Mo's decision to retrieve books. \`chapter_02.md\` requires a face-preserving exchange, forbids genius framing, retains one-book shortfall, and excludes Zhao Xiaomai. \`chapter_03.md\` requires shared-book choice, Shen Xi's voluntary nomination, unrecorded tardy slip, textbook-crisis closure, and excludes Zhao Xiaomai romance. None may duplicate the entire story bible.

- [ ] **Step 3: Verify the guidance boundary**

\`\`\`powershell
python -m pytest tests/test_novel_writer_context.py -q
@'
from pathlib import Path
for index in range(1, 4):
    text = Path(f"novels/daily_high_school/guidance/chapter_{index:02d}.md").read_text(encoding="utf-8")
    assert "赵小麦" in text
'@ | python -
\`\`\`

Expected: tests pass and assertions exit \`0\`.

- [ ] **Step 4: Commit guidance**

\`\`\`powershell
git add novels/daily_high_school/guidance
git commit -m "feat: guide daily high school opening chapters"
\`\`\`

### Task 3: Run and validate the real three-chapter pipeline

**Files:**

- Runtime update: \`novels/daily_high_school/novel.db\`
- Runtime output: \`novels/daily_high_school/output/chapter_01.md\`
- Runtime output: \`novels/daily_high_school/output/chapter_02.md\`
- Runtime output: \`novels/daily_high_school/output/chapter_03.md\`
- Runtime output: \`novels/daily_high_school/output/opening_pipeline_report.json\`

**Interfaces:**

- Consumes: \`novel_cli.py seed\`, \`plan\`, and \`write --stream\`.
- Produces: chronological plan/draft/ledger state for chapters 1—3.

- [ ] **Step 1: Synchronize source files**

\`\`\`powershell
python scripts/novel_cli.py seed novels/daily_high_school
\`\`\`

Expected: the CLI identifies \`daily-high-school\` without an exception.

- [ ] **Step 2: Run chronologically**

\`\`\`powershell
python scripts/novel_cli.py plan novels/daily_high_school 1
python scripts/novel_cli.py write novels/daily_high_school 1 --stream
python scripts/novel_cli.py plan novels/daily_high_school 2
python scripts/novel_cli.py write novels/daily_high_school 2 --stream
python scripts/novel_cli.py plan novels/daily_high_school 3
python scripts/novel_cli.py write novels/daily_high_school 3 --stream
\`\`\`

Expected: every chapter is accepted by Quality and saved under \`output/\`.

- [ ] **Step 3: Validate generated opening**

\`\`\`powershell
@'
import json
from pathlib import Path
output = Path("novels/daily_high_school/output")
texts = {i: (output / f"chapter_{i:02d}.md").read_text(encoding="utf-8") for i in range(1, 4)}
for i, text in texts.items():
    assert 1800 <= len(text) <= 3000, (i, len(text))
    assert "## " not in text and "### " not in text
    assert "赵小麦" not in text
    assert "教材" in text
report = {"char_counts": {str(i): len(text) for i, text in texts.items()}, "zhao_xiaomai_in_opening": False}
(output / "opening_pipeline_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
'@ | python -
\`\`\`

Then read the three drafts: chapter 1 must end at the retrieval decision, chapter 2 at the one-book shortfall, and chapter 3 at both crisis closure and Shen Xi's nomination.

- [ ] **Step 4: Report without committing runtime data**

Do not commit \`novel.db\` or generated drafts unless requested. Report absolute output paths, plan/draft character counts, Quality status, and any single revision made after reading.
