"""NODE_DIAGNOSTIC_SPECS — registry of per-node diagnostic specifications.

Each critical AWP node declares:
  role:                    what this node does in the pipeline
  successInvariants:       conditions that must hold when the node succeeds
  normalNoopReasons:       valid reasons for producing no result
  mustExpose:              fields that must appear in output summary
  redactionRules:          what to redact from diagnostic output
  diagnosticVersion:       version of this spec

Enforced checks = existing business rules that already block execution/commit.
Observational checks = diagnostic rules that only mark warning/violation,
                       never change node business result.
"""

from __future__ import annotations

from ..contracts.node_diagnostic_spec import NodeDiagnosticSpec

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

NODE_DIAGNOSTIC_SPECS: dict[str, NodeDiagnosticSpec] = {}


def _register(spec: NodeDiagnosticSpec) -> None:
    NODE_DIAGNOSTIC_SPECS[spec.node_class] = spec


# ---------------------------------------------------------------------------
# P1 Core Nodes
# ---------------------------------------------------------------------------

_register(NodeDiagnosticSpec(
    node_class="AWPV2CardStateInit",
    role="Initialize CardState for a card/session pair",
    diagnostic_version="1",
    success_invariants=[
        "card_state is not None",
        "card_state.card_id matches input card_id",
        "card_state.session_id matches input session_id",
        "card_state.revision == 0",
    ],
    normal_noop_reasons=["CardState already initialized (idempotent)"],
    must_expose=["card_id", "session_id", "revision"],
    redaction_rules={"greeting": "hash_only"},
    observational_checks=[
        {"id": "init_revisions_zero", "name": "Initial revision is zero",
         "invariant": "output.revision == 0"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2RoundSnapshot",
    role="Build immutable snapshot of current round context",
    diagnostic_version="1",
    success_invariants=[
        "snapshot is not None",
        "snapshot.card_id matches input card_id",
        "snapshot.snapshot_id is non-empty",
    ],
    normal_noop_reasons=[],
    must_expose=["snapshot_id", "card_id", "turn_index"],
    redaction_rules={"player_input": "hash_only", "card_state": "summary_only"},
    observational_checks=[
        {"id": "snapshot_has_turn_index", "name": "Snapshot has valid turn_index",
         "invariant": "output.turn_index >= 0"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2QualityGate",
    role="Three-state quality gate: accept / revise / reject",
    diagnostic_version="1",
    success_invariants=[
        "verdict is one of: accept, revise, reject",
        "accept → blocking_reasons is empty",
        "reject → blocking_reasons is non-empty",
    ],
    normal_noop_reasons=[],
    must_expose=["verdict", "blocking_reasons", "overall_score"],
    redaction_rules={"candidate_text": "hash_only"},
    enforced_checks=[
        {"id": "verdict_valid", "name": "Verdict is valid enum",
         "invariant": "verdict in {accept, revise, reject}"},
    ],
    observational_checks=[
        {"id": "reject_has_reasons", "name": "Reject has blocking reasons",
         "invariant": "verdict != reject OR len(blocking_reasons) > 0"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2CardStateCommit",
    role="The ONLY node that writes CardState changes",
    diagnostic_version="1",
    success_invariants=[
        "quality_decision.allows_side_effects() == True",
        "commit_result.status in {accepted, duplicate_patch}",
        "patch_id is non-empty",
    ],
    normal_noop_reasons=["duplicate_patch (idempotent replay)"],
    must_expose=["status", "patch_id", "from_revision", "to_revision"],
    redaction_rules={"state_update_proposal": "summary_only"},
    enforced_checks=[
        {"id": "gate_approved", "name": "Quality gate approved",
         "invariant": "quality_decision.verdict == accept"},
        {"id": "revision_match", "name": "Expected revision matches",
         "invariant": "expected_revision == current_revision"},
    ],
    observational_checks=[
        {"id": "idempotent_replay", "name": "Duplicate patch detected",
         "invariant": "status == duplicate_patch implies no state change"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2TurnRecordCommit",
    role="The ONLY node that writes TurnRecord",
    diagnostic_version="1",
    success_invariants=[
        "quality_decision.allows_side_effects() == True",
        "turn_record is saved",
    ],
    normal_noop_reasons=["duplicate_turn_id (idempotent replay)"],
    must_expose=["turn_id", "status"],
    redaction_rules={},
    enforced_checks=[
        {"id": "gate_approved", "name": "Quality gate approved",
         "invariant": "quality_decision.verdict == accept"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2ExecutionTrace",
    role="Save execution trace for the turn",
    diagnostic_version="1",
    success_invariants=["trace is saved"],
    normal_noop_reasons=["trace save failed (non-fatal)"],
    must_expose=["trace_id"],
    redaction_rules={},
    observational_checks=[
        {"id": "trace_save_non_fatal", "name": "Trace save failure is non-fatal",
         "invariant": "trace_save_failure != node_failure"},
    ],
))

# ---------------------------------------------------------------------------
# P2 Nodes
# ---------------------------------------------------------------------------

_register(NodeDiagnosticSpec(
    node_class="AWPV2SuggestionMerge",
    role="Merge suggestions from multiple agents with conflict resolution",
    diagnostic_version="1",
    success_invariants=[
        "merge_result is not None",
        "conflicts are resolved",
    ],
    normal_noop_reasons=["no suggestions to merge"],
    must_expose=["total_suggestions", "accepted_count", "rejected_count"],
    redaction_rules={"suggestions": "summary_only"},
    observational_checks=[
        {"id": "priority_order", "name": "Higher priority wins conflicts",
         "invariant": "conflict_resolution respects priority"},
    ],
))

# ---------------------------------------------------------------------------
# C1 Nodes
# ---------------------------------------------------------------------------

_register(NodeDiagnosticSpec(
    node_class="AWPV2DirectorPlan",
    role="Director produces delegation plan for sub-agents",
    diagnostic_version="1",
    success_invariants=["plan is not None", "tasks are valid"],
    normal_noop_reasons=["low risk, no agents needed"],
    must_expose=["task_count", "agent_types"],
    redaction_rules={"plan": "summary_only"},
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2FinalTurnBrief",
    role="Assemble final brief for Writer from all agent results",
    diagnostic_version="1",
    success_invariants=["brief is not None"],
    normal_noop_reasons=[],
    must_expose=["brief_id"],
    redaction_rules={"brief_content": "hash_only"},
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2QualityPipeline",
    role="Quality check pipeline with three-state verdict",
    diagnostic_version="1",
    success_invariants=["verdict is valid"],
    normal_noop_reasons=[],
    must_expose=["verdict", "checks_passed", "checks_failed"],
    redaction_rules={"candidate_text": "hash_only"},
))

# ---------------------------------------------------------------------------
# D1-D6 Dynamic Agent Nodes
# ---------------------------------------------------------------------------

for agent_name, role_desc in [
    ("AWPV2HistoryRecallTrigger", "Determine if history recall agent should run"),
    ("AWPV2HistoryRecallAgent", "Recall relevant historical events"),
    ("AWPV2OpportunityTrigger", "Determine if opportunity agent should run"),
    ("AWPV2OpportunityAgent", "Find dramatic opportunity candidates"),
    ("AWPV2WorldLifeTrigger", "Determine if world-life agent should run"),
    ("AWPV2WorldLifeAgent", "Find world vitality candidates"),
    ("AWPV2EmotionRelationshipTrigger", "Determine if emotion/relationship agent should run"),
    ("AWPV2EmotionRelationshipAgent", "Find emotional/relationship candidates"),
    ("AWPV2ContinuityTrigger", "Determine if continuity agent should run"),
    ("AWPV2ContinuityAgent", "Detect continuity issues"),
]:
    _register(NodeDiagnosticSpec(
        node_class=agent_name,
        role=role_desc,
        diagnostic_version="1",
        success_invariants=["result is not None"],
        normal_noop_reasons=["not_required: trigger conditions not met"],
        must_expose=["triggered", "reason"],
        redaction_rules={"request": "summary_only", "result": "summary_only"},
    ))

# D6 Memory Curator
_register(NodeDiagnosticSpec(
    node_class="AWPV2MemoryCurator",
    role="Post-acceptance memory governance: decide what to remember",
    diagnostic_version="1",
    success_invariants=["curation_result is not None"],
    normal_noop_reasons=[
        "no long-term value detected",
        "all candidates below threshold",
    ],
    must_expose=["candidates_evaluated", "candidates_accepted"],
    redaction_rules={"curation_request": "summary_only"},
    observational_checks=[
        {"id": "no_forget_important", "name": "Important memories not evicted",
         "invariant": "importance >= 0.8 memories preserved"},
    ],
))

# Memory Commit
_register(NodeDiagnosticSpec(
    node_class="AWPV2ActiveMemoryCommit",
    role="Write accepted memories to ActiveMemory store",
    diagnostic_version="1",
    success_invariants=[
        "quality_decision.allows_side_effects() == True",
        "memory entries are saved",
    ],
    normal_noop_reasons=["no memories to commit"],
    must_expose=["entries_committed", "status"],
    redaction_rules={},
    enforced_checks=[
        {"id": "gate_approved", "name": "Quality gate approved",
         "invariant": "quality_decision.verdict == accept"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2RagMemoryCommit",
    role="Write accepted memories to RagMemory store",
    diagnostic_version="1",
    success_invariants=[
        "quality_decision.allows_side_effects() == True",
        "memory entries are saved",
    ],
    normal_noop_reasons=["no memories to commit"],
    must_expose=["entries_committed", "status"],
    redaction_rules={},
    enforced_checks=[
        {"id": "gate_approved", "name": "Quality gate approved",
         "invariant": "quality_decision.verdict == accept"},
    ],
))

# ---------------------------------------------------------------------------
# P-CardImport Nodes
# ---------------------------------------------------------------------------

_register(NodeDiagnosticSpec(
    node_class="AWPV2CardImportReview",
    role="Review parsed card for security and structure issues",
    diagnostic_version="1",
    success_invariants=["review report is not None"],
    normal_noop_reasons=["card is clean, no issues found"],
    must_expose=["issue_count", "severity_max"],
    redaction_rules={"card_payload": "hash_only"},
    observational_checks=[
        {"id": "quarantine_on_critical", "name": "Critical issues trigger quarantine",
         "invariant": "severity_max == critical implies quarantine"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2CardImportApproval",
    role="Approve or reject card import based on review",
    diagnostic_version="1",
    success_invariants=["approval_decision is not None"],
    normal_noop_reasons=[],
    must_expose=["approved", "reason"],
    redaction_rules={},
    enforced_checks=[
        {"id": "no_critical_issues", "name": "No critical issues for approval",
         "invariant": "approved implies severity_max < critical"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2CardDefinitionCommit",
    role="Commit approved card definition to store",
    diagnostic_version="1",
    success_invariants=[
        "approval is granted",
        "card_definition is saved",
    ],
    normal_noop_reasons=["card already exists (idempotent)"],
    must_expose=["card_id", "status"],
    redaction_rules={"card_definition": "summary_only"},
    enforced_checks=[
        {"id": "approved", "name": "Card is approved before commit",
         "invariant": "approval.approved == True"},
    ],
))

# ---------------------------------------------------------------------------
# P-CardSession Bootstrap Nodes
# ---------------------------------------------------------------------------

_register(NodeDiagnosticSpec(
    node_class="AWPV2CardDefinitionReadyValidator",
    role="Validate CardDefinition is ready for session bootstrap",
    diagnostic_version="1",
    success_invariants=[
        "card_definition.status == ready",
        "source_hash matches expected",
        "card_version matches requested",
    ],
    normal_noop_reasons=["card not found", "card not ready"],
    must_expose=["logical_card_id", "card_version", "source_hash", "status"],
    redaction_rules={},
    enforced_checks=[
        {"id": "card_ready", "name": "Card is ready",
         "invariant": "validation_result.valid == True"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2GreetingSelection",
    role="Select and validate greeting from CardDefinition",
    diagnostic_version="1",
    success_invariants=[
        "greeting_id belongs to the card version",
        "safe_display_content is not empty",
    ],
    normal_noop_reasons=["greeting not found"],
    must_expose=["greeting_id", "logical_card_id", "card_version", "is_default"],
    redaction_rules={"safe_display_content": "hash_only"},
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2CardStateInitializer",
    role="Initialize CardState from safe initialStateSeed only",
    diagnostic_version="1",
    success_invariants=[
        "card_state.revision == 1",
        "variables only from initialStateSeed",
        "no script execution",
    ],
    normal_noop_reasons=[],
    must_expose=["card_id", "session_id", "revision", "variable_count"],
    redaction_rules={"initial_state_seed": "summary_only"},
    observational_checks=[
        {"id": "revision_one", "name": "Initial revision is one",
         "invariant": "output.revision == 1"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2OpeningRecordCommit",
    role="Commit OpeningRecord for bootstrap greeting",
    diagnostic_version="1",
    success_invariants=[
        "opening_record_id is not empty",
        "greeting_id matches selection",
        "safe_display_content is preserved",
    ],
    normal_noop_reasons=[],
    must_expose=["opening_record_id", "session_id", "greeting_id", "logical_card_id"],
    redaction_rules={"safe_display_content": "hash_only"},
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2WorldbookBindingBuilder",
    role="Build WorldbookBinding from CardDefinition catalog",
    diagnostic_version="1",
    success_invariants=[
        "worldbook_binding_id is not empty",
        "bound entries are from card catalog",
        "disabled entries are tracked separately",
        "chunks preserve parentEntryId",
    ],
    normal_noop_reasons=["no worldbook entries in card"],
    must_expose=[
        "worldbook_binding_id", "session_id", "logical_card_id",
        "bound_entry_count", "disabled_entry_count", "deferred_entry_count",
    ],
    redaction_rules={},
    observational_checks=[
        {"id": "binding_not_activation", "name": "Binding is not activation",
         "invariant": "output.entries[].activation_status in [candidate, disabled, deferred, unsupported]"},
    ],
))

_register(NodeDiagnosticSpec(
    node_class="AWPV2CardSessionBindingCommit",
    role="Commit final CardSessionBinding and Bootstrap Receipt",
    diagnostic_version="1",
    success_invariants=[
        "session_id is bound",
        "logical_card_id and card_version are immutable",
        "source_hash is recorded",
        "all sub-records are linked",
    ],
    normal_noop_reasons=["idempotent retry returns existing receipt"],
    must_expose=[
        "session_id", "logical_card_id", "card_version", "source_hash",
        "greeting_id", "opening_record_id", "worldbook_binding_id",
        "commit_status", "idempotency_status",
    ],
    redaction_rules={},
    enforced_checks=[
        {"id": "binding_ready", "name": "Session binding is ready",
         "invariant": "session_binding.status == ready"},
    ],
))


def get_diagnostic_spec(node_class: str) -> NodeDiagnosticSpec | None:
    """Get the diagnostic spec for a node class, or None if not registered."""
    return NODE_DIAGNOSTIC_SPECS.get(node_class)


def get_all_specs() -> dict[str, NodeDiagnosticSpec]:
    """Get all registered diagnostic specs."""
    return dict(NODE_DIAGNOSTIC_SPECS)
