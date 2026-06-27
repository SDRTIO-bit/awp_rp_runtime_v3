"""AgentSuggestion — structured output from a sub-agent.

schemaId: awp.rp.agent-suggestion.v1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.agent-suggestion.v1"
SCHEMA_VERSION = 1


class SuggestionKind(str, Enum):
    CONTINUITY_ISSUE = "continuity_issue"
    NARRATIVE_OPPORTUNITY = "narrative_opportunity"
    MEMORY_CANDIDATE = "memory_candidate"
    STATE_PATCH_PROPOSAL = "state_patch_proposal"
    TONE_ADJUSTMENT = "tone_adjustment"
    CHARACTER_CONSISTENCY = "character_consistency"
    WORLD_DETAIL = "world_detail"
    RELATIONSHIP_SHIFT = "relationship_shift"
    EMOTION_CUE = "emotion_cue"
    CRITIQUE = "critique"
    # D1: History/Recall kinds
    HISTORICAL_CONFLICT = "historical_conflict"
    IDENTITY_CLARIFICATION = "identity_clarification"
    TIMELINE_WARNING = "timeline_warning"
    WRITER_CONSTRAINT = "writer_constraint"
    DIRECTOR_FOLLOWUP = "director_followup"
    # D2: Opportunity kinds
    PROMISE_PRESSURE = "promise_pressure"
    RELATIONSHIP_TENSION = "relationship_tension"
    EMOTIONAL_SHIFT = "emotional_shift"
    SECRET_PRESSURE = "secret_pressure"
    MISUNDERSTANDING_PRESSURE = "misunderstanding_pressure"
    GOAL_REACTIVATION = "goal_reactivation"
    SCENE_PRESSURE = "scene_pressure"
    CHOICE_OPENING = "choice_opening"
    FORESHADOWING_ECHO = "foreshadowing_echo"
    PACE_VARIATION = "pace_variation"
    OPPORTUNITY_WARNING = "opportunity_warning"
    # D3: World-Life kinds
    ENVIRONMENTAL_PRESSURE = "environmental_pressure"
    WEATHER_OR_TIME_ATMOSPHERE = "weather_or_time_atmosphere"
    NPC_SIDE_TENSION = "npc_side_tension"
    EVENT_STAGE_ECHO = "event_stage_echo"
    LOCATION_LIFE_DETAIL = "location_life_detail"
    SOCIAL_BACKGROUND_SIGNAL = "social_background_signal"
    WORLDBOOK_RESONANCE = "worldbook_resonance"
    OFFSCREEN_CONSEQUENCE_HINT = "offscreen_consequence_hint"
    AMBIENT_RUMOR_SIGNAL = "ambient_rumor_signal"
    WORLD_LIFE_WARNING = "world_life_warning"
    # D4: Emotion/Relationship kinds
    ER_TRUST_TENSION = "er_trust_tension"
    ER_GUARDEDNESS = "er_guardedness"
    ER_EMOTIONAL_RESIDUE = "er_emotional_residue"
    ER_UNRESOLVED_HURT = "er_unresolved_hurt"
    ER_PROMISE_PRESSURE = "er_promise_pressure"
    ER_MISUNDERSTANDING_SIGNAL = "er_misunderstanding_signal"
    ER_JEALOUSY_RISK = "er_jealousy_risk"
    ER_AFFECTION_RESTRAINT = "er_affection_restraint"
    ER_CONFLICT_DEESCALATION = "er_conflict_deescalation"
    ER_RELATIONSHIP_BOUNDARY = "er_relationship_boundary"
    ER_SUBTEXT_OPPORTUNITY = "er_subtext_opportunity"
    ER_WARNING = "er_warning"

# Backward compat alias
SuggestionType = SuggestionKind


@dataclass
class AgentSuggestion:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    suggestion_id: str = ""
    trace_id: str = ""
    task_run_id: str = ""
    task_id: str = ""
    role: str = ""

    # Content
    kind: SuggestionKind = SuggestionKind.NARRATIVE_OPPORTUNITY
    priority: float = 0.5  # 0.0-1.0
    confidence: float = 0.5  # 0.0-1.0
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)

    # Evidence (required for high-risk)
    evidence: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)

    # Risk
    risk_flags: list[str] = field(default_factory=list)

    # Proposals (cannot be committed directly)
    proposed_state_changes: list[dict[str, Any]] = field(default_factory=list)
    proposed_memory_candidates: list[dict[str, Any]] = field(default_factory=list)

    # Timestamps
    created_at: str = ""

    # Backward compat aliases
    @property
    def suggestion_type(self) -> SuggestionKind:
        return self.kind

    @property
    def title(self) -> str:
        return self.summary

    @property
    def content(self) -> str:
        return "; ".join(self.recommendations) if self.recommendations else self.summary

    @property
    def importance(self) -> float:
        return self.priority

    @property
    def risk(self) -> float:
        return len(self.risk_flags) / 5.0  # rough mapping

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "suggestion_id": self.suggestion_id, "trace_id": self.trace_id,
            "task_run_id": self.task_run_id, "task_id": self.task_id,
            "role": self.role, "kind": self.kind.value,
            "priority": self.priority, "confidence": self.confidence,
            "summary": self.summary, "recommendations": self.recommendations,
            "evidence": self.evidence, "source_refs": self.source_refs,
            "risk_flags": self.risk_flags,
            "proposed_state_changes": self.proposed_state_changes,
            "proposed_memory_candidates": self.proposed_memory_candidates,
            "created_at": self.created_at,
            # backward compat
            "suggestion_type": self.kind.value,
            "title": self.summary,
            "content": self.content,
            "importance": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSuggestion:
        kind_raw = data.get("kind", data.get("suggestion_type", "narrative_opportunity"))
        try:
            kind = SuggestionKind(kind_raw)
        except ValueError:
            kind = SuggestionKind.NARRATIVE_OPPORTUNITY

        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            suggestion_id=data.get("suggestion_id", ""),
            trace_id=data.get("trace_id", ""),
            task_run_id=data.get("task_run_id", ""),
            task_id=data.get("task_id", ""),
            role=data.get("role", ""),
            kind=kind,
            priority=data.get("priority", data.get("importance", 0.5)),
            confidence=data.get("confidence", 0.5),
            summary=data.get("summary", data.get("title", "")),
            recommendations=data.get("recommendations", []),
            evidence=data.get("evidence", []),
            source_refs=data.get("source_refs", []),
            risk_flags=data.get("risk_flags", []),
            proposed_state_changes=data.get("proposed_state_changes", []),
            proposed_memory_candidates=data.get("proposed_memory_candidates", []),
            created_at=data.get("created_at", ""),
        )
