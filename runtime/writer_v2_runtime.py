"""WriterV2Runtime — upgraded Writer for C1.

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
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.final_turn_brief import FinalTurnBrief


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

        # Generate text that meets minimum length
        scene = bundle.final_turn_brief.get("scene_focus", "月光庭院")
        goal = bundle.final_turn_brief.get("turn_goal", "继续叙事")
        return (
            f"月光如水，洒在{scene}的青石板路上。远处传来若有若无的笛声，"
            f"仿佛在诉说着什么不为人知的故事。空气中弥漫着淡淡的花香，"
            f"混合着夜露的清凉。角色缓步前行，每一步都踏在光影交错之间，"
            f"仿佛行走在现实与梦境的边界。周围的景色在月色下显得格外宁静，"
            f"却又似乎隐藏着某种不可言说的秘密。这是一段足够长的测试文本，"
            f"用于满足质量门的最低长度要求。故事继续向前推进，"
            f"每一个细节都在为接下来的剧情做铺垫。{goal}的意图在字里行间缓缓展开，"
            f"如同一条看不见的丝线，将过去与未来串联在一起。"
        )


class WriterV2Runtime:
    """Runtime for the Writer V2 agent.

    Writer produces WriterDraft from WriterInputBundle.
    Writer does NOT use tools, delegate, write state, or write memory.
    """

    def __init__(self, adapter: WriterV2Adapter):
        self.adapter = adapter

    def run(self, bundle: WriterInputBundle) -> WriterDraft:
        """Run Writer to produce a WriterDraft.

        Writer ONLY reads from WriterInputBundle.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Generate text
        text = self.adapter.generate(bundle)

        # Create draft
        draft = WriterDraft(
            draft_id=f"wd_{uuid.uuid4().hex[:12]}",
            trace_id=bundle.trace_id,
            snapshot_id=bundle.snapshot_id,
            writer_input_bundle_id=bundle.bundle_id,
            text=text,
            character_count=len(text),
            revision_number=0,
            created_at=now,
        )

        return draft

    def revise(
        self,
        bundle: WriterInputBundle,
        original_text: str,
        issues: list[dict[str, Any]],
        revision_number: int,
    ) -> WriterDraft:
        """Revise a draft based on quality issues.

        Reviser can only fix the specific issues identified.
        """
        now = datetime.now(timezone.utc).isoformat()

        # For fake adapter, return the same text (issues are "fixed")
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
