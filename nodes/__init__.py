"""ComfyUI nodes for RP Runtime V2 — P1 + P2 + C1."""

from .card_state_init_node import AWPV2CardStateInit
from .round_snapshot_node import AWPV2RoundSnapshot
from .quality_gate_node import AWPV2QualityGate
from .card_state_commit_node import AWPV2CardStateCommit
from .turn_record_commit_node import AWPV2TurnRecordCommit
from .retry_turn_node import AWPV2RetryTurn
from .continue_turn_node import AWPV2ContinueTurn
from .execution_trace_node import AWPV2ExecutionTrace

# P2 nodes
from .director_node import AWPV2Director
from .delegation_plan_node import AWPV2DelegationPlan
from .dynamic_subagent_pool_node import AWPV2DynamicSubAgentPool
from .suggestion_merge_node import AWPV2SuggestionMerge
from .writer_input_bundle_node import AWPV2WriterInputBundle
from .agent_trace_node import AWPV2AgentTrace

# M1 memory nodes
from .accepted_turn_window_node import AWPV2AcceptedTurnWindow
from .active_memory_recall_node import AWPV2ActiveMemoryRecall
from .rag_memory_recall_node import AWPV2RagMemoryRecall
from .memory_context_assembler_node import AWPV2MemoryContextAssembler
from .memory_commit_plan_node import AWPV2MemoryCommitPlan
from .active_memory_commit_node import AWPV2ActiveMemoryCommit
from .rag_memory_commit_node import AWPV2RagMemoryCommit
from .memory_diagnostics_node import AWPV2MemoryDiagnostics

# C1: Dual Main Agent + Tool Gateway nodes
from .director_plan_node import AWPV2DirectorPlan
from .tool_plan_node import AWPV2ToolPlan
from .tool_gateway_node import AWPV2ToolGateway
from .enrichment_merge_node import AWPV2EnrichmentMerge
from .final_turn_brief_node import AWPV2FinalTurnBrief
from .writer_output_node import AWPV2WriterOutput as AWPV2WriterV2
from .writer_input_bundle_v2_node import AWPV2WriterInputBundleV2
from .quality_pipeline_node import AWPV2QualityPipeline
from .reviser_node import AWPV2Reviser
from .writer_output_node import AWPV2WriterOutput
from .tool_trace_node import AWPV2ToolTrace

# D1: History/Recall nodes
from .history_recall_trigger_node import AWPV2HistoryRecallTrigger
from .history_recall_request_node import AWPV2HistoryRecallRequest
from .history_recall_agent_node import AWPV2HistoryRecallAgent
from .recall_evidence_ranker_node import AWPV2RecallEvidenceRanker
from .history_recall_result_node import AWPV2HistoryRecallResult
from .history_recall_diagnostics_node import AWPV2HistoryRecallDiagnostics

NODE_CLASS_MAPPINGS = {
    # P1
    "AWPV2CardStateInit": AWPV2CardStateInit,
    "AWPV2RoundSnapshot": AWPV2RoundSnapshot,
    "AWPV2QualityGate": AWPV2QualityGate,
    "AWPV2CardStateCommit": AWPV2CardStateCommit,
    "AWPV2TurnRecordCommit": AWPV2TurnRecordCommit,
    "AWPV2RetryTurn": AWPV2RetryTurn,
    "AWPV2ContinueTurn": AWPV2ContinueTurn,
    "AWPV2ExecutionTrace": AWPV2ExecutionTrace,
    # P2
    "AWPV2Director": AWPV2Director,
    "AWPV2DelegationPlan": AWPV2DelegationPlan,
    "AWPV2DynamicSubAgentPool": AWPV2DynamicSubAgentPool,
    "AWPV2SuggestionMerge": AWPV2SuggestionMerge,
    "AWPV2WriterInputBundle": AWPV2WriterInputBundle,
    "AWPV2AgentTrace": AWPV2AgentTrace,
    # M1
    "AWPV2AcceptedTurnWindow": AWPV2AcceptedTurnWindow,
    "AWPV2ActiveMemoryRecall": AWPV2ActiveMemoryRecall,
    "AWPV2RagMemoryRecall": AWPV2RagMemoryRecall,
    "AWPV2MemoryContextAssembler": AWPV2MemoryContextAssembler,
    "AWPV2MemoryCommitPlan": AWPV2MemoryCommitPlan,
    "AWPV2ActiveMemoryCommit": AWPV2ActiveMemoryCommit,
    "AWPV2RagMemoryCommit": AWPV2RagMemoryCommit,
    "AWPV2MemoryDiagnostics": AWPV2MemoryDiagnostics,
    # C1
    "AWPV2DirectorPlan": AWPV2DirectorPlan,
    "AWPV2ToolPlan": AWPV2ToolPlan,
    "AWPV2ToolGateway": AWPV2ToolGateway,
    "AWPV2EnrichmentMerge": AWPV2EnrichmentMerge,
    "AWPV2FinalTurnBrief": AWPV2FinalTurnBrief,
    "AWPV2WriterV2": AWPV2WriterV2,
    "AWPV2WriterInputBundleV2": AWPV2WriterInputBundleV2,
    "AWPV2QualityPipeline": AWPV2QualityPipeline,
    "AWPV2Reviser": AWPV2Reviser,
    "AWPV2WriterOutput": AWPV2WriterOutput,
    "AWPV2ToolTrace": AWPV2ToolTrace,
    # D1: History/Recall
    "AWPV2HistoryRecallTrigger": AWPV2HistoryRecallTrigger,
    "AWPV2HistoryRecallRequest": AWPV2HistoryRecallRequest,
    "AWPV2HistoryRecallAgent": AWPV2HistoryRecallAgent,
    "AWPV2RecallEvidenceRanker": AWPV2RecallEvidenceRanker,
    "AWPV2HistoryRecallResult": AWPV2HistoryRecallResult,
    "AWPV2HistoryRecallDiagnostics": AWPV2HistoryRecallDiagnostics,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    # P1
    "AWPV2CardStateInit": "AWP V2 卡片状态初始化",
    "AWPV2RoundSnapshot": "AWP V2 回合快照",
    "AWPV2QualityGate": "AWP V2 质量门",
    "AWPV2CardStateCommit": "AWP V2 状态提交",
    "AWPV2TurnRecordCommit": "AWP V2 回合记录提交",
    "AWPV2RetryTurn": "AWP V2 重试回合",
    "AWPV2ContinueTurn": "AWP V2 继续回合",
    "AWPV2ExecutionTrace": "AWP V2 执行追踪",
    # P2
    "AWPV2Director": "AWP V2 叙事总控",
    "AWPV2DelegationPlan": "AWP V2 委派计划",
    "AWPV2DynamicSubAgentPool": "AWP V2 动态子Agent池",
    "AWPV2SuggestionMerge": "AWP V2 建议合并",
    "AWPV2WriterInputBundle": "AWP V2 Writer输入包",
    "AWPV2AgentTrace": "AWP V2 Agent追踪",
    # M1
    "AWPV2AcceptedTurnWindow": "AWP V2 已接受回合窗口",
    "AWPV2ActiveMemoryRecall": "AWP V2 活跃记忆召回",
    "AWPV2RagMemoryRecall": "AWP V2 RAG记忆召回",
    "AWPV2MemoryContextAssembler": "AWP V2 记忆上下文组装",
    "AWPV2MemoryCommitPlan": "AWP V2 记忆提交计划",
    "AWPV2ActiveMemoryCommit": "AWP V2 活跃记忆提交",
    "AWPV2RagMemoryCommit": "AWP V2 RAG记忆提交",
    "AWPV2MemoryDiagnostics": "AWP V2 记忆诊断",
    # C1
    "AWPV2DirectorPlan": "AWP V2 Director规划",
    "AWPV2ToolPlan": "AWP V2 工具计划",
    "AWPV2ToolGateway": "AWP V2 工具网关",
    "AWPV2EnrichmentMerge": "AWP V2 丰富合并",
    "AWPV2FinalTurnBrief": "AWP V2 最终回合简报",
    "AWPV2WriterV2": "AWP V2 写作节点V2",
    "AWPV2WriterInputBundleV2": "AWP V2 Writer输入包V2",
    "AWPV2QualityPipeline": "AWP V2 质量检查流水线",
    "AWPV2Reviser": "AWP V2 修订器",
    "AWPV2WriterOutput": "AWP V2 Writer输出",
    "AWPV2ToolTrace": "AWP V2 工具追踪",
    # D1: History/Recall
    "AWPV2HistoryRecallTrigger": "AWP V2 历史回查触发",
    "AWPV2HistoryRecallRequest": "AWP V2 历史回查请求",
    "AWPV2HistoryRecallAgent": "AWP V2 历史回查Agent",
    "AWPV2RecallEvidenceRanker": "AWP V2 回查证据排序",
    "AWPV2HistoryRecallResult": "AWP V2 历史回查结果",
    "AWPV2HistoryRecallDiagnostics": "AWP V2 历史回查诊断",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
