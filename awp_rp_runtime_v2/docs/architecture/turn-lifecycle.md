# Turn Lifecycle

## Complete Turn Sequence

### 1. Snapshot Phase
- Load or initialize CardState
- Load recent 5 TurnRecords
- Load active 15 memories
- Load RAG recall
- Load conditional worldbook entries
- Build frozen RoundSnapshot

### 2. Director Phase
- Read RoundSnapshot
- Understand player intent
- Generate TurnBrief (narrative intent, goals, constraints)
- Generate DelegationPlan (which sub-agents, if any)

### 3. Delegation Phase
- Validate DelegationPlan against policy
- Execute sub-agents with strict AgentTaskEnvelopes
- Collect AgentSuggestions

### 4. Merge Phase
- Merge suggestions by priority
- Detect conflicts
- Output SuggestionMergeResult (adopted/ignored/conflict)

### 5. Writer Phase
- Read RoundSnapshot + TurnBrief + adopted suggestions
- Generate candidate RP text
- Must NOT use tools, delegate, write state, or write memory

### 6. Quality Gate Phase
- Run deterministic checks (length, format, no JSON)
- Run LLM-based quality checks
- Accept or reject

### 7. Retry Phase (if rejected)
- Check retry count against limit
- Build retry context from rejection reasons
- Re-run Writer with feedback

### 8. State Proposal Phase
- Generate StateUpdateProposal from accepted text
- This is a CANDIDATE patch (not yet committed)

### 9. Commit Phase
- CardStateCommit: Apply state changes (revision check, idempotency)
- TurnRecordCommit: Save accepted turn record
- ActiveMemoryCommit: Update active memories
- RagMemoryCommit: Save RAG memories

### 10. Output Phase
- Return accepted text to player

## Invariants

1. Gate must pass before any writes
2. All writes require revision match
3. All writes use unique patchId for idempotency
4. Sub-agents cannot write state or memory
5. Writer cannot use tools or delegate
6. Director cannot produce player-visible text
