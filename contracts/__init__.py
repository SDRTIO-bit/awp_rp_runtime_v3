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

# D-Integration: Conflict Governance contracts
from .suggestion_conflict import SuggestionConflict, ConflictKind, ConflictResolution
from .agent_execution_report import AgentExecutionReport, AgentExecutionOutcome
from .turn_agent_budget_report import TurnAgentBudgetReport
from .integrated_turn_trace import IntegratedTurnTrace

# D6: Memory Curator contracts
from .memory_curation_request import MemoryCurationRequest
from .memory_curation_candidate import MemoryCurationCandidate
from .memory_curation_evidence import MemoryCurationEvidence
from .memory_curation_result import MemoryCurationResult
from .memory_curation_trigger_diagnostics import MemoryCurationTriggerDiagnostics

# P-RealProvider: Provider boundary contracts
from .provider_request import (
    ProviderUsage, ProviderFailure, ProviderAttemptReceipt,
    ProviderResponse, ProviderRole, ProviderMode, FailureCode,
)
from .provider_guardrail_config import ProviderGuardrailConfig

# P-FirstTurn: First Turn Execution contracts
from .first_turn_request import FirstTurnRequest
from .first_turn_context import FirstTurnContext, OpeningContext, SessionBoundWorldbookRetrievalResult
from .first_turn_receipt import FirstTurnReceipt, FirstTurnFailure, FirstTurnFailureCode
from .first_turn_diagnostics import FirstTurnDiagnostics

# P-CardImport
from .card_source_snapshot import CardSourceSnapshot
from .card_import_request import CardImportRequest
from .card_import_report import CardImportReport
from .card_import_issue import CardImportIssue
from .card_definition import CardDefinition, CardDefinitionStatus
from .card_profile import CardProfile
from .card_greeting import CardGreeting
from .card_worldbook_entry import CardWorldbookEntry
from .card_worldbook_chunk import CardWorldbookChunk
from .card_structure_hints import CardStructureHints
from .card_quarantine_record import CardQuarantineRecord
from .card_import_approval import CardImportApproval
from .card_import_result import CardImportResult, ImportResultStatus

# P-Observability: Trace & Diagnostic contracts
from .workflow_run_record import WorkflowRunContext, WorkflowRunRecord
from .node_execution_record import (
    NodeExecutionRecord, ContractCheck,
    ExecutionStatus, BusinessDisposition, SemanticHealth,
)
from .node_contract_check import NodeContractCheck
from .node_diagnostic_spec import NodeDiagnosticSpec
from .trace_artifact_ref import TraceArtifactRef
from .workflow_test_result import WorkflowTestResult
from .workflow_test_failure import WorkflowTestFailure
from .workflow_test_scenario import (
    WorkflowTestScenario, NodeExpectation, SideEffectExpectation,
)

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
    # D6: Memory Curator
    "MemoryCurationRequest",
    "MemoryCurationCandidate",
    "MemoryCurationEvidence",
    "MemoryCurationResult",
    "MemoryCurationTriggerDiagnostics",
    # D-Integration
    "SuggestionConflict", "ConflictKind", "ConflictResolution",
    "AgentExecutionReport", "AgentExecutionOutcome",
    "TurnAgentBudgetReport",
    "IntegratedTurnTrace",
    # P-RealProvider
    "ProviderUsage", "ProviderFailure", "ProviderAttemptReceipt",
    "ProviderResponse", "ProviderRole", "ProviderMode", "FailureCode",
    "ProviderGuardrailConfig",
    # P-CardImport
    "CardSourceSnapshot", "CardImportRequest", "CardImportReport", "CardImportIssue",
    "CardDefinition", "CardDefinitionStatus", "CardProfile", "CardGreeting",
    "CardWorldbookEntry", "CardWorldbookChunk", "CardStructureHints",
    "CardQuarantineRecord", "CardImportApproval", "CardImportResult", "ImportResultStatus",
    # P-Observability
    "WorkflowRunContext", "WorkflowRunRecord",
    "NodeExecutionRecord", "ContractCheck",
    "ExecutionStatus", "BusinessDisposition", "SemanticHealth",
    "NodeContractCheck", "NodeDiagnosticSpec", "TraceArtifactRef",
    "WorkflowTestResult", "WorkflowTestFailure",
    "WorkflowTestScenario", "NodeExpectation", "SideEffectExpectation",
]
