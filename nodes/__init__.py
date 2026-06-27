"""ComfyUI nodes for RP Runtime V2 — P1 + P2."""

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

NODE_CLASS_MAPPINGS = {
    "AWPV2CardStateInit": AWPV2CardStateInit,
    "AWPV2RoundSnapshot": AWPV2RoundSnapshot,
    "AWPV2QualityGate": AWPV2QualityGate,
    "AWPV2CardStateCommit": AWPV2CardStateCommit,
    "AWPV2TurnRecordCommit": AWPV2TurnRecordCommit,
    "AWPV2RetryTurn": AWPV2RetryTurn,
    "AWPV2ContinueTurn": AWPV2ContinueTurn,
    "AWPV2ExecutionTrace": AWPV2ExecutionTrace,
    "AWPV2Director": AWPV2Director,
    "AWPV2DelegationPlan": AWPV2DelegationPlan,
    "AWPV2DynamicSubAgentPool": AWPV2DynamicSubAgentPool,
    "AWPV2SuggestionMerge": AWPV2SuggestionMerge,
    "AWPV2WriterInputBundle": AWPV2WriterInputBundle,
    "AWPV2AgentTrace": AWPV2AgentTrace,
    "AWPV2AcceptedTurnWindow": AWPV2AcceptedTurnWindow,
    "AWPV2ActiveMemoryRecall": AWPV2ActiveMemoryRecall,
    "AWPV2RagMemoryRecall": AWPV2RagMemoryRecall,
    "AWPV2MemoryContextAssembler": AWPV2MemoryContextAssembler,
    "AWPV2MemoryCommitPlan": AWPV2MemoryCommitPlan,
    "AWPV2ActiveMemoryCommit": AWPV2ActiveMemoryCommit,
    "AWPV2RagMemoryCommit": AWPV2RagMemoryCommit,
    "AWPV2MemoryDiagnostics": AWPV2MemoryDiagnostics,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2CardStateInit": "AWP V2 卡片状态初始化",
    "AWPV2RoundSnapshot": "AWP V2 回合快照",
    "AWPV2QualityGate": "AWP V2 质量门",
    "AWPV2CardStateCommit": "AWP V2 状态提交",
    "AWPV2TurnRecordCommit": "AWP V2 回合记录提交",
    "AWPV2RetryTurn": "AWP V2 重试回合",
    "AWPV2ContinueTurn": "AWP V2 继续回合",
    "AWPV2ExecutionTrace": "AWP V2 执行追踪",
    "AWPV2Director": "AWP V2 叙事总控",
    "AWPV2DelegationPlan": "AWP V2 委派计划",
    "AWPV2DynamicSubAgentPool": "AWP V2 动态子Agent池",
    "AWPV2SuggestionMerge": "AWP V2 建议合并",
    "AWPV2WriterInputBundle": "AWP V2 Writer输入包",
    "AWPV2AgentTrace": "AWP V2 Agent追踪",
    "AWPV2AcceptedTurnWindow": "AWP V2 已接受回合窗口",
    "AWPV2ActiveMemoryRecall": "AWP V2 活跃记忆召回",
    "AWPV2RagMemoryRecall": "AWP V2 RAG记忆召回",
    "AWPV2MemoryContextAssembler": "AWP V2 记忆上下文组装",
    "AWPV2MemoryCommitPlan": "AWP V2 记忆提交计划",
    "AWPV2ActiveMemoryCommit": "AWP V2 活跃记忆提交",
    "AWPV2RagMemoryCommit": "AWP V2 RAG记忆提交",
    "AWPV2MemoryDiagnostics": "AWP V2 记忆诊断",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
