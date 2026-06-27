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

# C1: New contracts
from .director_plan import DirectorPlan
from .tool_plan import ToolPlan, PlannedToolRequest
from .tool_request import ToolRequest
from .tool_result import ToolResult, ToolResultStatus
from .tool_result_bundle import ToolResultBundle
from .tool_permission import ToolPermission
from .tool_execution_receipt import ToolExecutionReceipt
from .enrichment_bundle import EnrichmentBundle, EnrichmentItem
from .final_turn_brief import FinalTurnBrief
from .writer_draft import WriterDraft
from .quality_issue import QualityIssue, IssueSeverity, IssueCategory
from .quality_gate_result import QualityGateResult
from .revision_request import RevisionRequest
from .revision_result import RevisionResult

# D1: History/Recall contracts
from .recall_focus import RecallFocus, RecallKind
from .recall_evidence import RecallEvidence, EvidenceSourceType
from .continuity_risk import ContinuityRisk, RiskLevel
from .history_recall_request import HistoryRecallRequest
from .history_recall_result import HistoryRecallResult, HistoryRecallStatus
from .history_recall_suggestion import HistoryRecallSuggestion, HistorySuggestionKind
from .history_recall_diagnostics import HistoryRecallDiagnostics

# D3: World-Life contracts
from .world_life_request import WorldLifeRequest
from .world_life_candidate import WorldLifeCandidate, WorldLifeKind, WorldLayer, VisibilityMode
from .world_life_evidence import WorldLifeEvidence
from .world_life_result import WorldLifeResult, WorldLifeStatus, RejectedWorldLifeCandidate
from .world_life_risk import WorldLifeRisk, WorldLifeRiskLevel
from .world_life_suggestion import WorldLifeSuggestion, WorldLifeSuggestionKind
from .world_life_trigger_diagnostics import WorldLifeTriggerDiagnostics

# D4: Emotion/Relationship contracts
from .emotion_relationship_request import EmotionRelationshipRequest
from .emotion_relationship_candidate import EmotionRelationshipCandidate, RelationshipKind
from .relationship_evidence import RelationshipEvidence
from .emotion_relationship_result import EmotionRelationshipResult, EmotionRelationshipStatus, RejectedEmotionCandidate
from .relationship_risk import RelationshipRisk, RelationshipRiskLevel
from .emotion_relationship_suggestion import EmotionRelationshipSuggestion, EmotionRelationshipSuggestionKind
from .emotion_relationship_trigger_diagnostics import EmotionRelationshipTriggerDiagnostics

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
    # C1
    "DirectorPlan",
    "ToolPlan", "PlannedToolRequest",
    "ToolRequest",
    "ToolResult", "ToolResultStatus",
    "ToolResultBundle",
    "ToolPermission",
    "ToolExecutionReceipt",
    "EnrichmentBundle", "EnrichmentItem",
    "FinalTurnBrief",
    "WriterDraft",
    "QualityIssue", "IssueSeverity", "IssueCategory",
    "QualityGateResult",
    "RevisionRequest", "RevisionResult",
    # D1: History/Recall
    "RecallFocus", "RecallKind",
    "RecallEvidence", "EvidenceSourceType",
    "ContinuityRisk", "RiskLevel",
    "HistoryRecallRequest",
    "HistoryRecallResult", "HistoryRecallStatus",
    "HistoryRecallSuggestion", "HistorySuggestionKind",
    "HistoryRecallDiagnostics",
]
