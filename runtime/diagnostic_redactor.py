"""DiagnosticRedactor — three-level data redaction for trace output.

Level 1 (Summary): Default. Only type, length, hash of values.
Level 2 (Redline): Key IDs, revision, patchId, entryId, status, count, reason codes.
Level 3 (Raw): Full artifacts. Default OFF. Only via explicit artifactRef read.

Never saves:
  - Full card text
  - Full worldbook text
  - Full player input
  - Full prompt
  - Full RAG text
  - System prompt
  - API keys / cookies / tokens
  - Raw model chain-of-thought
"""

from __future__ import annotations

import hashlib
from typing import Any


# Fields that must NEVER appear in diagnostic output at any level
NEVER_EXPOSE_FIELDS = frozenset({
    "api_key", "apikey", "api_secret", "secret", "token", "cookie",
    "password", "passwd", "auth", "authorization",
    "system_prompt", "system_message", "system_instruction",
    "chain_of_thought", "reasoning_trace", "raw_reasoning",
})

# Fields that are safe at Level 2 (redline)
REDLINE_SAFE_FIELDS = frozenset({
    "card_id", "session_id", "turn_id", "trace_id", "workflow_run_id",
    "prompt_id", "attempt_id", "node_id", "patch_id", "memory_id",
    "suggestion_id", "entry_id", "revision", "from_revision", "to_revision",
    "status", "verdict", "outcome", "reason", "error_type",
    "total_count", "accepted_count", "rejected_count", "issue_count",
    "importance", "confidence", "score",
})


class DiagnosticRedactor:
    """Redacts sensitive data from diagnostic output."""

    def __init__(self, level: int = 1) -> None:
        """Initialize with redaction level (1=summary, 2=redline, 3=raw)."""
        if level not in (1, 2, 3):
            raise ValueError(f"Invalid redaction level: {level}. Must be 1, 2, or 3.")
        self.level = level

    def redact_value(self, key: str, value: Any) -> Any:
        """Redact a single value based on key and current level."""
        # Never expose these fields at any level
        if key.lower() in NEVER_EXPOSE_FIELDS:
            return "<REDACTED>"

        if self.level == 1:
            return self._to_summary(key, value)
        elif self.level == 2:
            return self._to_redline(key, value)
        else:  # level 3
            return value

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Redact all values in a dictionary."""
        return {k: self.redact_value(k, v) for k, v in data.items()}

    def _to_summary(self, key: str, value: Any) -> Any:
        """Level 1: summary only."""
        if isinstance(value, str):
            return {
                "type": "string",
                "length": len(value),
                "hash": hashlib.sha256(value.encode()).hexdigest()[:16],
            }
        if isinstance(value, dict):
            return {
                "type": "dict",
                "keys": list(value.keys())[:20],
                "size": len(value),
            }
        if isinstance(value, (list, tuple)):
            return {"type": "list", "length": len(value)}
        if isinstance(value, bool):
            return value  # Booleans are safe
        if isinstance(value, (int, float)):
            return value  # Numbers are safe
        return {"type": type(value).__name__}

    def _to_redline(self, key: str, value: Any) -> Any:
        """Level 2: redline fields."""
        if key in REDLINE_SAFE_FIELDS:
            return value
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str) and len(value) < 200:
            return value  # Short strings are safe at redline
        return self._to_summary(key, value)


class DiagnosticSummaryBuilder:
    """Builds diagnostic summaries from node inputs/outputs."""

    def __init__(self, redactor: DiagnosticRedactor | None = None) -> None:
        self.redactor = redactor or DiagnosticRedactor(level=1)

    def build_input_summary(self, node_class: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Build a redacted input summary for a node."""
        return self.redactor.redact_dict(inputs)

    def build_output_summary(self, node_class: str, outputs: Any) -> dict[str, Any]:
        """Build a redacted output summary for a node."""
        if outputs is None:
            return {"type": "none"}
        if isinstance(outputs, tuple):
            return {
                "type": "tuple",
                "length": len(outputs),
                "element_summaries": [
                    self._summarize_single(o) for o in outputs
                ],
            }
        return self._summarize_single(outputs)

    def _summarize_single(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return self.redactor.redact_dict(value)
        if isinstance(value, str):
            return self.redactor.redact_value("_text", value)
        return {"type": type(value).__name__}


class ArtifactRetentionPolicy:
    """Controls retention and access to raw diagnostic artifacts."""

    def __init__(
        self,
        default_ttl_seconds: int = 86400,
        max_artifacts_per_run: int = 100,
        allowed_access: str = "localhost_only",
        storage_root: str = "",
    ) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self.max_artifacts_per_run = max_artifacts_per_run
        self.allowed_access = allowed_access
        self.storage_root = storage_root

    def is_artifact_allowed(self, artifact_type: str) -> bool:
        """Check if an artifact type is allowed to be stored."""
        # Raw artifacts are only allowed when explicitly enabled
        allowed_types = {
            "input_summary", "output_summary", "error_summary",
            "state_diff", "memory_diff", "contract_check_result",
        }
        return artifact_type in allowed_types

    def get_ttl(self, artifact_type: str) -> int:
        """Get TTL for an artifact type."""
        return self.default_ttl_seconds

    def is_accessible(self, request_host: str) -> bool:
        """Check if a request host can access artifacts."""
        if self.allowed_access == "localhost_only":
            return request_host in ("localhost", "127.0.0.1", "::1")
        return False
