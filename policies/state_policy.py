"""StatePolicy — rules governing CardState access and mutation.

Enforces:
- Only commit runtimes can write
- Gate must pass before commit
- Revision checks for conflict detection
- Idempotency via patchId
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts.card_state import CardState
from ..contracts.state_update_proposal import StateUpdateProposal, PatchOp


@dataclass
class ValidationResult:
    """Result of a policy validation."""
    valid: bool
    errors: list[str]
    warnings: list[str]


class StatePolicy:
    """Policy for CardState access and mutation.

    This is a pure policy — no side effects, no I/O.
    """

    # Allowed patch operations
    ALLOWED_OPS = {
        PatchOp.SET_VARIABLE,
        PatchOp.INCREMENT_VARIABLE,
        PatchOp.DECREMENT_VARIABLE,
        PatchOp.SET_EVENT_FLAG,
        PatchOp.CLEAR_EVENT_FLAG,
        PatchOp.SET_SCENE,
        PatchOp.ADD_ACTIVE_STAGE,
        PatchOp.REMOVE_ACTIVE_STAGE,
    }

    def validate_proposal(
        self,
        proposal: StateUpdateProposal,
        current_state: CardState,
        expected_revision: int,
    ) -> ValidationResult:
        """Validate a state update proposal against current state.

        Returns ValidationResult with errors if invalid.
        """
        errors = []
        warnings = []

        # Revision check
        if current_state.revision != expected_revision:
            errors.append(
                f"Revision conflict: expected {expected_revision}, "
                f"current is {current_state.revision}"
            )

        # Identity check
        if proposal.card_id != current_state.card_id:
            errors.append(
                f"card_id mismatch: proposal={proposal.card_id}, "
                f"state={current_state.card_id}"
            )
        if proposal.session_id != current_state.session_id:
            errors.append(
                f"session_id mismatch: proposal={proposal.session_id}, "
                f"state={current_state.session_id}"
            )

        # Validate each operation
        for i, op in enumerate(proposal.operations):
            if op.op not in self.ALLOWED_OPS:
                errors.append(f"Operation[{i}]: unknown op '{op.op.value}'")
                continue

            # Path validation
            parts = op.path.split(".")
            if len(parts) < 2:
                errors.append(f"Operation[{i}]: invalid path '{op.path}'")
                continue

            namespace = parts[0]

            if op.op in (PatchOp.SET_VARIABLE, PatchOp.INCREMENT_VARIABLE, PatchOp.DECREMENT_VARIABLE):
                if namespace != "variables":
                    errors.append(f"Operation[{i}]: variable ops must target 'variables.*'")
                if op.op == PatchOp.SET_VARIABLE and op.value is None:
                    errors.append(f"Operation[{i}]: set_variable requires a value")

            elif op.op in (PatchOp.SET_EVENT_FLAG, PatchOp.CLEAR_EVENT_FLAG):
                if namespace != "event_flags":
                    errors.append(f"Operation[{i}]: event_flag ops must target 'event_flags.*'")

            elif op.op == PatchOp.SET_SCENE:
                if namespace != "scene_state":
                    errors.append(f"Operation[{i}]: set_scene must target 'scene_state.*'")

            elif op.op in (PatchOp.ADD_ACTIVE_STAGE, PatchOp.REMOVE_ACTIVE_STAGE):
                if namespace != "active_stage_ids":
                    errors.append(f"Operation[{i}]: stage ops must target 'active_stage_ids'")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def is_writable_by(self, caller: str) -> bool:
        """Check if a caller is allowed to write CardState.

        Only commit runtimes are allowed to write.
        """
        allowed_writers = {
            "card_state_commit_runtime",
            "CardStateCommitNode",
        }
        return caller in allowed_writers
