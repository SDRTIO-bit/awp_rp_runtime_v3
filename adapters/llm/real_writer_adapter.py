"""Real Writer Adapter using the configured provider."""

from __future__ import annotations

from typing import Any

from .deepseek_adapter import DeepSeekAdapter, SYSTEM_PROMPT_WRITER
from ...contracts.provider_request import ProviderAttemptReceipt
from ...contracts.writer_input_bundle import WriterInputBundle


class RealWriterV2Adapter:
    """Real Writer adapter using DeepSeek."""

    def __init__(self, deepseek: DeepSeekAdapter, model: str = "", preset_text: str = ""):
        self._llm = deepseek
        self._model = model
        self._preset_text = preset_text
        # Writer uses Pro model — disable thinking for faster, more direct output
        self._extra_body = {"thinking": {"type": "disabled"}}

    def set_preset(self, preset_text: str) -> None:
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
        """Generate narrative text with a deterministic revise loop."""
        _ = snapshot
        max_revisions = 2
        system_prompt = self._build_writer_system_prompt()
        user_prompt = self._build_writer_user_prompt(bundle)

        text, receipt = self._llm.generate_text(
            user_prompt,
            provider_role="writer",
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            model=self._model,
            turn_id=turn_id,
            attempt_id=attempt_id,
            extra_body=self._extra_body,
            system_prompt=system_prompt,
        )

        for rev in range(max_revisions):
            issues = self._check_output(text)
            if not issues:
                break
            revise_prompt = self._build_revise_prompt(user_prompt, text, issues, rev + 1)
            revised_text, rev_receipt = self._llm.generate_text(
                revise_prompt,
                provider_role="writer_revise",
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                model=self._model,
                turn_id=turn_id,
                attempt_id=f"{attempt_id}_r{rev + 1}",
                extra_body=self._extra_body,
                system_prompt=system_prompt,
            )
            if revised_text.strip():
                text = revised_text
                receipt = rev_receipt

        return text, receipt

    def _build_writer_system_prompt(self) -> str:
        """Build Writer system prompt with optional preset.

        Preset is prepended to system prompt for caching efficiency.
        """
        if self._preset_text:
            return f"""=== WRITER STYLE & CONSTRAINT PRESET (highest priority) ===
{self._preset_text}
=== END PRESET ===

{SYSTEM_PROMPT_WRITER}"""
        return SYSTEM_PROMPT_WRITER

    def _build_writer_prompt(self, bundle: WriterInputBundle) -> str:
        """Backward-compatible alias for _build_writer_user_prompt."""
        return self._build_writer_user_prompt(bundle)

    def _build_writer_user_prompt(self, bundle: WriterInputBundle) -> str:
        """Build user prompt for Writer text generation.

        Separates stable worldbook context from volatile turn data for
        provider prefix caching. Role/workflow/rules instructions are in
        the system prompt (SYSTEM_PROMPT_WRITER), not repeated here.
        """
        brief_dict = bundle.final_turn_brief or {}
        turn_goal = str(brief_dict.get("turn_goal", "") or "")
        scene_focus = str(brief_dict.get("scene_focus", "") or "")
        must_preserve = list(brief_dict.get("must_preserve_facts", []) or [])
        must_not_do = list(brief_dict.get("must_not_do", []) or [])
        constraints = list(brief_dict.get("writer_constraints", []) or [])
        opportunities = list(brief_dict.get("narrative_opportunities", []) or [])
        pacing_guidance = str(brief_dict.get("pacing_guidance", "") or "")
        risk_flags = list(brief_dict.get("risk_flags", []) or [])

        card_state = bundle.card_state_context or {}
        scene_state = card_state.get("scene_state", {}) if isinstance(card_state, dict) else {}
        scene_location = str(scene_state.get("location", "") or "")
        player_input = str(bundle.player_input or "")[:500]
        opening_text = str((bundle.opening_context or {}).get("safe_display_content", "") or "")[:300]

        # ── Worldbook: split stable (constant) vs dynamic ───────────────
        stable_worldbook_lines = []
        dynamic_worldbook_lines = []
        for entry in (bundle.worldbook_context or []):
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title", "") or entry.get("entry_id", "Untitled"))
            content = str(entry.get("content_excerpt", "") or "")
            activation_reason = str(entry.get("activation_reason", "") or "")
            matched = entry.get("matched_keywords", [])
            matched_text = ", ".join(str(item) for item in matched[:5]) if isinstance(matched, list) else ""
            line = f"- {title}: {content}"
            if activation_reason:
                line += f" (reason: {activation_reason})"
            if matched_text:
                line += f" (matched: {matched_text})"
            is_constant = (
                bool(entry.get("constant", False))
                or str(entry.get("entry_kind", "") or "") == "constant"
                or activation_reason == "constant"
            )
            if is_constant:
                stable_worldbook_lines.append(line)
            else:
                dynamic_worldbook_lines.append(line[:240])
        stable_worldbook_block = "\n".join(stable_worldbook_lines) if stable_worldbook_lines else "None"
        dynamic_worldbook_block = "\n".join(dynamic_worldbook_lines[:8]) if dynamic_worldbook_lines else "None"

        # ── Recent turns (last 5, truncated) ────────────────────────────
        recent_turn_lines = []
        for turn in (bundle.recent_turns_context or [])[:5]:
            if not isinstance(turn, dict):
                continue
            turn_index = turn.get("turn_index", "?")
            recent_turn_lines.append(
                f"Turn {turn_index} Player: {str(turn.get('player_input', '') or '')[:300]}"
            )
            recent_turn_lines.append(
                f"Turn {turn_index} Writer: {str(turn.get('writer_output', '') or '')[:400]}"
            )
        recent_turns_block = "\n".join(recent_turn_lines) if recent_turn_lines else "None"

        # ── Active memories (top 8, truncated) ──────────────────────────
        active_memory_lines = []
        for entry in (bundle.active_memory_context or [])[:8]:
            if isinstance(entry, dict):
                summary = str(entry.get("summary", "") or entry.get("content", "") or "")[:160]
                if summary:
                    active_memory_lines.append(f"- {summary}")
        active_memory_block = "\n".join(active_memory_lines) if active_memory_lines else "None"

        # ── RAG memories (top 6, truncated) ─────────────────────────────
        rag_memory_lines = []
        for entry in (bundle.rag_memory_context or [])[:6]:
            if isinstance(entry, dict):
                summary = str(entry.get("summary", "") or entry.get("content", "") or "")[:160]
                if summary:
                    rag_memory_lines.append(f"- {summary}")
        rag_memory_block = "\n".join(rag_memory_lines) if rag_memory_lines else "None"

        # ── Sub-agent guidance (from D1-D5 rule triggers) ──────────────
        sub_agent_guidance = list(getattr(bundle, 'accepted_guidance', []) or [])
        filtered_guidance = [g[:200] for g in sub_agent_guidance if g.strip()][:8]
        sub_agent_block = ""
        if filtered_guidance:
            guidance_lines = "\n".join(
                f"{i+1}. {g}" for i, g in enumerate(filtered_guidance)
            )
            sub_agent_block = f"-- Sub-agent guidance --\n{guidance_lines}\n"

        # ── Helper: format list ─────────────────────────────────────────
        def format_list(items: list[str], none_text: str = "None") -> str:
            if not items:
                return none_text
            return "\n".join(f"- {item}" for item in items)

        must_preserve_str = format_list(must_preserve)
        must_not_str = format_list(must_not_do)
        constraints_str = format_list(constraints)
        opportunities_str = format_list(opportunities)
        risks_str = format_list(risk_flags)

        # ── Opening context (only if present) ───────────────────────────
        opening_context_block = ""
        if opening_text:
            opening_context_block = f"Opening context:\n{opening_text}\n"

        return f"""You are a creative roleplay writer.
Keep the fixed instructions above separate from the volatile turn context below so provider prefix caching can be reused.

=== STABLE WRITER CONTRACT ===

This block contains stable worldbuilding context. It changes infrequently.
The instructions above (role, workflow, output rules) remain in effect.

{opening_context_block}
Stable worldbook context:
{stable_worldbook_block}

Write narrative prose only. Do not output JSON, debug info, or analysis.

=== TURN PACKET (volatile; changes every turn) ===

Scene: {scene_location}
Turn goal: {turn_goal}
Scene focus: {scene_focus}
Player said: {player_input}

-- Director's constraints for this turn --
Must preserve:
{must_preserve_str}

Must not do:
{must_not_str}

Writer constraints:
{constraints_str}

Narrative opportunities:
{opportunities_str}

Pacing guidance: {pacing_guidance}

Risk flags:
{risks_str}

-- Context --
Recent turns:
{recent_turns_block}

Active memories:
{active_memory_block}

RAG recall:
{rag_memory_block}

Dynamic worldbook context:
{dynamic_worldbook_block}

{sub_agent_block}
Write the next narrative response now."""

    def _check_output(self, text: str) -> list[str]:
        """Run deterministic checks on generated text."""
        issues = []
        length = len(text.strip()) if text else 0
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

        if text.strip().startswith("#"):
            issues.append(
                "FORMAT_ERROR: Text starts with markdown heading '#'. "
                "Remove meta markers and begin with narrative prose."
            )
        return issues

    def _build_revise_prompt(
        self,
        original_prompt: str,
        current_text: str,
        issues: list[str],
        attempt: int,
    ) -> str:
        issue_text = "\n".join(f"- {item}" for item in issues)
        return (
            f"{original_prompt}\n\n"
            f"=== REVISION REQUEST (attempt {attempt}; volatile) ===\n\n"
            f"Your previous output had the following issues:\n"
            f"{issue_text}\n\n"
            f"=== YOUR PREVIOUS OUTPUT (for reference) ===\n"
            f"{current_text[:2000]}\n\n"
            f"Please rewrite the entire narrative response, fixing every issue above. "
            f"Do not add meta commentary or markdown headers."
        )
