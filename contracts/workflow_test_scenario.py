"""WorkflowTestScenario — declarative scenario definition.

schemaId: awp.rp.workflow-test-scenario.v1

Each scenario is a self-contained test case with:
  - Explicit input fixtures
  - Explicit workflow fixture
  - Expected node path and statuses
  - Expected contract checks
  - Expected side effects (or lack thereof)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.workflow-test-scenario.v1"
SCHEMA_VERSION = 1


@dataclass
class NodeExpectation:
    """Expected state of a single node after scenario execution."""
    node_id: str = ""
    node_class: str = ""

    expected_execution_status: str = ""  # executed | cached | not_reached | etc.
    expected_business_disposition: str = ""  # produced_result | noop | not_required | etc.
    expected_semantic_health: str = ""  # passed | warning | violation

    # If True, any execution_status is acceptable (used for non-deterministic nodes)
    allow_any_status: bool = False

    # If True, noop is explicitly allowed
    allow_noop: bool = False

    # If True, degraded is explicitly allowed
    allow_degraded: bool = False

    # Expected contract check outcomes
    expected_contract_checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_class": self.node_class,
            "expected_execution_status": self.expected_execution_status,
            "expected_business_disposition": self.expected_business_disposition,
            "expected_semantic_health": self.expected_semantic_health,
            "allow_any_status": self.allow_any_status,
            "allow_noop": self.allow_noop,
            "allow_degraded": self.allow_degraded,
            "expected_contract_checks": self.expected_contract_checks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeExpectation:
        return cls(
            node_id=data.get("node_id", ""),
            node_class=data.get("node_class", ""),
            expected_execution_status=data.get("expected_execution_status", ""),
            expected_business_disposition=data.get("expected_business_disposition", ""),
            expected_semantic_health=data.get("expected_semantic_health", ""),
            allow_any_status=data.get("allow_any_status", False),
            allow_noop=data.get("allow_noop", False),
            allow_degraded=data.get("allow_degraded", False),
            expected_contract_checks=data.get("expected_contract_checks", []),
        )


@dataclass
class SideEffectExpectation:
    """Expected side effects (or lack thereof) for a store."""
    store_name: str = ""  # card_state | turn_record | active_memory | rag_memory
    expected_writes: int = 0  # 0 = no writes expected
    must_be_idempotent: bool = False
    must_be_zero: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "store_name": self.store_name,
            "expected_writes": self.expected_writes,
            "must_be_idempotent": self.must_be_idempotent,
            "must_be_zero": self.must_be_zero,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SideEffectExpectation:
        return cls(
            store_name=data.get("store_name", ""),
            expected_writes=data.get("expected_writes", 0),
            must_be_idempotent=data.get("must_be_idempotent", False),
            must_be_zero=data.get("must_be_zero", False),
        )


@dataclass
class WorkflowTestScenario:
    """Declarative test scenario definition."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    scenario_id: str = ""
    scenario_name: str = ""
    description: str = ""
    suite: str = "smoke"  # smoke | integration | comfy-api-e2e

    # Input fixtures
    input_fixtures: dict[str, Any] = field(default_factory=dict)

    # Workflow fixture reference
    workflow_fixture: str = ""  # path to workflow JSON fixture

    # Expected node path
    node_expectations: list[NodeExpectation] = field(default_factory=list)

    # Expected side effects
    side_effect_expectations: list[SideEffectExpectation] = field(default_factory=list)

    # Expected overall outcome
    expected_outcome: str = "success"  # success | failure

    # Whether this scenario requires ComfyUI
    requires_comfyui: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "description": self.description,
            "suite": self.suite,
            "input_fixtures": self.input_fixtures,
            "workflow_fixture": self.workflow_fixture,
            "node_expectations": [n.to_dict() for n in self.node_expectations],
            "side_effect_expectations": [s.to_dict() for s in self.side_effect_expectations],
            "expected_outcome": self.expected_outcome,
            "requires_comfyui": self.requires_comfyui,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowTestScenario:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            scenario_id=data.get("scenario_id", ""),
            scenario_name=data.get("scenario_name", ""),
            description=data.get("description", ""),
            suite=data.get("suite", "smoke"),
            input_fixtures=data.get("input_fixtures", {}),
            workflow_fixture=data.get("workflow_fixture", ""),
            node_expectations=[
                NodeExpectation.from_dict(n) for n in data.get("node_expectations", [])
            ],
            side_effect_expectations=[
                SideEffectExpectation.from_dict(s)
                for s in data.get("side_effect_expectations", [])
            ],
            expected_outcome=data.get("expected_outcome", "success"),
            requires_comfyui=data.get("requires_comfyui", False),
        )
