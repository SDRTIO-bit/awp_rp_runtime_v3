"""AWPV2HistoryRecallRequest — ComfyUI node for building HistoryRecallRequest.

Builds the request contract for the History/Recall Agent.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.recall_focus import RecallKind
from ..contracts.history_recall_request import HistoryRecallRequest


class AWPV2HistoryRecallRequest:
    """Builds a HistoryRecallRequest from trigger result and snapshot."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "snapshot": ("ROUND_SNAPSHOT", {}),
                "trigger_result": ("TRIGGER_RESULT", {}),
                "task_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("HISTORY_RECALL_REQUEST",)
    RETURN_NAMES = ("request",)
    FUNCTION = "build"
    CATEGORY = "AWP V2/History Recall"

    def build(self, snapshot, trigger_result, task_id=""):
        now = datetime.now(timezone.utc).isoformat()
        recall_kinds = []
        for kind_str in trigger_result.suggested_recall_kinds:
            try:
                recall_kinds.append(RecallKind(kind_str))
            except ValueError:
                pass

        request = HistoryRecallRequest(
            request_id=f"hrr_{uuid.uuid4().hex[:8]}",
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            task_run_id=task_id or f"task_{uuid.uuid4().hex[:8]}",
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            focus_entities=trigger_result.suggested_focus_entities,
            recall_kinds=recall_kinds,
            created_at=now,
        )
        return (request,)
