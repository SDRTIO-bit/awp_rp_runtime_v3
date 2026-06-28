"""Real Writer Adapter -- uses DeepSeek for narrative text generation.

Implements WriterV2Adapter protocol with real provider calls.
On failure, produces structured ProviderFailure.

Supports writer presets: style guides, banned-word lists, and writing
constraints injected via --writer-preset-path node input.
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
    Accepts an optional preset_text for style/constraint injection.
    """

    def __init__(self, deepseek: DeepSeekAdapter, model: str = "",
                 preset_text: str = ""):
        self._llm = deepseek
        self._model = model
        self._preset_text = preset_text

    def set_preset(self, preset_text: str) -> None:
        """Inject a writer preset (style guide, banned words, constraints)."""
        self._preset_text = preset_text

    def generate(
        self,
        bundle: WriterInputBundle,
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
        snapshot: Any = None,
    ) -> tuple[str, ProviderAttemptReceipt]:
        """Generate narrative text with self-check and revise loop.

        After initial generation, runs deterministic checks (word count,
        banned words, formatting) and requests revision if needed.
        Max 2 revision attempts.
        """
        MAX_REVISIONS = 2
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

        # ── Self-check and revise loop ──────────────────────────────────
        for rev in range(MAX_REVISIONS):
            issues = self._check_output(text)
            if not issues:
                break  # All checks passed

            # Build revise prompt with specific issues
            revise_prompt = self._build_revise_prompt(prompt, text, issues, rev + 1)
            revised_text, rev_receipt = self._llm.generate_text(
                revise_prompt,
                provider_role="writer_revise",
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                model=self._model,
                turn_id=turn_id,
                attempt_id=f"{attempt_id}_r{rev+1}",
            )
            if revised_text.strip():
                text = revised_text
                receipt = rev_receipt

        return text, receipt

    # ── Output quality checks (deterministic) ───────────────────────────

    def _check_output(self, text: str) -> list[str]:
        """Run deterministic checks on generated text.

        Returns list of issue descriptions. Empty list = all passed.
        """
        issues = []
        length = len(text.strip()) if text else 0

        # Word count check
        if length < 1000:
            issues.append(
                f"WORD_COUNT_CRITICAL: only {length} characters. "
                f"Minimum is 1000, target is 1200-1600. Please expand significantly."
            )
        elif length < 1200:
            issues.append(
                f"WORD_COUNT_LOW: {length} characters. "
                f"Target is 1200-1600. Need {1200 - length} more characters. "
                f"Add more sensory details, internal monologue, or scene description."
            )
        elif length > 1600:
            issues.append(
                f"WORD_COUNT_HIGH: {length} characters. "
                f"Target is 1200-1600. Trim {length - 1600} characters."
            )

        # Format artifact check
        if text.strip().startswith("#"):
            issues.append(
                "FORMAT_ERROR: Text starts with markdown heading '#'. "
                "Remove any meta-commentary markers. Start directly with narrative prose."
            )

        # Banned word quick-scan (partial, performance-conscious)
        BANNED_QUICK = [
            "不是而是", "狡黠", "餍足", "氤氲", "旖旎", "喟叹",
            "不容置疑", "不容错辨", "几不可闻", "几不可察",
        ]
        found = [w for w in BANNED_QUICK if w in text]
        if found:
            issues.append(
                f"BANNED_WORDS: Found prohibited terms: {', '.join(found)}. "
                f"Replace them according to the preset guidelines."
            )

        # Player input recap check (simplified: flag if text looks like dialogue recap)
        if "你说：" in text or "你问道：" in text or "你说，" in text:
            issues.append(
                "NO_RECAP_VIOLATION: Text appears to recap player's words. "
                "Never restate what the player said. Continue the scene naturally."
            )

        return issues

    def _build_revise_prompt(
        self, original_prompt: str, current_text: str, issues: list[str], attempt: int
    ) -> str:
        """Build a revision prompt with specific feedback."""
        issue_text = "\n".join(f"- {i}" for i in issues)
        return (
            f"=== REVISION REQUEST (attempt {attempt}) ===\n\n"
            f"Your previous output had the following issues:\n"
            f"{issue_text}\n\n"
            f"=== ORIGINAL INSTRUCTIONS ===\n"
            f"{original_prompt}\n\n"
            f"=== YOUR PREVIOUS OUTPUT (for reference) ===\n"
            f"{current_text[:2000]}\n\n"
            f"Please rewrite the ENTIRE narrative response, fixing ALL issues listed above. "
            f"Follow ALL preset guidelines. Do NOT include any meta-commentary, "
            f"markdown headers, or formatting markers. Start directly with narrative prose."
        )

    def _build_writer_prompt(self, bundle: WriterInputBundle, snapshot: Any = None) -> str:
        """Build prompt for Writer text generation.

        Contains only safe summary data, never full card text or API keys.
        Uses the optional snapshot for player_input, scene, and worldbook context.
        Prepends writer_preset if configured.
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

        # ── Build prompt parts ──────────────────────────────────────────
        parts = []

        # Inject writer preset as highest-priority system instructions
        if self._preset_text:
            parts.append("=== WRITER STYLE & CONSTRAINT PRESET (highest priority) ===")
            parts.append(self._preset_text)
            parts.append("=== END PRESET ===")
            parts.append("")

        parts.extend([
            f"You are a creative roleplay writer. Write the next narrative response.",
            f"",
            f"Scene: {scene_location}",
            f"Turn goal: {turn_goal}",
            f"Scene focus: {scene_focus}",
            f"Player said: {player_input}",
        ])

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

        if self._preset_text:
            parts.append(f"Write the next narrative response. Follow ALL preset guidelines above — including word count, paragraph structure, style, and banned words. Do NOT use a default word limit.")
        else:
            parts.append(f"Write a narrative response that continues the scene naturally.")

        return "\n".join(parts)
