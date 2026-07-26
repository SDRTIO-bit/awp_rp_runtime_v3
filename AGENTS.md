# AGENTS.md — AWP Novel Runtime

## Identity

AWP Novel Runtime is a novel-only authoring system. Python 3.10+, React 18, SQLite, and an embedded Pi Coding Agent harness are used. RP Mode and ComfyUI integration are retired.

The Python import name remains `awp_rp_runtime_v3` for database/project and external-script compatibility; do not infer active RP features from that historical name.

## Default Product Flow

The TUI defaults to a dedicated Pi writing editor:

```text
author message
  → Python appends .awp/authoring/journal/*.jsonl
  → Pi editor captures, questions, challenges, and synthesizes
  → pending author plan
  → later author approval
  → still-later execution approval
  → deterministic AuthorPlanCompiler
  → Writer → Mechanical/Quality checks → Ledger
```

The editor is loyal to the work and target reader, not author approval. It must not flatter, directly write a full chapter, approve its own proposal, or call Architect between an approved author plan and Writer.

## Authoring Boundary

- `contracts/novel_authoring.py`: strict material, scene, plan, and approval contracts.
- `runtime/novel_authoring_service.py`: the only writer of local authoring journal/inbox/plan files.
- `runtime/novel_author_plan_compiler.py`: deterministic conversion to `ChapterPlan`; no LLM.
- `runtime/novel_pi_tool_service.py`: project-bound editor tool allowlist.
- `agent_harness/resources/system-prompt.md`: dedicated editor identity.
- `agent_harness/resources/skills/author-collaboration/SKILL.md`: automatically invoked editing loop.

All files are fixed beneath `<project>/.awp/authoring`. Unconfirmed material never enters canonical settings or Writer input. Proposal, approval, and execution must occur on different author turns.

## Pi Architecture

`agent_harness/` pins `@earendil-works/pi-coding-agent` at `0.80.6` and requires Node `>=22.19`.

- Interactive Host: persistent project editor Session, eight project-bound tools, no shell/network/arbitrary file tools.
- Role Host: isolated Architect, Director, Writer, Continuity, Style Cleaner, and Ledger Curator Sessions.
- Writer keeps one Session per chapter revision; other automated roles are task scoped.
- Python is the only state/file writer.
- `NOVEL_AGENT_RUNTIME=pi` is default. `legacy` is explicit only; failures never silently fall back.

The autonomous CLI retains explicit `plan`, `write`, and `batch` commands for compatibility. Those paths are not the default author-led TUI workflow.

## Storage

`SessionRuntimeStoreRegistry` contains only Novel stores plus Active/RAG memory stores. Historical `card_id`/`session_id` columns remain inside memory/database migrations for compatibility.

## Important Entry Points

- `runtime/novel_engine.py`
- `runtime/novel_agent_runtime.py`
- `scripts/awp_tui.py`
- `scripts/novel_cli.py`
- `scripts/awp_server.py`
- `web/src/pages/Novels.tsx`
- `web/src/pages/NovelDetail.tsx`

## Build and Test

```powershell
pip install -e ".[dev]"
python -m pytest tests/test_novel_author*.py -q
python -m pytest tests/test_novel_pi_*.py -q
cd agent_harness
npm ci
npm test
cd ..\web
npm ci
npm run build
```

Run long Python suites in bounded groups. Real-provider tests may be skipped unless their explicit environment gates are enabled.

## Conventions

- Novel pipeline LLM calls are synchronous; SDK token streaming is still synchronous.
- No silent runtime fallback.
- Pydantic v2 for new authoring/tool contracts.
- Chinese prompts and comments for writing roles.
- Only approved author plans may select plot in the default flow.
- Writer generic style defaults must remain subordinate to author-approved creative choices.
