"""WriterV2Runtime - upgraded Writer for C1.

Writer reads WriterInputBundle and produces WriterDraft.
Writer does NOT:
- Access CardState Store
- Access TurnRecord Store
- Access Memory Store
- Call ToolGateway
- Retrieve worldbook directly
- Delegate to sub-agents
- Write state or memory
- Output JSON, debug info, or system statements
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from ..contracts.writer_input_bundle import WriterInputBundle
from ..contracts.writer_draft import WriterDraft


class WriterV2Adapter(Protocol):
    """Protocol for Writer V2 adapters (fake or real LLM)."""

    def generate(self, bundle: WriterInputBundle) -> str:
        """Generate player-visible RP text from WriterInputBundle."""
        ...


class FakeWriterV2Adapter:
    """Fake Writer V2 for testing. Returns deterministic text."""

    def __init__(self):
        self._custom_text: str | None = None

    def set_text(self, text: str):
        self._custom_text = text

    def generate(self, bundle: WriterInputBundle) -> str:
        if self._custom_text:
            return self._custom_text

        brief = bundle.final_turn_brief or {}
        scene = str(brief.get("scene_focus", "current scene") or "current scene")
        goal = str(brief.get("turn_goal", "continue the interaction") or "continue the interaction")
        opening = str((bundle.opening_context or {}).get("safe_display_content", "") or "")[:220]
        player_input = str(bundle.player_input or "")[:240]
        worldbook_titles = [
            str(entry.get("title", "") or entry.get("entry_id", ""))
            for entry in (bundle.worldbook_context or [])[:3]
            if isinstance(entry, dict)
        ]
        worldbook_hint = ", ".join(title for title in worldbook_titles if title) or "no explicit worldbook title"
        prior_writer = ""
        if bundle.recent_turns_context:
            prior_writer = str(bundle.recent_turns_context[0].get("writer_output", "") or "")[:220]

        paragraph = (
            f"Scene focus: {scene}. Turn goal: {goal}. "
            f"The selected opening still matters here: {opening or 'no opening text provided'}. "
            f"The player just said: {player_input or 'no player input provided'}. "
            f"Worldbook cues currently in scope include {worldbook_hint}, and the reply should treat them as active facts rather than decoration. "
            f"The narration keeps the exchange grounded in concrete sensory detail, preserves continuity with the last accepted reply, and moves the scene forward without exposing any system data or tool traces. "
            f"When prior context exists, it remains visible inside the cadence of the answer: {prior_writer or 'there is no previous accepted writer output yet'}. "
            f"The response therefore expands on intent, atmosphere, gesture, timing, and consequence so the scene reads like a real roleplay turn instead of a stub, while still leaving space for the next player action."
        )
        return "\n\n".join([paragraph] * 5)


class WriterV2Runtime:
    """Runtime for the Writer V2 agent."""

    def __init__(self, adapter: WriterV2Adapter):
        self.adapter = adapter

    def run(self, bundle: WriterInputBundle) -> WriterDraft:
        """Run Writer to produce a WriterDraft."""
        now = datetime.now(timezone.utc).isoformat()
        text = self.adapter.generate(bundle)
        return WriterDraft(
            draft_id=f"wd_{uuid.uuid4().hex[:12]}",
            trace_id=bundle.trace_id,
            snapshot_id=bundle.snapshot_id,
            writer_input_bundle_id=bundle.bundle_id,
            text=text,
            character_count=len(text),
            revision_number=0,
            created_at=now,
        )

    def revise(
        self,
        bundle: WriterInputBundle,
        original_text: str,
        issues: list[dict[str, Any]],
        revision_number: int,
    ) -> WriterDraft:
        """Revise a draft based on quality issues."""
        now = datetime.now(timezone.utc).isoformat()
        text = self.adapter.generate(bundle)
        return WriterDraft(
            draft_id=f"wd_{uuid.uuid4().hex[:12]}",
            trace_id=bundle.trace_id,
            snapshot_id=bundle.snapshot_id,
            writer_input_bundle_id=bundle.bundle_id,
            text=text,
            character_count=len(text),
            revision_number=revision_number,
            created_at=now,
        )
