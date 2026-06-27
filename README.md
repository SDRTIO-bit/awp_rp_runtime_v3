# awp_rp_runtime_v2

ComfyUI RP Runtime V2: Dual-Master-Agent + Controlled Dynamic Sub-Agent + Deterministic CardState + Three-Layer Memory

## Architecture

### Dual Master Agents
- **Director**: Reads RoundSnapshot, produces TurnBrief + DelegationPlan. Does NOT produce player-visible text.
- **Writer**: Reads TurnBrief + adopted suggestions, produces player-visible RP text. Does NOT use tools, delegate, or write state.

### Dynamic Sub-Agents
Created from DelegationPlan. Each gets a strict AgentTaskEnvelope.
- rp-critic
- rp-memory-curator
- rp-state-updater
- worldbook-researcher
- continuity-checker

Sub-agents cannot write state, write memory, or delegate further.

### Deterministic CardState
The single source of truth for world variables, event flags, and scene state.
Only CardStateCommitRuntime can write. All writes require:
- Gate pass
- Revision match
- Unique patchId
- Transaction atomicity

### Three-Layer Memory
1. **Recent 5 TurnRecords**: Complete accepted turns (never truncated)
2. **Active 15 Memories**: Plot attention cards (30-80 chars each)
3. **RAG Memory**: Long-term searchable memories

### Turn Lifecycle
```
Player Input → CardStateInit → RoundSnapshot → Director → SubAgents
→ SuggestionMerge → Writer → QualityGate → StateProposal
→ CardStateCommit → TurnRecordCommit → MemoryCommit → Player Output
```

## Project Structure

```
awp_rp_runtime_v2/
├─ contracts/          # Data contracts (dataclasses)
├─ policies/           # Pure policy (no I/O)
├─ storage/            # Storage interfaces + SQLite
├─ runtime/            # Runtime orchestration
├─ nodes/              # ComfyUI nodes
├─ adapters/           # External system interfaces
├─ services/           # Service coordination
└─ testing/            # Fakes and fixtures
```

## Running Tests

```bash
cd awp_rp_runtime_v2
python -m pytest tests/ -v
```

## Key Constraints

1. No agent can write directly to storage
2. Only commit runtimes can write
3. Gate must pass before any writes
4. All writes support revision, patchId, idempotency
5. Sub-agents cannot delegate further
6. Writer cannot use tools
7. Director cannot produce player-visible text
