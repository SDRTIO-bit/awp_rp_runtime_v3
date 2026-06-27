"""TraceArtifactRef — reference to a raw diagnostic artifact.

schemaId: awp.rp.trace-artifact-ref.v1

Artifacts are Level 3 (raw) data. By default, raw content is NOT included.
Only a reference (path + hash) is stored. Raw content must be explicitly
requested and is only available from the local test data directory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.trace-artifact-ref.v1"
SCHEMA_VERSION = 1


@dataclass
class TraceArtifactRef:
    """Reference to a raw diagnostic artifact."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    artifact_id: str = ""
    artifact_type: str = ""  # input_snapshot | output_snapshot | error_dump | state_diff | memory_diff
    node_id: str = ""
    workflow_run_id: str = ""

    # Storage reference (never exposes arbitrary file paths via API)
    relative_path: str = ""
    content_hash: str = ""
    content_size_bytes: int = 0

    # Retention
    created_at: str = ""
    ttl_seconds: int = 86400  # 24h default
    retention_policy: str = "test_run_only"

    # Access control
    access: str = "localhost_only"  # localhost_only | disabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "node_id": self.node_id,
            "workflow_run_id": self.workflow_run_id,
            "relative_path": self.relative_path,
            "content_hash": self.content_hash,
            "content_size_bytes": self.content_size_bytes,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
            "retention_policy": self.retention_policy,
            "access": self.access,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceArtifactRef:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            artifact_id=data.get("artifact_id", ""),
            artifact_type=data.get("artifact_type", ""),
            node_id=data.get("node_id", ""),
            workflow_run_id=data.get("workflow_run_id", ""),
            relative_path=data.get("relative_path", ""),
            content_hash=data.get("content_hash", ""),
            content_size_bytes=data.get("content_size_bytes", 0),
            created_at=data.get("created_at", ""),
            ttl_seconds=data.get("ttl_seconds", 86400),
            retention_policy=data.get("retention_policy", "test_run_only"),
            access=data.get("access", "localhost_only"),
        )
