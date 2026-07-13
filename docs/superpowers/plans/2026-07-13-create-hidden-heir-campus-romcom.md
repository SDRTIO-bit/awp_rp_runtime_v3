# Hidden-Heir Campus Romcom Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a completely isolated novel project for 《告白事故与我无关》, write and audit its 50-chapter outline before designing the cast, then generate and audit the first three chapters through the full novel pipeline.

**Architecture:** The project is file-driven and lives under `novels/告白事故与我无关`. `outline.md` is the first creative source of truth; character cards are derived from the approved plot rather than written first. After the outline and cast are stable, the existing Architect → Director → Writer → Quality → Ledger CLI seeds a new SQLite database and generates chapters sequentially.

**Tech Stack:** UTF-8 Markdown, JSON, Python 3.10+, existing `scripts/novel_cli.py`, SQLite, PowerShell verification commands.

## Global Constraints

- Do not modify, seed from, copy the database of, or write outputs into `novels/校园小说`.
- New project directory is exactly `novels/告白事故与我无关` and project id is exactly `confession-accident`.
- Write and structurally audit all 50 chapter beats before creating detailed character cards.
- The first 50 chapters contain four fully entered main heroines, two forceful heroine seeds, and no formal seventh-heroine arc.
- All heroines and Chen Mo remain unaware of his true family identity throughout the first 50 chapters.
- Chapter 1 enters the stage accident within the first 300 Chinese characters; it does not open with school exposition or wage calculation.
- Hidden-identity anomalies may complicate events but may not solve romantic, disciplinary, club, or student-government conflicts.
- A returning heroine must change the current causal chain; do not add empty hallway, cafeteria, or roll-call cameos.
- Use global prompts `prompts/writer.md` and `prompts/architect_romcom.md` by project-level prompt names; do not edit global prompt files for this project.
- Preserve all unrelated dirty-worktree changes. Stage and commit only paths explicitly listed in each task.
- Use `apply_patch` for project text-file creation and edits.

---

## File Map

- `novels/告白事故与我无关/project.json` — pipeline metadata, volume policy, finalized characters, prompt selection, and hard limits.
- `novels/告白事故与我无关/outline.md` — 50 chapter-level causal contracts; written before detailed characters.
- `novels/告白事故与我无关/outline_audit.md` — structural audit, repetition findings, payoff map, and corrections made to the outline.
- `novels/告白事故与我无关/relationship_calendar.md` — chapter-by-chapter presence and causal contribution of each introduced heroine.
- `novels/告白事故与我无关/story_bible.md` — character-derived story canon written after outline approval.
- `novels/告白事故与我无关/world.md` — parallel-world school rules, class structure, identity information rules, and location constraints.
- `novels/告白事故与我无关/reference_benchmark.txt` — concise prose behavior reference for the Writer; no copied novel passages.
- `novels/告白事故与我无关/audit_skill.md` — project-local outline/chapter audit workflow and safe reset boundaries.
- `novels/告白事故与我无关/guidance/WRITING_STANDARD.md` — compact chapter-writing contract.
- `novels/告白事故与我无关/guidance/chapter_01.md` — cold-open and Chapter 1 decision guidance.
- `novels/告白事故与我无关/guidance/chapter_02.md` — pursuit/accountability guidance.
- `novels/告白事故与我无关/guidance/chapter_03.md` — first three-chapter payoff guidance.
- `novels/告白事故与我无关/novel.db` — new runtime database created only after outline and characters are approved.
- `novels/告白事故与我无关/output/chapter_01.md` through `chapter_03.md` — pipeline-generated test chapters.

---

### Task 1: Scaffold the Isolated Project and Write the 50-Chapter Outline

**Files:**
- Create: `novels/告白事故与我无关/project.json`
- Create: `novels/告白事故与我无关/world.md`
- Create: `novels/告白事故与我无关/outline.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-07-13-hidden-heir-campus-romcom-design.md`.
- Produces: a parseable 50-chapter `outline.md`; a metadata-only `project.json` with `"characters": []`; a minimal `world.md` containing only already-approved setting rules.

- [ ] **Step 1: Create the metadata-only project shell**

Use `apply_patch` to create `project.json` with:

```json
{
  "project": {
    "id": "confession-accident",
    "title": "告白事故与我无关",
    "genre": "平行世界、财阀学园、多女主恋爱喜剧、轻小说式长篇",
    "core_emotion": "公开处刑式爆笑→被迫共谋→群像偏袒→身份疑云",
    "one_sentence_pitch": "以为自己是奖学金生的陈默被陌生女孩拽上告白舞台，从此不断卷入败犬少女们无法按剧本收场的青春事故。",
    "target_reader": "16—28岁校园恋爱喜剧读者",
    "target_platform": "番茄长篇",
    "config": {
      "writer_prompt": "writer",
      "architect_prompt": "architect_romcom",
      "story_bible": "story_bible.md",
      "canon_priority": ["project.json", "story_bible.md", "world.md", "outline.md"],
      "runtime_state_policy": "本项目使用独立novel.db；不得注入其他小说项目的账本、角色或章节。"
    }
  },
  "volume": {
    "index": 1,
    "title": "第一卷：告白字幕停不下来了",
    "chapter_start": 1,
    "chapter_end": 50
  },
  "characters": []
}
```

Do not run `seed`; detailed characters do not exist yet.

- [ ] **Step 2: Create the minimal world contract**

Use `apply_patch` to create `world.md` with only these approved sections: East Continent Federation; White Birch Academy; high-school second year start; clubs/student government/school festival; mixed financial classes; Chen Mo's post-accident information boundary; no heroine knows the hidden identity; identity clues cannot solve visible conflicts. Do not add character biographies.

- [ ] **Step 3: Write Chapters 1–10 in `outline.md`**

Use this exact field set for every chapter:

```markdown
## 第N章 标题
- 定位:
- 立即目标:
- 阻力:
- 关键选择与转折:
- 当章兑现:
- 身份暗线:
- 连续性人物:
- 结尾钩子:
- 任务描述:
```

Chapter-band requirements:

- Chapters 1–3: cold-open accident → discipline pursuit → public improvisation; complete the first small payoff.
- Chapters 4–6: turn Tang Li's lie into a real production obligation; Chen Mo wins through rules and cost-bearing, not family intervention.
- Chapters 7–10: first public performance changes how the school reads the pair; introduce the first administrative identity anomaly without explaining it.

- [ ] **Step 4: Write Chapters 11–25 in `outline.md`**

Chapter-band requirements:

- Chapters 11–16: introduce the second heroine through a family-arranged choice that collides with Tang Li's production, not through an unrelated side quest.
- Chapters 17–20: keep Tang Li causally active while the second heroine makes an irreversible choice.
- Chapters 21–25: introduce the real scholarship-dependent heroine; make Chen Mo's belief that they are socioeconomic equals emotionally useful and factually ironic.

- [ ] **Step 5: Write Chapters 26–40 in `outline.md`**

Chapter-band requirements:

- Chapters 26–32: student-government heroine enters because the existing production and scholarship conflict threatens academy reputation.
- Chapters 33–36: all four main heroines affect the same decision from incompatible positions.
- Chapters 37–40: first seeded heroine connects to Chen Mo's pre-accident past without identifying his family; the second seed arrives through inter-school competition.

- [ ] **Step 6: Write Chapters 41–50 in `outline.md`**

Chapter-band requirements:

- Chapters 41–47: school-festival climax; every main heroine has an independent objective and contributes a non-interchangeable choice.
- Chapters 48–49: comedic and relational accounting after the climax; no immediate confession or harem settlement.
- Chapter 50: Chen Mo retains one contradictory record and asks his father the first direct identity question; no answer is given.

- [ ] **Step 7: Verify the outline is structurally complete**

Run:

```powershell
$p = 'novels\告白事故与我无关\outline.md'
$text = Get-Content -LiteralPath $p -Raw -Encoding UTF8
$nums = [regex]::Matches($text, '(?m)^## 第(\d+)章') | ForEach-Object { [int]$_.Groups[1].Value }
if ($nums.Count -ne 50) { throw "Expected 50 chapters, got $($nums.Count)" }
if (($nums -join ',') -ne ((1..50) -join ',')) { throw 'Chapter numbers are not sequential 1..50' }
$required = @('定位','立即目标','阻力','关键选择与转折','当章兑现','身份暗线','连续性人物','结尾钩子','任务描述')
foreach ($field in $required) {
  $count = ([regex]::Matches($text, "(?m)^- $field:")).Count
  if ($count -ne 50) { throw "$field count=$count; expected 50" }
}
'OUTLINE_STRUCTURE_OK'
```

Expected: `OUTLINE_STRUCTURE_OK`.

- [ ] **Step 8: Commit the scaffold and outline only**

```powershell
git add -- 'novels/告白事故与我无关/project.json' 'novels/告白事故与我无关/world.md' 'novels/告白事故与我无关/outline.md'
git commit -m "feat: outline confession accident campus romcom"
```

Checkpoint: present the complete outline to the user before beginning detailed character design.

---

### Task 2: Audit and Repair the Outline Before Character Design

**Files:**
- Modify: `novels/告白事故与我无关/outline.md`
- Create: `novels/告白事故与我无关/outline_audit.md`
- Create: `novels/告白事故与我无关/relationship_calendar.md`

**Interfaces:**
- Consumes: all 50 chapter contracts from Task 1.
- Produces: an audited causal chain and an explicit continuity schedule that Task 3 uses to determine the final cast.

- [ ] **Step 1: Build the payoff and repetition audit**

Write `outline_audit.md` with seven fixed sections:

1. First-300-character opening contract.
2. Three-chapter payoff cadence for groups 1–3 through 49–50.
3. Eight-to-ten-chapter public set pieces.
4. Repeated-conflict scan: fake dating, discipline, rehearsal, family arrangement, scholarship, public rumor.
5. Identity-clue ladder and whether any clue solves the visible plot.
6. Four-main-heroine causal dependency map.
7. Repairs applied to exact chapter numbers.

Each identified problem must name the affected chapters and the replacement beat; do not write generic advice.

- [ ] **Step 2: Build the relationship continuity calendar**

Create `relationship_calendar.md` with one row per chapter and columns for Chen Mo, Tang Li, heroine slot 2, heroine slot 3, heroine slot 4, seed A, and seed B. Use `主场`, `推动`, `受影响`, or `未登场`; every non-empty heroine appearance must include a five-to-fifteen-character causal contribution.

- [ ] **Step 3: Repair the outline from the audit**

Use `apply_patch` to revise `outline.md`. Enforce:

- no introduced main heroine disappears for more than seven chapters without an explicit offscreen objective;
- no appearance exists solely to say hello, eat together, or watch another heroine's scene;
- no three consecutive chapters end on the same hook type;
- no identity clue grants Chen Mo money, authority, evidence, or an ally that closes the main conflict;
- Chapter 50 contains active suspicion, not passive confusion.

- [ ] **Step 4: Run text-level red-flag checks**

Run:

```powershell
$files = @(
  'novels\告白事故与我无关\outline.md',
  'novels\告白事故与我无关\outline_audit.md',
  'novels\告白事故与我无关\relationship_calendar.md'
)
$bad = Select-String -LiteralPath $files -Pattern 'TBD|TODO|待定|以后再说|继续准备|继续排练' -Encoding UTF8
if ($bad) { $bad | Format-Table; throw 'Outline contains placeholders or non-events' }
'OUTLINE_AUDIT_OK'
```

Expected: `OUTLINE_AUDIT_OK`.

- [ ] **Step 5: Commit audited outline artifacts**

```powershell
git add -- 'novels/告白事故与我无关/outline.md' 'novels/告白事故与我无关/outline_audit.md' 'novels/告白事故与我无关/relationship_calendar.md'
git commit -m "docs: audit confession accident outline"
```

---

### Task 3: Derive and Finalize Characters From the Audited Plot

**Files:**
- Modify: `novels/告白事故与我无关/project.json`
- Modify: `novels/告白事故与我无关/outline.md`
- Modify: `novels/告白事故与我无关/relationship_calendar.md`
- Create: `novels/告白事故与我无关/story_bible.md`
- Expand: `novels/告白事故与我无关/world.md`

**Interfaces:**
- Consumes: heroine function slots and exact causal needs established by Tasks 1–2.
- Produces: final names, character ids, voices, desires, failures, relationship contracts, supporting cast, and world canon required by the CLI seed.

- [ ] **Step 1: Design Chen Mo and Tang Li against their actual chapter decisions**

For each character, record in `story_bible.md`: public image, private desire, immediate first-arc goal, false belief, comic mechanism, speaking rhythm, action under pressure, non-negotiable boundary, unique attraction mechanism, and the chapter numbers that prove each trait.

Chen Mo must include: transmigration at twelve, no original memories, belief that his family is ordinary, frugality, adult common sense without omniscience, and inability to call family power.

Tang Li must include: stage-writer competence, improvisation failure, public bravado, the person who reused her confession script, and why her continued presence affects later heroines.

- [ ] **Step 2: Design the other three main heroines and two seeded heroines**

Derive each final character from the audited slot. Reject a design unless all four tests pass:

1. Removing her would break at least three named chapter beats.
2. Her failure is not interchangeable with Tang Li's rejection.
3. Her dialogue can be recognized without a speaker tag.
4. She wants something in the school plot that is not Chen Mo.

The seventh heroine remains outside the first-50-chapter cast and receives no character card.

- [ ] **Step 3: Design supporting characters and reasonable opposing interests**

Create only the supporting cast required by the outline: Tang Li's former target and his chosen girl, Chen Mo's parents, one homeroom teacher, one discipline administrator, club peers, and family/student-government counterparts already used by named chapters. No antagonist may exist solely to insult a heroine or expose Chen Mo's status.

- [ ] **Step 4: Populate `project.json`**

Replace `"characters": []` with complete character objects using stable ids. Every object includes `character_id`, `name`, `role`, `pov_eligible`, `first_appearance`, `personality`, `voice_style`, `core_motivation`, `weakness`, `current_state`, `arc_phase`, and `relationships`.

Add project hard limits, identity information policy, content cadence, volume objective, key results, and ending policy. Validate JSON:

```powershell
$p = 'novels\告白事故与我无关\project.json'
$json = Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json
if ($json.project.id -ne 'confession-accident') { throw 'Wrong project id' }
if ($json.characters.Count -lt 10) { throw 'Expected protagonists, heroines, and supporting cast' }
if (($json.characters.character_id | Sort-Object -Unique).Count -ne $json.characters.Count) { throw 'Duplicate character ids' }
'PROJECT_JSON_OK'
```

Expected: `PROJECT_JSON_OK`.

- [ ] **Step 5: Replace all functional heroine labels**

Use `apply_patch` to replace every `heroine slot`, `女主槽位`, `女主A`, `女主B`, `seed A`, and `seed B` reference in project files with final names or ids. Verify:

```powershell
$files = Get-ChildItem -LiteralPath 'novels\告白事故与我无关' -File
$left = Select-String -LiteralPath $files.FullName -Pattern 'heroine slot|女主槽位|女主A|女主B|seed A|seed B' -Encoding UTF8
if ($left) { $left | Format-Table; throw 'Functional labels remain after character finalization' }
'CHARACTER_LABELS_FINAL'
```

Expected: `CHARACTER_LABELS_FINAL`.

- [ ] **Step 6: Commit final story canon**

```powershell
git add -- 'novels/告白事故与我无关/project.json' 'novels/告白事故与我无关/story_bible.md' 'novels/告白事故与我无关/world.md' 'novels/告白事故与我无关/outline.md' 'novels/告白事故与我无关/relationship_calendar.md'
git commit -m "feat: derive confession accident cast from outline"
```

Checkpoint: present the character design and its chapter dependencies to the user before running the generation pipeline.

---

### Task 4: Add Project-Local Writing and Audit Contracts

**Files:**
- Create: `novels/告白事故与我无关/reference_benchmark.txt`
- Create: `novels/告白事故与我无关/audit_skill.md`
- Create: `novels/告白事故与我无关/guidance/WRITING_STANDARD.md`
- Create: `novels/告白事故与我无关/guidance/chapter_01.md`
- Create: `novels/告白事故与我无关/guidance/chapter_02.md`
- Create: `novels/告白事故与我无关/guidance/chapter_03.md`

**Interfaces:**
- Consumes: finalized chapters 1–3, character voices, and global prompt names.
- Produces: context-light Writer guidance and an audit workflow that cannot touch another project.

- [ ] **Step 1: Write the prose benchmark**

Limit `reference_benchmark.txt` to 1,500 Chinese characters. Define positive behavior rather than banned-word lists: conflict-bearing dialogue, mixed sentence lengths, physical action only when it changes leverage, no narrator explanation after readable behavior, and one main payoff per chapter. Do not paste passages from reference novels.

- [ ] **Step 2: Write the project audit workflow**

In `audit_skill.md`, require: read project canon; verify the first 300 characters; verify goal/obstacle/choice/payoff; check heroine voice; check identity clue separation; run full pipeline; repair only local prose defects. Explicitly limit destructive cleanup to `novels/告白事故与我无关/novel.db`, `.novel_cli.json`, and `output/` after absolute-path verification.

- [ ] **Step 3: Write compact chapter guidance**

Keep `WRITING_STANDARD.md` under 800 Chinese characters and each chapter guidance file under 300 Chinese characters. Each chapter file states: visible event, both sides' immediate goals, one dialogue reversal, chapter payoff, ending consequence, and at most three factual prohibitions.

- [ ] **Step 4: Verify guidance size and scope**

Run:

```powershell
$base = 'novels\告白事故与我无关'
$limit = @{
  "$base\reference_benchmark.txt" = 1500
  "$base\guidance\WRITING_STANDARD.md" = 800
  "$base\guidance\chapter_01.md" = 300
  "$base\guidance\chapter_02.md" = 300
  "$base\guidance\chapter_03.md" = 300
}
foreach ($entry in $limit.GetEnumerator()) {
  $len = (Get-Content -LiteralPath $entry.Key -Raw -Encoding UTF8).Length
  if ($len -gt $entry.Value) { throw "$($entry.Key) is $len chars; limit=$($entry.Value)" }
}
'GUIDANCE_SIZE_OK'
```

Expected: `GUIDANCE_SIZE_OK`.

- [ ] **Step 5: Commit local writing contracts**

```powershell
git add -- 'novels/告白事故与我无关/reference_benchmark.txt' 'novels/告白事故与我无关/audit_skill.md' 'novels/告白事故与我无关/guidance'
git commit -m "docs: add confession accident writing contracts"
```

---

### Task 5: Seed a Fresh Runtime and Validate Isolation

**Files:**
- Create: `novels/告白事故与我无关/novel.db`
- Create: `novels/告白事故与我无关/.novel_cli.json`

**Interfaces:**
- Consumes: finalized project files from Tasks 1–4.
- Produces: isolated database state for `confession-accident`.

- [ ] **Step 1: Verify no runtime state exists before first seed**

Run:

```powershell
$base = (Resolve-Path 'novels\告白事故与我无关').Path
foreach ($name in @('novel.db','.novel_cli.json')) {
  $p = Join-Path $base $name
  if (Test-Path -LiteralPath $p) { throw "Unexpected pre-existing runtime state: $p" }
}
'RUNTIME_CLEAN'
```

Expected: `RUNTIME_CLEAN`.

- [ ] **Step 2: Seed the new project**

Run:

```powershell
$env:PYTHONPATH = '.'
python -u scripts\novel_cli.py seed 'novels\告白事故与我无关'
```

Expected output includes `项目: 告白事故与我无关 (confession-accident)` and `数据已注入数据库`.

- [ ] **Step 3: Validate state paths and project id**

Run:

```powershell
$state = Get-Content -LiteralPath 'novels\告白事故与我无关\.novel_cli.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$expected = (Resolve-Path 'novels\告白事故与我无关').Path
if ($state.project_id -ne 'confession-accident') { throw 'State project id mismatch' }
if ((Split-Path -Parent $state.db_path) -ne $expected) { throw 'Database escaped the new project directory' }
if ($state.novel_dir -ne $expected) { throw 'Novel directory mismatch' }
'RUNTIME_ISOLATED'
```

Expected: `RUNTIME_ISOLATED`.

- [ ] **Step 4: Show pipeline status**

Run:

```powershell
$env:PYTHONPATH = '.'
python -u scripts\novel_cli.py status 'novels\告白事故与我无关'
```

Expected: project `confession-accident` exists with zero generated chapters.

---

### Task 6: Generate and Audit Chapters 1–3 Sequentially

**Files:**
- Create: `novels/告白事故与我无关/output/chapter_01.md`
- Create: `novels/告白事故与我无关/output/chapter_01.quality.json`
- Create: `novels/告白事故与我无关/output/chapter_02.md`
- Create: `novels/告白事故与我无关/output/chapter_02.quality.json`
- Create: `novels/告白事故与我无关/output/chapter_03.md`
- Create: `novels/告白事故与我无关/output/chapter_03.quality.json`
- Modify when required by audit: corresponding `outline.md` chapter block and `guidance/chapter_NN.md` only.

**Interfaces:**
- Consumes: isolated seeded database and finalized local guidance.
- Produces: three accepted test chapters and audit notes grounded in the actual output.

- [ ] **Step 1: Plan and write Chapter 1 through the full pipeline**

Run:

```powershell
$env:PYTHONPATH = '.'
python -u scripts\novel_cli.py plan 'novels\告白事故与我无关' 1
python -u scripts\novel_cli.py write 'novels\告白事故与我无关' 1 --stream
```

Expected: both commands exit 0 and `output/chapter_01.md` exists.

- [ ] **Step 2: Enforce the Chapter 1 cold-open contract**

Run:

```powershell
$text = Get-Content -LiteralPath 'novels\告白事故与我无关\output\chapter_01.md' -Raw -Encoding UTF8
$body = $text -replace '(?s)^#.*?\r?\n+', ''
$head = $body.Substring(0, [Math]::Min(300, $body.Length))
if ($head -notmatch '喜欢你十二年|字幕|舞台') { throw 'Chapter 1 misses the stage-conflict cold open' }
if ($head -match '东洲联邦|白桦学园是一所|陈默今年十七岁') { throw 'Chapter 1 opens with exposition' }
'CHAPTER_1_COLD_OPEN_OK'
```

Expected: `CHAPTER_1_COLD_OPEN_OK`.

- [ ] **Step 3: Audit Chapter 1 before generating Chapter 2**

Apply `audit_skill.md`. If the failure is prose-local, patch only the generated chapter. If the failure is causal or character-level, patch Chapter 1 in `outline.md` and `guidance/chapter_01.md`, then use the following bounded reset and rerun Tasks 5–6 from seed. Never carry a rejected Chapter 1 into Chapter 2.

```powershell
$expected = [IO.Path]::GetFullPath((Join-Path (Get-Location) 'novels\告白事故与我无关'))
$base = (Resolve-Path -LiteralPath 'novels\告白事故与我无关').Path
if ($base -ne $expected) { throw "Refusing reset outside expected project: $base" }
foreach ($name in @('novel.db','.novel_cli.json')) {
  $p = Join-Path $base $name
  if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
}
$output = Join-Path $base 'output'
if (Test-Path -LiteralPath $output) {
  Get-ChildItem -LiteralPath $output -File | Remove-Item -Force
}
'NEW_PROJECT_RUNTIME_RESET'
```

Expected: `NEW_PROJECT_RUNTIME_RESET`; `novels/校园小说` is never enumerated or modified.

- [ ] **Step 4: Plan, write, and audit Chapter 2**

Run:

```powershell
$env:PYTHONPATH = '.'
python -u scripts\novel_cli.py plan 'novels\告白事故与我无关' 2
python -u scripts\novel_cli.py write 'novels\告白事故与我无关' 2 --stream
```

Verify Chapter 2 contains an active pursuit by school authority, incompatible explanations from Chen Mo and Tang Li, and a consequence that makes the fake play real. Do not proceed if it is primarily paperwork or rehearsal procedure.

- [ ] **Step 5: Plan, write, and audit Chapter 3**

Run:

```powershell
$env:PYTHONPATH = '.'
python -u scripts\novel_cli.py plan 'novels\告白事故与我无关' 3
python -u scripts\novel_cli.py write 'novels\告白事故与我无关' 3 --stream
```

Verify Chapter 3 pays off the initial accident through a public choice, not merely by scheduling another rehearsal. Tang Li must say or do something she could not have done in Chapter 1; Chen Mo must lose or risk something because he actively chooses to stay.

- [ ] **Step 6: Run cross-chapter prose checks**

Run:

```powershell
$chapters = Get-ChildItem -LiteralPath 'novels\告白事故与我无关\output' -Filter 'chapter_0[1-3].md' | Sort-Object Name
if ($chapters.Count -ne 3) { throw 'Expected exactly three test chapters' }
foreach ($c in $chapters) {
  $text = Get-Content -LiteralPath $c.FullName -Raw -Encoding UTF8
  if ($text.Length -lt 2500) { throw "$($c.Name) is too short: $($text.Length) chars" }
  if ($text -match '总而言之|这一刻.{0,20}明白了|不是.{0,30}而是.{0,30}不是') { Write-Warning "$($c.Name) contains explanatory prose worth manual review" }
}
'THREE_CHAPTER_FILES_OK'
```

Expected: `THREE_CHAPTER_FILES_OK`; warnings require manual review rather than automatic rejection.

- [ ] **Step 7: Commit accepted generated chapters and their local fixes**

```powershell
git add -- 'novels/告白事故与我无关/outline.md' 'novels/告白事故与我无关/guidance' 'novels/告白事故与我无关/output'
git commit -m "feat: generate confession accident opening chapters"
```

Do not commit `novel.db` or `.novel_cli.json` unless this repository already tracks runtime databases for new novel projects and the user explicitly asks to preserve runtime state.

---

### Task 7: Final Verification and Handoff

**Files:**
- Verify: all files under `novels/告白事故与我无关`
- Verify: `docs/superpowers/specs/2026-07-13-hidden-heir-campus-romcom-design.md`

**Interfaces:**
- Consumes: accepted outline, cast, local contracts, runtime outputs.
- Produces: an evidence-backed handoff with no claim that unverified chapters are complete.

- [ ] **Step 1: Verify project isolation and tracked scope**

Run:

```powershell
git status --short
git diff --check
git log -6 --oneline -- 'novels/告白事故与我无关' 'docs/superpowers/specs/2026-07-13-hidden-heir-campus-romcom-design.md'
```

Confirm no implementation commit contains changes under `novels/校园小说`, `prompts/`, or unrelated source files.

- [ ] **Step 2: Re-run outline, JSON, guidance, and chapter-file checks**

Repeat the validation commands from Tasks 1–6. Expected terminal markers:

```text
OUTLINE_STRUCTURE_OK
OUTLINE_AUDIT_OK
PROJECT_JSON_OK
CHARACTER_LABELS_FINAL
GUIDANCE_SIZE_OK
RUNTIME_ISOLATED
CHAPTER_1_COLD_OPEN_OK
THREE_CHAPTER_FILES_OK
```

- [ ] **Step 3: Deliver the result**

Report: new project path, outline and character files, the four main/two seeded heroine policy, generated chapter paths, tests run, any manual prose repairs, and whether the first three chapters are ready for the user's reading decision. Do not claim market success or platform acceptance from structural checks alone.
