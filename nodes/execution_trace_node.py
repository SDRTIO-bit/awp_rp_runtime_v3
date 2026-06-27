"""AWPV2ExecutionTrace — output execution trace for debugging/replay.

Input: any number of traceable artifacts
Output: execution_trace (JSON)
"""

from __future__ import annotations

from typing import Any


class AWPV2ExecutionTrace:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
            "optional": {
                "quality_decision": ("QUALITY_DECISION",),
                "commit_result": ("CARD_STATE_COMMIT_RESULT",),
                "turn_record": ("TURN_RECORD",),
            },
        }

    RETURN_TYPES = ("EXECUTION_TRACE",)
    RETURN_NAMES = ("execution_trace",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        round_snapshot: dict[str, Any],
        quality_decision: dict[str, Any] | None = None,
        commit_result: dict[str, Any] | None = None,
        turn_record: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any]]:
        from ..contracts.execution_trace import ExecutionTrace, TraceEvent
        from ..contracts.round_snapshot import RoundSnapshot

        snapshot = RoundSnapshot.from_dict(round_snapshot)

        events = [
            TraceEvent(
                event_id="evt_snapshot",
                event_type="snapshot_built",
                actor="AWPV2RoundSnapshot",
                details={"snapshot_id": snapshot.snapshot_id},
            ),
        ]

        if quality_decision:
            events.append(TraceEvent(
                event_id="evt_quality",
                event_type="quality_checked",
                actor="AWPV2QualityGate",
                details={"verdict": quality_decision.get("verdict", "unknown")},
            ))

        if commit_result:
            events.append(TraceEvent(
                event_id="evt_commit",
                event_type="state_committed",
                actor="AWPV2CardStateCommit",
                details={"status": commit_result.get("status", "unknown")},
            ))

        if turn_record:
            events.append(TraceEvent(
                event_id="evt_turn",
                event_type="turn_committed",
                actor="AWPV2TurnRecordCommit",
                details={"turn_id": turn_record.get("turn_id", "")},
            ))

        trace = ExecutionTrace(
            trace_id=snapshot.trace_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            events=events,
            success=True,
        )

        return (trace.to_dict(),)
