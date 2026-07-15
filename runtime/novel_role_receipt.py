"""Secret-free provider receipts for Pi-backed novel role sessions."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from ..contracts.novel_pi_role_protocol import NovelPiRoleResult
from ..contracts.provider_request import (
    FailureCode,
    ProviderAttemptReceipt,
    ProviderFailure,
    ProviderUsage,
)


def _iso(value: datetime) -> str:
    return value.isoformat()


def build_pi_provider_receipt(
    result: NovelPiRoleResult,
    *,
    workflow_run_id: str = "",
    trace_id: str = "",
    turn_id: str = "",
    attempt_id: str = "",
) -> ProviderAttemptReceipt:
    """Map Pi terminal metadata to the existing provider receipt contract.

    Raw prompts, generated text, credentials, and connection URLs are deliberately
    absent. The receipt is safe to persist in traces.
    """

    finished = datetime.now(timezone.utc)
    started = finished - timedelta(milliseconds=result.latency_ms)
    usage = result.usage
    provider_usage = ProviderUsage(
        prompt_tokens=int(usage.get("input", 0)),
        completion_tokens=int(usage.get("output", 0)),
        total_tokens=int(usage.get("total", 0)),
        model=result.model,
        prompt_cache_hit_tokens=int(usage.get("cache_read", 0)),
        prompt_cache_miss_tokens=int(usage.get("cache_write", 0)),
        output_content_chars=len(result.text),
    )
    success = bool(result.text.strip())
    failure: dict[str, object] = {}
    if not success:
        failure = ProviderFailure(
            failure_code=FailureCode.EMPTY_RESPONSE,
            failure_message="Pi novel role returned empty text",
        ).to_dict()
    receipt_seed = f"{result.request_id}:{result.role}:{result.session_key}"
    receipt_id = "prrec_" + hashlib.sha256(receipt_seed.encode()).hexdigest()[:16]
    return ProviderAttemptReceipt(
        receipt_id=receipt_id,
        provider_role=result.role,
        provider_request_id=result.request_id,
        model=result.model,
        workflow_run_id=workflow_run_id,
        trace_id=trace_id,
        turn_id=turn_id,
        attempt_id=attempt_id,
        started_at=_iso(started),
        finished_at=_iso(finished),
        latency_ms=result.latency_ms,
        success=success,
        failure=failure,
        usage=provider_usage.to_dict(),
    )
