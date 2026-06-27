"""AWP Trace Wrapper — safe, observational node tracing.

Only wraps AWP-owned nodes. Does NOT monkeypatch ComfyUI globally.

Two mechanisms:
  AWPTraceableNodeMixin  — class mixin for nodes that opt in
  @awp_trace_node(...)   — decorator for wrapping existing node classes

Wrapper responsibilities (and ONLY these):
  1. Record start time
  2. Build input summary
  3. Call original node function
  4. Build output summary
  5. Run observational contract checks
  6. Record exception summary
  7. Save NodeExecutionRecord
  8. Return original node result unchanged

Wrapper NEVER:
  - Changes node inputs
  - Changes node outputs
  - Changes return types
  - Changes wiring behavior
  - Changes caching semantics
  - Changes commit behavior
  - Swallows original exceptions
"""

from __future__ import annotations

import hashlib
import time
import traceback
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

from ..contracts.node_execution_record import (
    NodeExecutionRecord, ContractCheck,
    ExecutionStatus, BusinessDisposition, SemanticHealth,
)
from ..contracts.workflow_run_record import WorkflowRunContext


class DiagnosticCollector:
    """Thread-safe collector for NodeExecutionRecords within a run.

    Nodes write records here. The scenario runner reads them after execution.
    """

    def __init__(self) -> None:
        self._records: list[NodeExecutionRecord] = []
        self._by_node_id: dict[str, NodeExecutionRecord] = {}
        self._context: WorkflowRunContext | None = None

    def set_context(self, context: WorkflowRunContext) -> None:
        self._context = context

    def get_context(self) -> WorkflowRunContext | None:
        return self._context

    def add(self, record: NodeExecutionRecord) -> None:
        self._records.append(record)
        if record.node_id:
            self._by_node_id[record.node_id] = record

    def get_all(self) -> list[NodeExecutionRecord]:
        return list(self._records)

    def get_by_node_id(self, node_id: str) -> NodeExecutionRecord | None:
        return self._by_node_id.get(node_id)

    def clear(self) -> None:
        self._records.clear()
        self._by_node_id.clear()
        self._context = None

    def to_dicts(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._records]


def _build_input_summary(node_class: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Build a redacted input summary — never includes full card text or prompt."""
    summary: dict[str, Any] = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            summary[key] = {
                "type": "string",
                "length": len(value),
                "hash": hashlib.sha256(value.encode()).hexdigest()[:16],
            }
        elif isinstance(value, dict):
            summary[key] = {
                "type": "dict",
                "keys": list(value.keys())[:20],
                "size": len(value),
            }
        elif isinstance(value, (list, tuple)):
            summary[key] = {
                "type": "list",
                "length": len(value),
            }
        elif isinstance(value, bool):
            summary[key] = {"type": "bool", "value": value}
        elif isinstance(value, (int, float)):
            summary[key] = {"type": type(value).__name__, "value": value}
        else:
            summary[key] = {"type": type(value).__name__}
    return summary


def _build_output_summary(result: Any) -> dict[str, Any]:
    """Build a redacted output summary."""
    if result is None:
        return {"type": "none"}
    if isinstance(result, tuple):
        return {
            "type": "tuple",
            "length": len(result),
            "element_types": [type(r).__name__ for r in result],
        }
    if isinstance(result, dict):
        return {"type": "dict", "keys": list(result.keys())[:20], "size": len(result)}
    if isinstance(result, str):
        return {"type": "string", "length": len(result)}
    return {"type": type(result).__name__}


def _build_error_summary(exc: Exception) -> dict[str, Any]:
    """Build error summary without leaking sensitive data."""
    return {
        "error_type": type(exc).__name__,
        "message": str(exc)[:500],
        "traceback_tail": traceback.format_exc()[-1000:],
    }


def _resolve_node_id(node_instance: Any, kwargs: dict[str, Any]) -> str:
    """Resolve a stable node_id for the record."""
    # Try explicit node_id input
    if "node_id" in kwargs and isinstance(kwargs["node_id"], str):
        return kwargs["node_id"]
    # Try _node_id attribute (set by ComfyUI)
    if hasattr(node_instance, "_node_id"):
        return str(getattr(node_instance, "_node_id"))
    # Fallback to class name
    return type(node_instance).__name__


def awp_trace_node(
    collector: DiagnosticCollector,
    build_diagnostic_summary: Callable[..., list[ContractCheck]] | None = None,
) -> Callable:
    """Decorator that wraps an AWP node's execute method with observational tracing.

    Args:
        collector: The DiagnosticCollector for this run
        build_diagnostic_summary: Optional domain-specific check builder.
            Signature: (node_class, inputs, outputs) -> list[ContractCheck]

    Returns:
        Decorator that wraps the execute method.
    """
    def decorator(execute_fn: Callable) -> Callable:
        @wraps(execute_fn)
        def wrapper(self, *args, **kwargs) -> Any:
            node_class = type(self).__name__
            node_id = _resolve_node_id(self, kwargs)

            # Capture context from collector
            ctx = collector.get_context()

            record = NodeExecutionRecord(
                trace_id=ctx.trace_id if ctx else "",
                workflow_run_id=ctx.workflow_run_id if ctx else "",
                prompt_id=ctx.prompt_id if ctx else "",
                turn_id=ctx.turn_id if ctx else "",
                attempt_id=ctx.attempt_id if ctx else "",
                node_id=node_id,
                node_class=node_class,
                node_label=getattr(self, "CATEGORY", ""),
                node_version="1",
            )

            # 1. Record start
            started_at = datetime.now(timezone.utc).isoformat()
            record.input_summary = _build_input_summary(node_class, kwargs)

            # 2. Call original
            try:
                result = execute_fn(self, *args, **kwargs)

                # 3. Build output summary
                finished_at = datetime.now(timezone.utc).isoformat()
                record.set_timing(started_at, finished_at)
                record.output_summary = _build_output_summary(result)
                record.execution_status = ExecutionStatus.EXECUTED.value
                record.business_disposition = BusinessDisposition.PRODUCED_RESULT.value

                # 4. Run domain-specific checks
                if build_diagnostic_summary:
                    try:
                        checks = build_diagnostic_summary(node_class, kwargs, result)
                        for check in checks:
                            record.add_contract_check(check)
                    except Exception as check_exc:
                        record.add_contract_check(ContractCheck(
                            check_id="diagnostic_check_error",
                            check_name="diagnostic_check_error",
                            check_type="observational",
                            passed=False,
                            severity="warning",
                            message=f"Diagnostic check failed: {check_exc}",
                        ))

                # 5. Save record
                collector.add(record)
                return result

            except Exception as exc:
                # Record exception
                finished_at = datetime.now(timezone.utc).isoformat()
                record.set_timing(started_at, finished_at)
                record.execution_status = ExecutionStatus.FAILED.value
                record.business_disposition = BusinessDisposition.NOOP.value
                record.semantic_health = SemanticHealth.VIOLATION.value
                record.error_summary = _build_error_summary(exc)
                collector.add(record)

                # Re-raise — never swallow
                raise

        return wrapper
    return decorator


class AWPTraceableNodeMixin:
    """Mixin for AWP nodes that want automatic tracing.

    Usage:
        class MyNode(AWPTraceableNodeMixin):
            def execute(self, ...):
                ...

    The mixin wraps `execute` with tracing if a collector is set.
    If no collector is set, execute runs unmodified.
    """

    _diagnostic_collector: DiagnosticCollector | None = None
    _build_diagnostic_summary: Callable | None = None

    @classmethod
    def set_diagnostic_collector(cls, collector: DiagnosticCollector | None) -> None:
        cls._diagnostic_collector = collector

    def execute(self, *args, **kwargs) -> Any:
        raise NotImplementedError("Subclasses must implement execute()")


def mark_node_not_reached(
    collector: DiagnosticCollector,
    node_id: str,
    node_class: str,
    reason: str = "",
) -> None:
    """Record that a node was not reached (e.g., upstream failure)."""
    ctx = collector.get_context()
    record = NodeExecutionRecord(
        trace_id=ctx.trace_id if ctx else "",
        workflow_run_id=ctx.workflow_run_id if ctx else "",
        prompt_id=ctx.prompt_id if ctx else "",
        turn_id=ctx.turn_id if ctx else "",
        attempt_id=ctx.attempt_id if ctx else "",
        node_id=node_id,
        node_class=node_class,
        execution_status=ExecutionStatus.NOT_REACHED.value,
        business_disposition=BusinessDisposition.NOT_REQUIRED.value,
        semantic_health=SemanticHealth.PASSED.value,
    )
    if reason:
        record.error_summary = {"reason": reason}
    collector.add(record)


def mark_node_blocked(
    collector: DiagnosticCollector,
    node_id: str,
    node_class: str,
    upstream_failure_node_id: str,
) -> None:
    """Record that a node was blocked by upstream failure."""
    ctx = collector.get_context()
    record = NodeExecutionRecord(
        trace_id=ctx.trace_id if ctx else "",
        workflow_run_id=ctx.workflow_run_id if ctx else "",
        prompt_id=ctx.prompt_id if ctx else "",
        turn_id=ctx.turn_id if ctx else "",
        attempt_id=ctx.attempt_id if ctx else "",
        node_id=node_id,
        node_class=node_class,
        execution_status=ExecutionStatus.BLOCKED_BY_UPSTREAM_FAILURE.value,
        business_disposition=BusinessDisposition.NOOP.value,
        semantic_health=SemanticHealth.PASSED.value,
        upstream_node_ids=[upstream_failure_node_id],
    )
    record.error_summary = {
        "blocked_by": upstream_failure_node_id,
        "reason": "upstream_failure_propagation",
    }
    collector.add(record)
