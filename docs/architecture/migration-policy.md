# Migration Policy

## V1 to V2 Migration

V2 is a clean-room implementation. No V1 code is copied.

### What Stays in V1
- Old MainAgent implementation
- Old MVU patterns
- Old agent loop
- Old session flow

### What V2 Provides
- New contract-based architecture
- Dual master agents (Director + Writer)
- Dynamic sub-agents with strict envelopes
- Deterministic CardState with formal commits
- Three-layer memory system

### Adapter Interface
If V1 functionality needs to be accessed, it must go through adapter interfaces:
- `LLMProviderInterface` for LLM backends
- `ComfyUIAdapter` for ComfyUI integration
- `CharacterCardAdapter` for card loading
- `WorldbookAdapter` for worldbook loading
- `PresetAdapter` for preset loading

### No Backward Compatibility
V2 does not maintain backward compatibility with V1.
All V1 code must be migrated through adapters or rewritten.
