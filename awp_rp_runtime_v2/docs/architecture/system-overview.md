# System Overview

## Core Architecture

The RP Runtime V2 is a ComfyUI custom node plugin that implements a formal turn lifecycle for role-playing scenarios.

### Key Components

1. **Contract Layer**: Pure data structures (dataclasses) defining all data exchanged between components
2. **Policy Layer**: Pure business rules with no side effects
3. **Storage Layer**: Abstract interfaces + SQLite implementation
4. **Runtime Layer**: Orchestration logic for each step of the turn lifecycle
5. **Node Layer**: ComfyUI node implementations
6. **Adapter Layer**: Interfaces for external systems (LLM, character cards, worldbooks)
7. **Service Layer**: High-level coordination

### Data Flow

```
Player Input
    ↓
CardStateInit → CardState (load or initialize)
    ↓
RoundSnapshotBuilder → RoundSnapshot (frozen)
    ↓
DirectorRuntime → TurnBrief + DelegationPlan
    ↓
DynamicSubAgentPool → AgentSuggestion[]
    ↓
SuggestionMerger → SuggestionMergeResult
    ↓
WriterRuntime → candidate text
    ↓
CriticRuntime → QualityDecision
    ↓ (if accepted)
StateProposalRuntime → StateUpdateProposal
    ↓
CardStateCommitRuntime → committed CardState
    ↓
TurnRecordCommitRuntime → committed TurnRecord
    ↓
ActiveMemoryCommitRuntime → committed ActiveMemory
    ↓
RagMemoryCommitRuntime → committed RAG Memory
    ↓
Player Output
```

### Single Source of Truth

- **CardState**: World variables, event flags, scene state
- **TurnRecord**: Accepted turns only (never drafts or rejections)
- **ActiveMemory**: 15 plot attention cards
- **RAG Memory**: Long-term searchable memories
- **RoundSnapshot**: Frozen facts for the current round
