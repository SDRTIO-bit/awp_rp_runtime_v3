# AGENTS.md — Project Context for AI Agents

## Identity
**AWP RP Runtime V3** — Dual-mode runtime: interactive AI Role-Playing + automated Novel Writing. Built on ComfyUI workflow orchestration. Python 3.10+, React 18 frontend, SQLite storage.

## Two Modes

### RP Mode (mature)
- Interactive role-play with Director + Writer dual master agents + 6 dynamic sub-agents (D1-D6)
- SSE streaming via `_safe_on_step()` at 9 pipeline stages
- `PersistentTurnEngine` in `runtime/persistent_turn_engine.py` — main orchestrator
- 981 tests, 981 LOC in engine alone
- Frontend PipelineStreamDrawer renders real-time step progress

### Novel Mode (active development)
- Automated chapter generation: Architect → Director → Writer → Quality → Ledger
- `NovelEngine` in `runtime/novel_engine.py` — main orchestrator
- `NovelLLMFactory` in `runtime/novel_llm_factory.py` — role-based adapter factory

## Novel Mode Architecture (2026-07 latest)

### Streaming Pipeline (new)
| Layer | File | Purpose |
|-------|------|---------|
| Callbacks | `runtime/novel_trace.py` | `NovelStreamCallbacks` dataclass — on_phase, on_beat, on_chunk, on_error |
| Engine | `runtime/novel_engine.py` | `write_chapter_stream()` — fires phase callbacks at each stage |
| Writer | `runtime/novel_writer_adapter.py` | Builds a chapter-scoped Pi Writer task and preserves streaming callbacks |
| Role runtime | `runtime/novel_role_runtime.py` | Pi role sessions by default; explicit legacy compatibility boundary |
| Role bridge | `runtime/novel_pi_role_bridge.py` | Synchronous JSONL bridge to the isolated Pi Role Host |
| CLI | `scripts/novel_cli.py` | `--stream` flag for write/batch commands |

### NovelBrain (LLM Agent)
| File | Purpose |
|------|---------|
| `runtime/novel_brain.py` | ReAct agent with 5 tool functions, drives `NovelEngine` |
| `runtime/novel_agent_runtime.py` | Selects embedded Pi (`pi`, default) or explicit legacy NovelBrain runtime |
| `runtime/novel_pi_bridge.py` | Local JSON Lines bridge between Python and the Node Pi Host |
| `runtime/novel_pi_tool_service.py` | Project-bound allowlist that routes Pi calls through `NovelEngine` |
| `scripts/awp_tui.py` | Textual TUI — left/right split (pipeline + chat) |
| `tui.bat` | Windows launcher — `tui [project_name]` |

### Embedded Pi Novel Harness
- `agent_harness/` pins `@earendil-works/pi-coding-agent` at `0.80.6` and requires Node `>=22.19`.
- Pi is embedded through two isolated Node child processes, not an external Pi CLI: the interactive Host and the automated Role Host. Both use stdin/stdout JSON Lines and open no port.
- The interactive Host exposes five project tools. The Role Host runs separate Pi Agent Sessions for Architect, Director, Writer, Continuity, Style Cleaner, and Ledger Curator with role-specific read-only tools and skills.
- Writer keeps one Session for a chapter revision; other automated roles use task-scoped Sessions. Python remains the only state/file writer.
- Run `npm test` in `agent_harness/` for Node tests and `pytest tests/test_novel_pi_*.py -v` for Python bridge tests.
- `NOVEL_AGENT_RUNTIME=pi` is the default. `NOVEL_AGENT_RUNTIME=legacy` is the only manual fallback; Pi failures must not silently switch runtimes.

### LLM Role Config (`novel_llm_factory.py`)
| Role | Model | Max Tokens | Thinking |
|------|-------|------------|----------|
| director | deepseek-v4-pro | 8000 | high |
| architect | deepseek-v4-flash | 20000 | disabled |
| writer | deepseek-v4-pro | 4000 | medium |
| brain | deepseek-v4-pro | 2000 | low |
| continuity_checker | deepseek-v4-flash | 4000 | disabled |
| ledger_curator | deepseek-v4-flash | 4000 | disabled |

Provider switching via env var `NOVEL_LLM_PROVIDER`:
- `deepseek` (default) → `DeepSeekAdapter`
- `opencode` → `OpenAICompatibleAdapter` @ OpenCode Zen gateway (mimo-v2.5-pro for checker, qwen3.7-plus for others)
- `zengate` → same adapter class, different endpoint

## Key Architecture Rules

### Deterministic vs Agent Layer
- Only `CardStateCommitRuntime` writes state
- Only `ActiveMemoryCommitRuntime` / `RagMemoryCommitRuntime` write memory
- Quality Gate rejection = zero side effects
- All LLM calls are synchronous (blocking) — streaming via `stream=True` on SDK, not async

### Registry/Store Pattern
- `SessionRuntimeStoreRegistry` provides all 10 stores (card_state, turn_record, active_memory, rag_memory, trace, chapter_plan, draft, ledger, batch_progress, project_meta)
- All novel adapters accept `registry` as first constructor arg
- Used through `NovelEngine(self._registry)` or `NovelBrain(registry=...)`

### Data Flow: SSE Streaming (RP only, novel uses different pattern)
```
Player Input → management_api.py → ExecutionDispatcher → PersistentTurnEngine → SSE events → PipelineStreamDrawer
```

### Data Flow: Novel Streaming (new)
```
TUI/CLI → NovelEngine.write_chapter_stream() → NovelRoleRuntime → isolated Pi Role Host → Writer Pi Session → NovelStreamCallbacks → TUI/CLI
```

## Important Files

### Engines
- `runtime/persistent_turn_engine.py` (1791 lines) — RP main engine
- `runtime/novel_engine.py` (675→940+ lines) — Novel engine with streaming

### Adapters
- `adapters/llm/deepseek_adapter.py` — DeepSeek dual-endpoint (OpenAI + Anthropic)
- `adapters/llm/openai_compatible.py` — Generic OpenAI-compatible
- `adapters/llm/fake.py` — Testing fakes
- `runtime/novel_llm_factory.py` — Role-based adapter factory

### Contracts
- `contracts/` — 136 Pydantic models (novel_*, card_state, turn_record, execution_trace, etc.)

### Storage
- `storage/sqlite/database.py` — Schema initialization
- `storage/sqlite/novel_stores.py` — Novel project tables
- `storage/interfaces.py` — Abstract store interfaces

### Frontend
- `web/src/pages/Novels.tsx` — Novel project list
- `web/src/pages/NovelDetail.tsx` — Novel detail (chapters, ledger, export)
- `web/src/components/PipelineStreamDrawer.tsx` — RP pipeline observation

### CLI & Scripts
- `scripts/novel_cli.py` — Novel file-driven CLI (init, seed, plan, write, batch, export)
- `scripts/awp_tui.py` — Textual TUI for Brain interaction
- `scripts/awp_server.py` — Standalone HTTP server
- `tui.bat` — Windows TUI launcher

## Build & Test

```bash
# Only python 3.10+ supported (tested with 3.14)
pip install -e ".[dev]"

# Unit tests
pytest

# Lint (no strict setup, use manual checks)
python -c "import py_compile; py_compile.compile('path/to/file.py', doraise=True)"

# TUI
tui [project_name]   # from repo root
python -m awp_rp_runtime_v3.scripts.awp_tui [project_name]
```

## Recent Commits (novel pipeline)
- `b622038` — feat: 小说管线流式输出 + NovelBrain LLM 代理 + Textual TUI
- `b2a8078` — v3: 小说系统完整重构
- `1cb69fd` — fix: LedgerCurator format parser, quality_decision_id persistence
- `da979f9` — feat: prompt externalization + novel CLI

## Key Conventions
- No `async`/`await` in novel pipeline — all synchronous blocking calls
- No `logging` module — use structured patterns (ExecutionTrace, on_step callbacks)
- Pydantic v2 for all contracts
- Chinese comments and system prompts for novel agents
- Module-level path hack in `scripts/`: `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
