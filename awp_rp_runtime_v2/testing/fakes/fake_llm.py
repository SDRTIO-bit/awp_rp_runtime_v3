"""Fake LLM provider for testing.

Returns deterministic responses based on the prompt content.
No actual LLM calls are made.
"""

from __future__ import annotations

from typing import Any

from ...contracts.turn_brief import TurnBrief, NarrativeGoal
from ...contracts.delegation_plan import DelegationPlan, DelegationTask
from ...contracts.agent_suggestion import AgentSuggestion, SuggestionType
from ...contracts.quality_decision import QualityDecision, QualityVerdict
from ...contracts.state_update_proposal import StateUpdateProposal, PatchOp, PatchOpEntry


class FakeLLMProvider:
    """Fake LLM that returns deterministic structured responses."""

    def __init__(self):
        self.call_count = 0
        self.last_prompt = ""
        self._custom_responses: dict[str, Any] = {}

    def set_response(self, key: str, value: Any) -> None:
        """Set a custom response for a key."""
        self._custom_responses[key] = value

    def generate_turn_brief(self, snapshot_summary: str) -> TurnBrief:
        """Generate a fake TurnBrief."""
        self.call_count += 1
        self.last_prompt = snapshot_summary

        if "turn_brief" in self._custom_responses:
            return self._custom_responses["turn_brief"]

        return TurnBrief(
            turn_id="fake_turn_001",
            narrative_intent="Continue the story naturally",
            goals=[
                NarrativeGoal(
                    goal_id="goal_1",
                    description="Advance the main plot",
                    priority=0.8,
                    category="plot",
                )
            ],
            constraints=["Maintain character consistency"],
            focus_entities=["player"],
            tone_guidance="Atmospheric and immersive",
            opportunities=["Introduce a subtle clue"],
            risks=["Avoid rushing the plot"],
            key_context="Player is exploring the scene",
        )

    def generate_delegation_plan(self, snapshot_summary: str) -> DelegationPlan:
        """Generate a fake DelegationPlan."""
        self.call_count += 1

        if "delegation_plan" in self._custom_responses:
            return self._custom_responses["delegation_plan"]

        # Default: no sub-agents
        return DelegationPlan(
            turn_id="fake_turn_001",
            mode="none",
            reason="Simple turn, no delegation needed",
            tasks=[],
        )

    def generate_suggestion(self, task: DelegationTask) -> AgentSuggestion:
        """Generate a fake AgentSuggestion."""
        self.call_count += 1

        if "suggestion" in self._custom_responses:
            return self._custom_responses["suggestion"]

        return AgentSuggestion(
            suggestion_id=f"sug_{task.task_id}",
            task_id=task.task_id,
            role=task.role,
            suggestion_type=SuggestionType.NARRATIVE_OPPORTUNITY,
            title="A subtle opportunity",
            content="Consider adding a environmental detail",
            importance=0.6,
            risk=0.1,
            evidence=["Previous turn mentioned the setting"],
            source_refs=["turn_record:prev"],
        )

    def generate_candidate_text(
        self, snapshot_summary: str, turn_brief: dict[str, Any],
        adopted_suggestions: list[dict[str, Any]],
    ) -> str:
        """Generate fake candidate RP text."""
        self.call_count += 1

        if "candidate_text" in self._custom_responses:
            return self._custom_responses["candidate_text"]

        # Generate text that meets minimum length
        return (
            "月光如水，洒在青石板路上。远处传来若有若无的笛声，"
            "仿佛在诉说着什么不为人知的故事。空气中弥漫着淡淡的花香，"
            "混合着夜露的清凉。角色缓步前行，每一步都踏在光影交错之间，"
            "仿佛行走在现实与梦境的边界。周围的景色在月色下显得格外宁静，"
            "却又似乎隐藏着某种不可言说的秘密。这是一段足够长的测试文本，"
            "用于满足质量门的最低长度要求。故事继续向前推进，"
            "每一个细节都在为接下来的剧情做铺垫。"
        )

    def check_quality(self, candidate_text: str) -> QualityDecision:
        """Run fake quality check."""
        self.call_count += 1

        if "quality_decision" in self._custom_responses:
            return self._custom_responses["quality_decision"]

        # Simple length check
        if len(candidate_text) < 100:
            return QualityDecision(
                verdict=QualityVerdict.REJECTED,
                candidate_text=candidate_text,
                checks=[{"name": "length", "passed": False, "details": "Too short"}],
                overall_score=0.2,
                rejection_reasons=["Text too short"],
                retry_allowed=True,
                retry_count=0,
            )

        return QualityDecision(
            verdict=QualityVerdict.ACCEPTED,
            candidate_text=candidate_text,
            checks=[
                {"name": "length", "passed": True, "details": "Sufficient length"},
                {"name": "format", "passed": True, "details": "Valid format"},
            ],
            overall_score=0.9,
            acceptance_notes=["Passed all checks"],
        )

    def generate_state_proposal(
        self, accepted_text: str, snapshot_summary: str
    ) -> StateUpdateProposal:
        """Generate a fake state update proposal."""
        self.call_count += 1

        if "state_proposal" in self._custom_responses:
            return self._custom_responses["state_proposal"]

        return StateUpdateProposal(
            turn_id="fake_turn_001",
            card_id="test_card",
            session_id="test_session",
            operations=[],
            source="fake_llm",
            confidence=0.8,
        )
