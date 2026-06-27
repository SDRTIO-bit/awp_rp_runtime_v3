"""AgentRuntimeRegistry — explicit role registration.

No dynamic import. No string-to-class auto-mapping.
Each role must be explicitly registered with its capabilities and constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..contracts.agent_task_envelope import AgentTaskEnvelope
from ..contracts.agent_suggestion import AgentSuggestion, SuggestionKind


class AgentRunner(Protocol):
    """Protocol for agent runners."""
    def run(self, envelope: AgentTaskEnvelope) -> list[AgentSuggestion]:
        ...


@dataclass(frozen=True)
class AgentRoleSpec:
    """Specification for a registered agent role."""
    role_id: str
    description: str = ""
    allowed_suggestion_kinds: list[SuggestionKind] = field(default_factory=list)
    default_budget_tokens: int = 700
    max_budget_tokens: int = 2000
    allowed_tools: list[str] = field(default_factory=list)
    can_delegate: bool = False
    can_write_state: bool = False
    can_write_memory: bool = False
    can_generate_final_text: bool = False


# Built-in role specs
BUILTIN_ROLES: dict[str, AgentRoleSpec] = {
    "continuity-checker": AgentRoleSpec(
        role_id="continuity-checker",
        description="Checks timeline, location, knowledge consistency",
        allowed_suggestion_kinds=[
            SuggestionKind.CONTINUITY_ISSUE,
            SuggestionKind.CHARACTER_CONSISTENCY,
        ],
    ),
    "worldbook-researcher": AgentRoleSpec(
        role_id="worldbook-researcher",
        description="Searches worldbook for relevant entries",
        allowed_suggestion_kinds=[
            SuggestionKind.WORLD_DETAIL,
            SuggestionKind.NARRATIVE_OPPORTUNITY,
        ],
    ),
    "emotion-relationship-analyst": AgentRoleSpec(
        role_id="emotion-relationship-analyst",
        description="Analyzes character emotions and relationship dynamics",
        allowed_suggestion_kinds=[
            SuggestionKind.EMOTION_CUE,
            SuggestionKind.RELATIONSHIP_SHIFT,
            SuggestionKind.NARRATIVE_OPPORTUNITY,
        ],
    ),
    "memory-curator": AgentRoleSpec(
        role_id="memory-curator",
        description="Identifies memory candidates from the current turn",
        allowed_suggestion_kinds=[
            SuggestionKind.MEMORY_CANDIDATE,
        ],
    ),
    "state-updater": AgentRoleSpec(
        role_id="state-updater",
        description="Proposes state changes (cannot commit)",
        allowed_suggestion_kinds=[
            SuggestionKind.STATE_PATCH_PROPOSAL,
        ],
    ),
    "rp-critic": AgentRoleSpec(
        role_id="rp-critic",
        description="Evaluates narrative quality and consistency",
        allowed_suggestion_kinds=[
            SuggestionKind.CRITIQUE,
            SuggestionKind.TONE_ADJUSTMENT,
        ],
    ),
    # D1: History/Recall Agent
    "history-recall": AgentRoleSpec(
        role_id="history-recall",
        description="History/Recall sub-agent for historical evidence and continuity",
        allowed_suggestion_kinds=[
            SuggestionKind.CONTINUITY_ISSUE,
            SuggestionKind.CHARACTER_CONSISTENCY,
            SuggestionKind.HISTORICAL_CONFLICT,
            SuggestionKind.IDENTITY_CLARIFICATION,
            SuggestionKind.TIMELINE_WARNING,
            SuggestionKind.WRITER_CONSTRAINT,
            SuggestionKind.DIRECTOR_FOLLOWUP,
        ],
        default_budget_tokens=1000,
        max_budget_tokens=2000,
        allowed_tools=[
            "rag_memory_lookup", "entity_alias_lookup", "timeline_lookup",
            "relationship_context_lookup", "worldbook_lookup",
            "accepted_turn_lookup", "active_memory_lookup",
        ],
        can_delegate=False,
        can_write_state=False,
        can_write_memory=False,
        can_generate_final_text=False,
    ),
    # D2: Opportunity Agent
    "opportunity": AgentRoleSpec(
        role_id="opportunity",
        description="Opportunity Agent — identifies narrative opportunities based on existing facts",
        allowed_suggestion_kinds=[
            SuggestionKind.PROMISE_PRESSURE,
            SuggestionKind.RELATIONSHIP_TENSION,
            SuggestionKind.EMOTIONAL_SHIFT,
            SuggestionKind.SECRET_PRESSURE,
            SuggestionKind.MISUNDERSTANDING_PRESSURE,
            SuggestionKind.GOAL_REACTIVATION,
            SuggestionKind.SCENE_PRESSURE,
            SuggestionKind.CHOICE_OPENING,
            SuggestionKind.FORESHADOWING_ECHO,
            SuggestionKind.PACE_VARIATION,
            SuggestionKind.OPPORTUNITY_WARNING,
        ],
        default_budget_tokens=1000,
        max_budget_tokens=2000,
        allowed_tools=[
            "accepted_turn_lookup", "active_memory_lookup",
            "rag_memory_lookup", "relationship_context_lookup",
            "timeline_lookup", "worldbook_lookup", "entity_alias_lookup",
        ],
        can_delegate=False,
        can_write_state=False,
        can_write_memory=False,
        can_generate_final_text=False,
    ),
    # D4: Emotion/Relationship Agent
    "emotion-relationship": AgentRoleSpec(
        role_id="emotion-relationship",
        description="Emotion/Relationship Agent — interprets character emotions and relationship dynamics from existing facts",
        allowed_suggestion_kinds=[
            SuggestionKind.ER_TRUST_TENSION,
            SuggestionKind.ER_GUARDEDNESS,
            SuggestionKind.ER_EMOTIONAL_RESIDUE,
            SuggestionKind.ER_UNRESOLVED_HURT,
            SuggestionKind.ER_PROMISE_PRESSURE,
            SuggestionKind.ER_MISUNDERSTANDING_SIGNAL,
            SuggestionKind.ER_JEALOUSY_RISK,
            SuggestionKind.ER_AFFECTION_RESTRAINT,
            SuggestionKind.ER_CONFLICT_DEESCALATION,
            SuggestionKind.ER_RELATIONSHIP_BOUNDARY,
            SuggestionKind.ER_SUBTEXT_OPPORTUNITY,
            SuggestionKind.ER_WARNING,
        ],
        default_budget_tokens=1000,
        max_budget_tokens=2000,
        allowed_tools=[
            "accepted_turn_lookup", "active_memory_lookup",
            "rag_memory_lookup", "relationship_context_lookup",
            "timeline_lookup", "worldbook_lookup", "entity_alias_lookup",
        ],
        can_delegate=False,
        can_write_state=False,
        can_write_memory=False,
        can_generate_final_text=False,
    ),
}


class AgentRuntimeRegistry:
    """Explicit role registry. No dynamic import."""

    def __init__(self):
        self._specs: dict[str, AgentRoleSpec] = dict(BUILTIN_ROLES)
        self._runners: dict[str, AgentRunner] = {}

    def register_spec(self, spec: AgentRoleSpec) -> None:
        self._specs[spec.role_id] = spec

    def register_runner(self, role_id: str, runner: AgentRunner) -> None:
        if role_id not in self._specs:
            raise ValueError(f"Cannot register runner for unknown role: {role_id}")
        self._runners[role_id] = runner

    def get_spec(self, role_id: str) -> AgentRoleSpec | None:
        return self._specs.get(role_id)

    def is_registered(self, role_id: str) -> bool:
        return role_id in self._specs

    def get_runner(self, role_id: str) -> AgentRunner | None:
        return self._runners.get(role_id)

    def get_all_roles(self) -> list[str]:
        return list(self._specs.keys())

    def validate_suggestion_kinds(
        self, role_id: str, kinds: list[SuggestionKind]
    ) -> list[str]:
        """Validate that suggestion kinds are allowed for this role."""
        spec = self._specs.get(role_id)
        if not spec:
            return [f"Unknown role: {role_id}"]
        errors = []
        for k in kinds:
            if k not in spec.allowed_suggestion_kinds:
                errors.append(
                    f"Role '{role_id}' cannot produce suggestion kind '{k.value}'"
                )
        return errors
