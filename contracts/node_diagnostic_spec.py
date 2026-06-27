"""NodeDiagnosticSpec — per-node-class diagnostic declaration.

schemaId: awp.rp.node-diagnostic-spec.v1

Every critical node declares:
  role: what this node does in the pipeline
  successInvariants: conditions that must hold when the node succeeds
  normalNoopReasons: valid reasons for the node to produce no result
  mustExpose: fields that must appear in output summary
  redactionRules: what to redact from diagnostic output
  diagnosticVersion: version of this spec
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.node-diagnostic-spec.v1"
SCHEMA_VERSION = 1


@dataclass
class NodeDiagnosticSpec:
    """Diagnostic specification for a single node class."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    node_class: str = ""
    role: str = ""
    diagnostic_version: str = "1"

    success_invariants: list[str] = field(default_factory=list)
    normal_noop_reasons: list[str] = field(default_factory=list)
    must_expose: list[str] = field(default_factory=list)
    redaction_rules: dict[str, str] = field(default_factory=dict)

    # Check definitions
    enforced_checks: list[dict[str, Any]] = field(default_factory=list)
    observational_checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "node_class": self.node_class,
            "role": self.role,
            "diagnostic_version": self.diagnostic_version,
            "success_invariants": self.success_invariants,
            "normal_noop_reasons": self.normal_noop_reasons,
            "must_expose": self.must_expose,
            "redaction_rules": self.redaction_rules,
            "enforced_checks": self.enforced_checks,
            "observational_checks": self.observational_checks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeDiagnosticSpec:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            node_class=data.get("node_class", ""),
            role=data.get("role", ""),
            diagnostic_version=data.get("diagnostic_version", "1"),
            success_invariants=data.get("success_invariants", []),
            normal_noop_reasons=data.get("normal_noop_reasons", []),
            must_expose=data.get("must_expose", []),
            redaction_rules=data.get("redaction_rules", {}),
            enforced_checks=data.get("enforced_checks", []),
            observational_checks=data.get("observational_checks", []),
        )
