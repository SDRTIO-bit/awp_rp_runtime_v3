"""Data contracts for RP Runtime V2."""

from .card_state import CardState, VariableEntry, EventFlag, SceneState
from .card_state_patch import (
    CardStatePatch, CardStatePatchOperation, PatchOpType,
    PatchValidationError, validate_patch_operations, OP_SPECS, SCENE_FIELD_TYPES,
)
from .card_state_commit import (
    CardStateCommitRequest, CardStateCommitResult, CardStateCommitStatus,
)
from .round_snapshot import RoundSnapshot
from .turn_record import TurnRecord, TurnMode
from .turn_brief import TurnBrief, NarrativeGoal
from .delegation_plan import DelegationPlan, DelegationTask
from .agent_task_envelope import AgentTaskEnvelope, TaskBudget
from .agent_suggestion import AgentSuggestion, SuggestionKind, SuggestionType
from .suggestion_merge_result import (
    SuggestionMergeResult, MergeItem, MergeDecision,
)
from .writer_contract import WriterContract
from .writer_input_bundle import WriterInputBundle
from .quality_decision import (
    QualityDecision, QualityVerdict,
    assert_side_effects_allowed, SideEffectBlockedError,
)
from .state_update_proposal import StateUpdateProposal, PatchOp, PatchOpEntry
from .memory_commit_plan import MemoryCommitPlan, ActiveMemoryEntry, RagMemoryEntry
from .execution_trace import ExecutionTrace, TraceEvent
from .agent_execution_result import AgentExecutionResult

__all__ = [
    "CardState", "VariableEntry", "EventFlag", "SceneState",
    "CardStatePatch", "CardStatePatchOperation", "PatchOpType",
    "PatchValidationError", "validate_patch_operations", "OP_SPECS", "SCENE_FIELD_TYPES",
    "CardStateCommitRequest", "CardStateCommitResult", "CardStateCommitStatus",
    "RoundSnapshot",
    "TurnRecord", "TurnMode",
    "TurnBrief", "NarrativeGoal",
    "DelegationPlan", "DelegationTask",
    "AgentTaskEnvelope", "TaskBudget",
    "AgentSuggestion", "SuggestionKind", "SuggestionType",
    "SuggestionMergeResult", "MergeItem", "MergeDecision",
    "WriterContract", "WriterInputBundle",
    "QualityDecision", "QualityVerdict",
    "assert_side_effects_allowed", "SideEffectBlockedError",
    "StateUpdateProposal", "PatchOp", "PatchOpEntry",
    "MemoryCommitPlan", "ActiveMemoryEntry", "RagMemoryEntry",
    "ExecutionTrace", "TraceEvent",
    "AgentExecutionResult",
]
