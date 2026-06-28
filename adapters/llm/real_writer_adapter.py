"""Real Writer Adapter -- uses DeepSeek for narrative text generation.

Implements WriterV2Adapter protocol with real provider calls.
On failure, produces structured ProviderFailure.
"""

from __future__ import annotations

from typing import Any

from .deepseek_adapter import DeepSeekAdapter
from ...contracts.writer_draft import WriterDraft
from ...contracts.writer_input_bundle import WriterInputBundle
from ...contracts.provider_request import ProviderAttemptReceipt


class RealWriterV2Adapter:
    """Real Writer adapter using DeepSeek.

    Generates narrative RP text from WriterInputBundle.
    """

    def __init__(self, deepseek: DeepSeekAdapter, model: str = ""):
        self._llm = deepseek
        self._model = model

    def generate(
        self,
        bundle: WriterInputBundle,
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
        snapshot: Any = None,
    ) -> tuple[str, ProviderAttemptReceipt]:
        """Generate narrative text from writer input bundle.

        snapshot is an optional RoundSnapshot for player_input, scene_location,
        and worldbook context. It is never stored or logged — only used to build
        the prompt.
        """
        prompt = self._build_writer_prompt(bundle, snapshot)

        text, receipt = self._llm.generate_text(
            prompt,
            provider_role="writer",
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            model=self._model,
            turn_id=turn_id,
            attempt_id=attempt_id,
        )

        return text, receipt

    def _build_writer_prompt(self, bundle: WriterInputBundle, snapshot: Any = None) -> str:
        """Build prompt for Writer text generation.

        Contains only safe summary data, never full card text or API keys.
        Uses the optional snapshot for player_input, scene, and worldbook context.
        """
        brief_dict = bundle.final_turn_brief
        brief = None
        turn_goal = ""
        scene_focus = ""
        must_preserve = []
        must_not_do = []
        constraints = []
        opportunities = []

        if isinstance(brief_dict, dict):
            turn_goal = brief_dict.get("turn_goal", "")
            scene_focus = brief_dict.get("scene_focus", "")
            must_preserve = brief_dict.get("must_preserve_facts", [])
            must_not_do = brief_dict.get("must_not_do", [])
            constraints = brief_dict.get("writer_constraints", [])
            opportunities = brief_dict.get("narrative_opportunities", [])
        elif brief_dict is not None:
            brief = brief_dict
            turn_goal = brief.turn_goal if hasattr(brief, 'turn_goal') else ""
            scene_focus = brief.scene_focus if hasattr(brief, 'scene_focus') else ""
            must_preserve = brief.must_preserve_facts if hasattr(brief, 'must_preserve_facts') else []
            must_not_do = brief.must_not_do if hasattr(brief, 'must_not_do') else []
            constraints = brief.writer_constraints if hasattr(brief, 'writer_constraints') else []
            opportunities = brief.narrative_opportunities if hasattr(brief, 'narrative_opportunities') else []

        player_input = ""
        scene_location = ""
        wb_summaries = []
        if snapshot is not None:
            player_input = getattr(snapshot, 'player_input', '')[:500]
            if hasattr(snapshot, 'card_state') and hasattr(snapshot.card_state, 'scene_state'):
                scene_location = getattr(snapshot.card_state.scene_state, 'location', '')
            for entry in getattr(snapshot, 'active_worldbook_entries', [])[:5]:
                if isinstance(entry, dict):
                    title = entry.get("title", "")
                    content_preview = entry.get("content", "")[:100]
                    wb_summaries.append(f"- {title}: {content_preview}...")

        wb_context = "\n".join(wb_summaries) if wb_summaries else "None"

        # Opening context
        opening_text = ""
        if hasattr(bundle, 'opening_context') and bundle.opening_context:
            opening_text = bundle.opening_context.get("safe_display_content", "")[:300]

        parts = [
            f"You are a creative roleplay writer. Write the next narrative response.",
            f"",
            f"Scene: {scene_location}",
            f"Turn goal: {turn_goal}",
            f"Scene focus: {scene_focus}",
            f"Player said: {player_input}",
        ]

        if opening_text:
            parts.append(f"Opening context: {opening_text}")

        if must_preserve:
            parts.append(f"Must preserve: {', '.join(must_preserve[:3])}")

        if must_not_do:
            parts.append(f"Must not do: {', '.join(must_not_do[:3])}")

        if constraints:
            parts.append(f"Constraints: {', '.join(constraints[:3])}")

        if opportunities:
            parts.append(f"Opportunities: {', '.join(opportunities[:3])}")

        parts.append(f"Worldbook context:\n{wb_context}")
        parts.append(f"")
        parts.append(f"Write a narrative response (200-500 characters) that continues the scene naturally.")

        return "\n".join(parts)
