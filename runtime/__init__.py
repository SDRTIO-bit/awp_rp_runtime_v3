"""Runtime layer for RP Runtime V2."""

from .round_snapshot_builder import RoundSnapshotBuilder
from .director_runtime import DirectorRuntime
from .delegation_planner import DelegationPlanner
from .dynamic_subagent_pool import DynamicSubAgentPool
from .suggestion_merger import SuggestionMerger
from .writer_runtime import WriterRuntime
from .critic_runtime import CriticRuntime
from .state_proposal_runtime import StateProposalRuntime
from .card_state_commit_runtime import CardStateCommitRuntime
from .turn_record_commit_runtime import TurnRecordCommitRuntime
from .active_memory_commit_runtime import ActiveMemoryCommitRuntime
from .rag_memory_commit_runtime import RagMemoryCommitRuntime
from .continue_runtime import ContinueRuntime
from .retry_runtime import RetryRuntime
from .turn_orchestrator import TurnOrchestrator

# C1: New runtime modules
from .tool_registry import ToolRegistry, ToolRegistration, V1_ALLOWED_TOOLS
from .tool_permission_policy import ToolPermissionPolicy
from .tool_budget_runtime import ToolBudgetRuntime
from .tool_result_validator import ToolResultValidator
from .tool_gateway import ToolGateway, ToolRunner, FakeToolRunner
from .enrichment_merger import EnrichmentMerger
from .final_turn_brief_runtime import FinalTurnBriefRuntime
from .director_v2_runtime import DirectorV2Runtime, DirectorV2Adapter, FakeDirectorV2Adapter
from .writer_v2_runtime import WriterV2Runtime, WriterV2Adapter, FakeWriterV2Adapter
from .reviser_runtime import ReviserRuntime
from .quality_pipeline_runtime import (
    QualityPipelineRuntime, IdentityGate, SceneGate, LengthGate, FormatGate,
)
from .writer_input_bundle_v2_builder import WriterInputBundleV2Builder

# D1: History/Recall runtime
from .history_recall_trigger_policy import HistoryRecallTriggerPolicy
from .history_recall_runtime import HistoryRecallRuntime
from .history_recall_query_planner import HistoryRecallQueryPlanner
from .recall_evidence_ranker import RecallEvidenceRanker
from .history_recall_validator import HistoryRecallValidator
from .history_recall_adapter import HistoryRecallAdapter
from .history_recall_tool_profile import (
    HISTORY_RECALL_TOOLS, HISTORY_RECALL_ROLE_SPEC,
    create_history_recall_tool_registry,
)

__all__ = [
    "RoundSnapshotBuilder",
    "DirectorRuntime",
    "DelegationPlanner",
    "DynamicSubAgentPool",
    "SuggestionMerger",
    "WriterRuntime",
    "CriticRuntime",
    "StateProposalRuntime",
    "CardStateCommitRuntime",
    "TurnRecordCommitRuntime",
    "ActiveMemoryCommitRuntime",
    "RagMemoryCommitRuntime",
    "ContinueRuntime",
    "RetryRuntime",
    "TurnOrchestrator",
    # C1
    "ToolRegistry", "ToolRegistration", "V1_ALLOWED_TOOLS",
    "ToolPermissionPolicy",
    "ToolBudgetRuntime",
    "ToolResultValidator",
    "ToolGateway", "ToolRunner", "FakeToolRunner",
    "EnrichmentMerger",
    "FinalTurnBriefRuntime",
    "DirectorV2Runtime", "DirectorV2Adapter", "FakeDirectorV2Adapter",
    "WriterV2Runtime", "WriterV2Adapter", "FakeWriterV2Adapter",
    "ReviserRuntime",
    "QualityPipelineRuntime", "IdentityGate", "SceneGate", "LengthGate", "FormatGate",
    "WriterInputBundleV2Builder",
    # D1
    "HistoryRecallTriggerPolicy",
    "HistoryRecallRuntime",
    "HistoryRecallQueryPlanner",
    "RecallEvidenceRanker",
    "HistoryRecallValidator",
    "HistoryRecallAdapter",
    "HISTORY_RECALL_TOOLS", "HISTORY_RECALL_ROLE_SPEC",
    "create_history_recall_tool_registry",
]
