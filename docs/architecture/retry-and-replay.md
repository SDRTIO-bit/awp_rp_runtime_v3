# Retry and Replay

## Retry Policy

- Maximum 3 retries per turn
- Retry is triggered when QualityGate rejects
- Retry re-runs Writer with rejection feedback
- Retry does NOT duplicate state or memory writes
- Each retry increments retry_count

## Continue Policy

- Continue must be based on last accepted TurnRecord
- Cannot continue from a rejected or non-existent turn
- Continue does NOT create new state writes

## Replay

- TurnRecord contains all data needed for replay
- ExecutionTrace records every event for debugging
- Patch log in CardState store enables state replay

## Idempotency

- patchId is unique per state commit
- Duplicate patchId raises DuplicatePatchError
- Same patchId retry returns the same result
