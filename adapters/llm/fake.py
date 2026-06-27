"""Fake LLM adapter for testing.

Returns deterministic responses. No actual LLM calls.
Used as the default adapter for all tests.
"""

from __future__ import annotations

from typing import Any

from .base import BaseLlmAdapter


class FakeLlmAdapter(BaseLlmAdapter):
    """Fake LLM adapter for testing.

    Returns deterministic responses based on prompt content.
    No actual LLM calls are made.
    """

    def __init__(self):
        self.call_count = 0
        self.last_prompt = ""
        self._custom_responses: dict[str, Any] = {}

    def set_response(self, key: str, value: Any) -> None:
        """Set a custom response for a key."""
        self._custom_responses[key] = value

    def generate_text(self, prompt: str, max_tokens: int = 4000) -> str:
        """Generate fake text."""
        self.call_count += 1
        self.last_prompt = prompt

        if "text" in self._custom_responses:
            return self._custom_responses["text"]

        return (
            "月光如水，洒在青石板路上。远处传来若有若无的笛声，"
            "仿佛在诉说着什么不为人知的故事。空气中弥漫着淡淡的花香，"
            "混合着夜露的清凉。角色缓步前行，每一步都踏在光影交错之间，"
            "仿佛行走在现实与梦境的边界。周围的景色在月色下显得格外宁静，"
            "却又似乎隐藏着某种不可言说的秘密。这是一段足够长的测试文本，"
            "用于满足质量门的最低长度要求。故事继续向前推进，"
            "每一个细节都在为接下来的剧情做铺垫。"
        )

    def generate_structured(
        self, prompt: str, schema: dict[str, Any], max_tokens: int = 4000
    ) -> dict[str, Any]:
        """Generate fake structured output."""
        self.call_count += 1
        self.last_prompt = prompt

        if "structured" in self._custom_responses:
            return self._custom_responses["structured"]

        # Return a minimal valid structure
        return {"result": "fake_structured_output", "confidence": 0.8}

    @property
    def model_name(self) -> str:
        return "fake-model-v1"

    @property
    def is_available(self) -> bool:
        return True
