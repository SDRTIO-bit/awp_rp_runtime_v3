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

    def __init__(self, deepseek: DeepSeekAdapter):
        self._llm = deepseek

    def generate(
        self,
        bundle: WriterInputBundle,
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
    ) -> tuple[str, ProviderAttemptReceipt]:
        """Generate narrative text from writer input bundle."""
        prompt = self._build_writer_prompt(bundle)

        text, receipt = self._llm.generate_text(
            prompt,
            provider_role="writer",
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
        )

        return text, receipt

    def _build_writer_prompt(self, bundle: WriterInputBundle) -> str:
        """Build prompt for Writer text generation.

        Contains only safe summary data, never full card text or API keys.
        """
        brief = bundle.final_turn_brief
        snapshot = bundle.round_snapshot

        turn_goal = brief.turn_goal if brief else ""
        scene_focus = brief.scene_focus if brief else ""
        must_preserve = brief.must_preserve_facts if brief else []
        must_not_do = brief.must_not_do if brief else []
        constraints = brief.writer_constraints if brief else []
        opportunities = brief.narrative_opportunities if brief else []

        player_input = snapshot.player_input[:500] if snapshot else ""
        scene_location = ""
        if snapshot and hasattr(snapshot.card_state, 'scene_state'):
            scene_location = getattr(snapshot.card_state.scene_state, 'location', '')

        # Worldbook context (safe summaries only)
        wb_summaries = []
        if snapshot:
            for entry in snapshot.active_worldbook_entries[:5]:
                if isinstance(entry, dict):
                    title = entry.get("title", "")
                    content_preview = entry.get("content", "")[:100]
                    wb_summaries.append(f"- {title}: {content_preview}...")

        wb_context = "\n".join(wb_summaries) if wb_summaries else "None"

        # Opening context
        opening_text = ""
        if bundle.opening_context:
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
