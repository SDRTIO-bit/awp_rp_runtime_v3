# Remove Recording-Device Lead Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the recorder-as-leverage premise so Chen Mo earns trust by discretion, then regenerate the first three chapters through the novel pipeline.

**Architecture:** The opening incident becomes an accidental witness event in the sports commentator booth. A teacher mistakes both students for a sports-promotion team and assigns a real deliverable; this replaces damaged equipment, recordings, backups, and deletion as the recurring contract.

**Tech Stack:** Markdown project canon, JSON project metadata, SQLite-backed Novel CLI pipeline.

## Global Constraints

- Chen Mo holds no recording, photo, file, backup, or other private evidence of Zhao Xiaomai's failure.
- Zhao Xiaomai remains active and dignified; Jiang Yue is candid, not a villain.
- Rewrite only the first arc and related global language; preserve the 50-chapter heroine order.
- Generate each replacement chapter with `seed → plan → write --stream`.

---

### Task 1: Replace the opening causal engine

**Files:**
- Modify: `novels/校园小说/story_bible.md`
- Modify: `novels/校园小说/world.md`
- Modify: `novels/校园小说/project.json`

- [ ] Remove all recorder, file backup, deletion, and hidden-partition mechanisms.
- [ ] Define the commentator-booth witness event and the teacher-assigned sports-promotion task.
- [ ] Verify `project.json` parses with `ConvertFrom-Json`.

### Task 2: Rebuild Zhao Xiaomai's first eight chapter briefs

**Files:**
- Modify: `novels/校园小说/outline.md`
- Modify: `novels/校园小说/guidance/chapter_01.md`
- Modify: `novels/校园小说/guidance/chapter_02.md`
- Modify: `novels/校园小说/guidance/chapter_03.md`

- [ ] Make chapter 1 establish witness plus compulsory work partnership.
- [ ] Make chapter 2 prove Chen Mo keeps silent while the task becomes public.
- [ ] Make chapter 3 form the stopwatch/start-sound pact without any secret file.
- [ ] Keep each Writer guidance below 250 characters.

### Task 3: Reset only the replacement runtime state

**Files:**
- Preserve: `novels/校园小说/archive/pre_reboot_20260713/`
- Preserve: `novels/校园小说/output_pre_reboot/`
- Replace: `novels/校园小说/novel.db`
- Replace: `novels/校园小说/output/chapter_01.md` through `chapter_03.md`

- [ ] Archive the current trial database and outputs under a timestamped replacement backup.
- [ ] Start a new novel database so outdated recorder ledger entries cannot reach the Writer.

### Task 4: Regenerate and inspect chapters 1–3

**Commands:**

```powershell
$env:PYTHONPATH = "."
python -u scripts/novel_cli.py seed "novels\校园小说"
python -u scripts/novel_cli.py plan "novels\校园小说" 1
python -u scripts/novel_cli.py write "novels\校园小说" 1 --stream
```

- [ ] Repeat the command sequence for chapters 2 and 3.
- [ ] Verify the output contains no recorder, recording, backup, file deletion, or hidden partition references.
- [ ] Verify chapter 3 ends with the stopwatch/start-sound agreement.
