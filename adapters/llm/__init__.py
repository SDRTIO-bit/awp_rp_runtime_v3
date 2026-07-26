"""LLM provider adapters used by the novel pipeline."""

from .base import BaseLlmAdapter
from .deepseek_adapter import DeepSeekAdapter
from .openai_compatible import OpenAICompatibleAdapter

__all__ = ["BaseLlmAdapter", "DeepSeekAdapter", "OpenAICompatibleAdapter"]
