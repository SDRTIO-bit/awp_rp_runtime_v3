"""Test-only MemoryCurator fixture for controlled memory persistence verification.

ONLY enabled when AWP_RUNTIME_PROFILE=test.
Generates one deterministic, auditable MemoryCommitPlan per accepted turn.
Never used in real provider paths.
"""

from __future__ import annotations

from ...contracts.memory_commit_plan import MemoryCommitPlan
from ...contracts.memory_curation_candidate import (
    MemoryCurationCandidate, CurationTargetLayer, CurationOperation,
)
from ...contracts.memory_curation_result import MemoryCurationResult
from ...contracts.memory_curation_evidence import MemoryCurationEvidence
from ...contracts.quality_decision import QualityDecision
from ...contracts.turn_record import TurnRecord
from ...contracts.round_snapshot import RoundSnapshot
from ...contracts.active_memory import ActiveMemoryRecord, ActiveMemoryKind
from ...contracts.rag_memory import RagMemoryRecord
from ...runtime.memory_plan_compiler import MemoryPlanCompiler


class TestMemoryCuratorFixture:
    """Deterministic memory curator for test verification.

    Produces exactly one ActiveMemory candidate per accepted turn.
    The summary is deterministic: "test_memory:<turn_id>".
    This proves the full D6 → MemoryCommitPlan → SQLite → recall chain.
    """

    def curate(
        self,
        turn_record: TurnRecord,
        snapshot: RoundSnapshot,
        quality_decision: QualityDecision,
    ) -> MemoryCurationResult | None:
        """Produce a deterministic curation result for testing."""
        import os
        if os.environ.get("AWP_RUNTIME_PROFILE") != "test":
            return None

        candidate = MemoryCurationCandidate(
            candidate_id=f"test_cand_{turn_record.turn_id[:12]}",
            operation=CurationOperation.CREATE_ACTIVE,
            target_layer=CurationTargetLayer.ACTIVE_MEMORY,
            summary=f"test_memory:{turn_record.turn_id}:player_interaction_anchor",
            content=f"Test memory from turn {turn_record.turn_id}: "
                    f"player said '{turn_record.player_input[:50]}'",
            importance=0.6,
            confidence=0.95,
            entity_refs=["test_fixture"],
            tags=["test_anchor"],
            reason="test_fixture_deterministic_memory",
            evidence_refs=[
                MemoryCurationEvidence(
                    evidence_id=f"ev_{turn_record.turn_id[:12]}",
                    source_turn_id=turn_record.turn_id,
                    evidence_type="accepted_turn",
                    quote=turn_record.writer_output[:100] if turn_record.writer_output else "",
                    relevance=0.95,
                ),
            ],
        )

        return MemoryCurationResult(
            result_id=f"test_mcr_{turn_record.turn_id[:12]}",
            trace_id=snapshot.trace_id,
            turn_id=turn_record.turn_id,
            card_id=turn_record.card_id,
            session_id=turn_record.session_id,
            accepted_candidates=[candidate],
            rejected_candidates=[],
            total_candidates_generated=1,
            total_candidates_accepted=1,
            total_candidates_rejected=0,
            degraded=False,
        )


def compile_test_memory_plan(
    turn_record: TurnRecord,
    snapshot: RoundSnapshot,
    quality_decision: QualityDecision,
) -> MemoryCommitPlan | None:
    """Compile a test memory plan from the fixture.

    Returns None if not in test profile.
    Returns MemoryCommitPlan with one ActiveMemory entry if in test profile.
    """
    curator = TestMemoryCuratorFixture()
    result = curator.curate(turn_record, snapshot, quality_decision)
    if not result:
        return None

    compiler = MemoryPlanCompiler()
    plan = compiler.compile(
        curation_result=result,
        turn_id=turn_record.turn_id,
        card_id=turn_record.card_id,
        session_id=turn_record.session_id,
        trace_id=snapshot.trace_id,
        expected_card_state_revision=turn_record.result_card_state_revision,
        quality_decision_ref=turn_record.quality_decision_ref or turn_record.turn_id,
    )
    return plan
