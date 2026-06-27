# ADR-001: V2 Clean Room Architecture

## Status

Accepted

## Context

The V1 architecture accumulated complexity over time, with a monolithic MainAgent
that handled too many responsibilities. The V2 architecture aims to be clean,
modular, and formally structured.

## Decision

Build V2 from scratch with:

1. **Dual Master Agents** (Director + Writer) instead of one MainAgent
2. **Dynamic Sub-Agents** with strict envelopes instead of ad-hoc tool calls
3. **Deterministic CardState** as single source of truth
4. **Three-Layer Memory** (TurnRecords + ActiveMemory + RAG)
5. **Formal Turn Lifecycle** with explicit phases
6. **Gate-Protected Commits** with revision and idempotency

## Consequences

### Positive
- Clear separation of concerns
- Testable components
- Auditable state changes
- Predictable turn lifecycle

### Negative
- More components to maintain
- More complex initial setup
- Requires careful policy enforcement

## Alternatives Considered

1. **Refactor V1 incrementally**: Too much technical debt
2. **Single enhanced MainAgent**: Doesn't solve the core problem
3. **Full microservice architecture**: Overkill for ComfyUI nodes
