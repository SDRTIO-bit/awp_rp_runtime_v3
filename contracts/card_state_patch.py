"""CardStatePatch — formal patch operations for CardState.

schemaId: awp.rp.card-state-patch.v1

NOT a generic JSON Patch. Only whitelisted operations are allowed.
Each operation has explicit path rules, value types, and error codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.card-state-patch.v1"
SCHEMA_VERSION = 1


class PatchOpType(str, Enum):
    """Allowed patch operation types.

    Each op has:
    - allowed_path_prefix: which top-level key it may target
    - value_type: expected type of 'value'
    - may_create: whether it can create a new key
    - error_code: specific error code on failure
    """
    SET = "set"                      # variables.* — set a variable value
    REMOVE = "remove"                # variables.* | event_flags.* — remove a key
    INCREMENT = "increment"          # variables.* — numeric += value (default 1)
    APPEND_UNIQUE = "append_unique"  # active_stage_ids — add if not present
    SET_FLAG = "set_flag"            # event_flags.* — mark as fired
    ACTIVATE_STAGE = "activate_stage"    # active_stage_ids — add stage id
    DEACTIVATE_STAGE = "deactivate_stage"  # active_stage_ids — remove stage id
    SET_SCENE_FIELD = "set_scene_field"    # scene_state.* — set a scene field


# Operation specification: (allowed_prefix, value_type, may_create, error_code)
OP_SPECS: dict[PatchOpType, dict[str, Any]] = {
    PatchOpType.SET: {
        "allowed_prefixes": ["variables"],
        "value_type": None,  # any non-None
        "may_create": True,
        "error_code": "INVALID_SET",
    },
    PatchOpType.REMOVE: {
        "allowed_prefixes": ["variables", "event_flags"],
        "value_type": None,  # value ignored
        "may_create": False,
        "error_code": "INVALID_REMOVE",
    },
    PatchOpType.INCREMENT: {
        "allowed_prefixes": ["variables"],
        "value_type": (int, float),
        "may_create": False,  # variable must exist
        "error_code": "INVALID_INCREMENT",
    },
    PatchOpType.APPEND_UNIQUE: {
        "allowed_prefixes": ["active_stage_ids"],
        "value_type": str,
        "may_create": True,
        "error_code": "INVALID_APPEND_UNIQUE",
    },
    PatchOpType.SET_FLAG: {
        "allowed_prefixes": ["event_flags"],
        "value_type": None,  # value is optional metadata
        "may_create": True,
        "error_code": "INVALID_SET_FLAG",
    },
    PatchOpType.ACTIVATE_STAGE: {
        "allowed_prefixes": ["active_stage_ids"],
        "value_type": str,
        "may_create": True,
        "error_code": "INVALID_ACTIVATE_STAGE",
    },
    PatchOpType.DEACTIVATE_STAGE: {
        "allowed_prefixes": ["active_stage_ids"],
        "value_type": str,
        "may_create": False,
        "error_code": "INVALID_DEACTIVATE_STAGE",
    },
    PatchOpType.SET_SCENE_FIELD: {
        "allowed_prefixes": ["scene_state"],
        "value_type": None,  # depends on field
        "may_create": True,
        "error_code": "INVALID_SET_SCENE_FIELD",
    },
}

# Allowed scene_state fields and their types
SCENE_FIELD_TYPES: dict[str, type | tuple[type, ...]] = {
    "location": str,
    "time_of_day": str,
    "weather": str,
    "active_npcs": list,
    "description": str,
    "metadata": dict,
}


class PatchValidationError:
    """A single validation error on a patch operation."""
    def __init__(self, op_index: int, error_code: str, message: str):
        self.op_index = op_index
        self.error_code = error_code
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "op_index": self.op_index,
            "error_code": self.error_code,
            "message": self.message,
        }

    def __repr__(self) -> str:
        return f"PatchValidationError(op[{self.op_index}], {self.error_code}: {self.message})"


@dataclass(frozen=True)
class CardStatePatchOperation:
    """A single patch operation.

    NOT generic JSON Patch. Only whitelisted ops on allowed paths.
    """
    op: PatchOpType
    path: str  # e.g. "variables.favorability" or "scene_state.location"
    value: Any = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op.value,
            "path": self.path,
            "value": self.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardStatePatchOperation:
        return cls(
            op=PatchOpType(data["op"]),
            path=data["path"],
            value=data.get("value"),
            reason=data.get("reason", ""),
        )


@dataclass
class CardStatePatch:
    """A validated collection of patch operations.

    All operations are validated before any are applied.
    Any illegal operation causes the entire patch to be rejected.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    patch_id: str = ""
    card_id: str = ""
    session_id: str = ""
    operations: list[CardStatePatchOperation] = field(default_factory=list)
    source: str = ""  # Who created this patch
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "patch_id": self.patch_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "operations": [op.to_dict() for op in self.operations],
            "source": self.source,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardStatePatch:
        operations = [
            CardStatePatchOperation.from_dict(op) for op in data.get("operations", [])
        ]
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            patch_id=data.get("patch_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            operations=operations,
            source=data.get("source", ""),
            trace_id=data.get("trace_id", ""),
        )


def validate_patch_operations(
    operations: list[CardStatePatchOperation],
    current_variables: set[str],
    current_event_flags: set[str],
    current_stages: list[str],
) -> list[PatchValidationError]:
    """Validate all operations in a patch.

    Returns list of errors. Empty = all valid.
    Any error means the ENTIRE patch must be rejected (zero partial writes).
    """
    errors: list[PatchValidationError] = []

    for i, op in enumerate(operations):
        spec = OP_SPECS.get(op.op)
        if spec is None:
            errors.append(PatchValidationError(i, "UNKNOWN_OP", f"Unknown op: {op.op}"))
            continue

        # Parse path
        parts = op.path.split(".")
        if len(parts) < 2:
            errors.append(PatchValidationError(
                i, spec["error_code"],
                f"Path must have at least 2 segments: '{op.path}'"
            ))
            continue

        prefix = parts[0]
        key = parts[1]

        # Check prefix
        if prefix not in spec["allowed_prefixes"]:
            errors.append(PatchValidationError(
                i, spec["error_code"],
                f"Op '{op.op.value}' cannot target '{prefix}', "
                f"allowed: {spec['allowed_prefixes']}"
            ))
            continue

        # Op-specific validation
        if op.op == PatchOpType.SET:
            if op.value is None:
                errors.append(PatchValidationError(
                    i, "INVALID_SET", "set requires a non-None value"
                ))

        elif op.op == PatchOpType.REMOVE:
            if prefix == "variables" and key not in current_variables:
                if not spec["may_create"]:
                    errors.append(PatchValidationError(
                        i, "INVALID_REMOVE", f"Variable '{key}' does not exist"
                    ))
            elif prefix == "event_flags" and key not in current_event_flags:
                if not spec["may_create"]:
                    errors.append(PatchValidationError(
                        i, "INVALID_REMOVE", f"Event flag '{key}' does not exist"
                    ))

        elif op.op == PatchOpType.INCREMENT:
            if key not in current_variables:
                errors.append(PatchValidationError(
                    i, "INVALID_INCREMENT", f"Variable '{key}' does not exist"
                ))
            elif op.value is not None and not isinstance(op.value, (int, float)):
                errors.append(PatchValidationError(
                    i, "INVALID_INCREMENT", f"Increment value must be numeric, got {type(op.value).__name__}"
                ))

        elif op.op in (PatchOpType.APPEND_UNIQUE, PatchOpType.ACTIVATE_STAGE):
            if not isinstance(op.value, str) or not op.value:
                errors.append(PatchValidationError(
                    i, spec["error_code"], f"Value must be a non-empty string"
                ))

        elif op.op == PatchOpType.DEACTIVATE_STAGE:
            if not isinstance(op.value, str) or not op.value:
                errors.append(PatchValidationError(
                    i, "INVALID_DEACTIVATE_STAGE", "Value must be a non-empty string"
                ))
            elif op.value not in current_stages:
                errors.append(PatchValidationError(
                    i, "INVALID_DEACTIVATE_STAGE", f"Stage '{op.value}' is not active"
                ))

        elif op.op == PatchOpType.SET_FLAG:
            # May create new flags; value is optional metadata
            pass

        elif op.op == PatchOpType.SET_SCENE_FIELD:
            if key not in SCENE_FIELD_TYPES:
                errors.append(PatchValidationError(
                    i, "INVALID_SET_SCENE_FIELD",
                    f"Unknown scene field '{key}', allowed: {list(SCENE_FIELD_TYPES.keys())}"
                ))
            elif op.value is not None:
                expected = SCENE_FIELD_TYPES[key]
                if not isinstance(op.value, expected):
                    errors.append(PatchValidationError(
                        i, "INVALID_SET_SCENE_FIELD",
                        f"Scene field '{key}' expects {expected.__name__ if isinstance(expected, type) else expected}, "
                        f"got {type(op.value).__name__}"
                    ))

    return errors
