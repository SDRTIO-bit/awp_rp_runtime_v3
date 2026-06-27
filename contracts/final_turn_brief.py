"""FinalTurnBrief — Director's final brief after tool enrichment.

schemaId: awp.rp.final-turn-brief.v1

Produced by Director after ToolGateway results are validated.
This is the definitive input for Writer (via WriterInputBundle).
Director does NOT produce player-visible text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.final-turn-brief.v1"
SCHEMA_VERSION = 1


@dataclass
class FinalTurnBrief:
    """Director's final brief after tool enrichment.

    Director reads EnrichmentBundle and produces this.
    Writer reads this (via WriterInputBundle), NOT raw tool results.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    brief_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    director_plan_id: str = ""
    tool_result_bundle_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # Core narrative (from DirectorPlan, enriched)
    base_card_state_revision: int = 0
    turn_goal: str = ""
    scene_focus: str = ""

    # Characters
    active_character_refs: list[str] = field(default_factory=list)

    # Facts
    must_preserve_facts: list[str] = field(default_factory=list)
    must_not_do: list[str] = field(default_factory=list)

    # Tool findings (adopted/rejected with reasons)
    accepted_evidence: list[dict[str, Any]] = field(default_factory=list)
    accepted_tool_findings: list[str] = field(default_factory=list)
    rejected_tool_findings: list[dict[str, Any]] = field(default_factory=list)

    # Opportunities
    narrative_opportunities: list[str] = field(default_factory=list)

    # Writer constraints
    writer_constraints: list[str] = field(default_factory=list)

    # Sensitivity flags
    state_sensitivity_flags: list[str] = field(default_factory=list)
    memory_sensitivity_flags: list[str] = field(default_factory=list)

    # D1: History/Recall findings
    accepted_history_findings: list[str] = field(default_factory=list)
    rejected_history_findings: list[dict[str, Any]] = field(default_factory=list)
    history_continuity_warnings: list[str] = field(default_factory=list)
    history_evidence_refs: list[str] = field(default_factory=list)

    # D2: Opportunity findings
    accepted_opportunities: list[dict[str, Any]] = field(default_factory=list)
    rejected_opportunities: list[dict[str, Any]] = field(default_factory=list)
    opportunity_warnings: list[str] = field(default_factory=list)
    opportunity_evidence_refs: list[str] = field(default_factory=list)

    # D3: World-Life findings
    accepted_world_life_candidates: list[dict[str, Any]] = field(default_factory=list)
    rejected_world_life_candidates: list[dict[str, Any]] = field(default_factory=list)
    world_life_warnings: list[str] = field(default_factory=list)
    world_life_evidence_refs: list[str] = field(default_factory=list)

    # D4: Emotion/Relationship findings
    accepted_relationship_findings: list[str] = field(default_factory=list)
    rejected_relationship_findings: list[dict[str, Any]] = field(default_factory=list)
    relationship_warnings: list[str] = field(default_factory=list)
    relationship_evidence_refs: list[str] = field(default_factory=list)

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "brief_id": self.brief_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "director_plan_id": self.director_plan_id,
            "tool_result_bundle_id": self.tool_result_bundle_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "base_card_state_revision": self.base_card_state_revision,
            "turn_goal": self.turn_goal,
            "scene_focus": self.scene_focus,
            "active_character_refs": self.active_character_refs,
            "must_preserve_facts": self.must_preserve_facts,
            "must_not_do": self.must_not_do,
            "accepted_evidence": self.accepted_evidence,
            "accepted_tool_findings": self.accepted_tool_findings,
            "rejected_tool_findings": self.rejected_tool_findings,
            "narrative_opportunities": self.narrative_opportunities,
            "writer_constraints": self.writer_constraints,
            "state_sensitivity_flags": self.state_sensitivity_flags,
            "memory_sensitivity_flags": self.memory_sensitivity_flags,
            # D1
            "accepted_history_findings": self.accepted_history_findings,
            "rejected_history_findings": self.rejected_history_findings,
            "history_continuity_warnings": self.history_continuity_warnings,
            "history_evidence_refs": self.history_evidence_refs,
            # D2
            "accepted_opportunities": self.accepted_opportunities,
            "rejected_opportunities": self.rejected_opportunities,
            "opportunity_warnings": self.opportunity_warnings,
            "opportunity_evidence_refs": self.opportunity_evidence_refs,
            # D3
            "accepted_world_life_candidates": self.accepted_world_life_candidates,
            "rejected_world_life_candidates": self.rejected_world_life_candidates,
            "world_life_warnings": self.world_life_warnings,
            "world_life_evidence_refs": self.world_life_evidence_refs,
            # D4
            "accepted_relationship_findings": self.accepted_relationship_findings,
            "rejected_relationship_findings": self.rejected_relationship_findings,
            "relationship_warnings": self.relationship_warnings,
            "relationship_evidence_refs": self.relationship_evidence_refs,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FinalTurnBrief:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            brief_id=data.get("brief_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            director_plan_id=data.get("director_plan_id", ""),
            tool_result_bundle_id=data.get("tool_result_bundle_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            base_card_state_revision=data.get("base_card_state_revision", 0),
            turn_goal=data.get("turn_goal", ""),
            scene_focus=data.get("scene_focus", ""),
            active_character_refs=data.get("active_character_refs", []),
            must_preserve_facts=data.get("must_preserve_facts", []),
            must_not_do=data.get("must_not_do", []),
            accepted_evidence=data.get("accepted_evidence", []),
            accepted_tool_findings=data.get("accepted_tool_findings", []),
            rejected_tool_findings=data.get("rejected_tool_findings", []),
            narrative_opportunities=data.get("narrative_opportunities", []),
            writer_constraints=data.get("writer_constraints", []),
            state_sensitivity_flags=data.get("state_sensitivity_flags", []),
            memory_sensitivity_flags=data.get("memory_sensitivity_flags", []),
            # D1
            accepted_history_findings=data.get("accepted_history_findings", []),
            rejected_history_findings=data.get("rejected_history_findings", []),
            history_continuity_warnings=data.get("history_continuity_warnings", []),
            history_evidence_refs=data.get("history_evidence_refs", []),
            # D2
            accepted_opportunities=data.get("accepted_opportunities", []),
            rejected_opportunities=data.get("rejected_opportunities", []),
            opportunity_warnings=data.get("opportunity_warnings", []),
            opportunity_evidence_refs=data.get("opportunity_evidence_refs", []),
            # D3
            accepted_world_life_candidates=data.get("accepted_world_life_candidates", []),
            rejected_world_life_candidates=data.get("rejected_world_life_candidates", []),
            world_life_warnings=data.get("world_life_warnings", []),
            world_life_evidence_refs=data.get("world_life_evidence_refs", []),
            # D4
            accepted_relationship_findings=data.get("accepted_relationship_findings", []),
            rejected_relationship_findings=data.get("rejected_relationship_findings", []),
            relationship_warnings=data.get("relationship_warnings", []),
            relationship_evidence_refs=data.get("relationship_evidence_refs", []),
            created_at=data.get("created_at", ""),
        )
