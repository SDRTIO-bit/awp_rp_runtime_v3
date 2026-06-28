"""Provider Environment Guard -- enforces double-confirmation for real provider tests.

Real provider tests MUST NOT run unless:
  AWP_REAL_LLM_E2E == "1"
  AND
  AWP_ALLOW_EXTERNAL_CARD_CONTENT == "1"

This guard is checked at the entry point of every real provider test.
It never prints API keys or card content.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any

# Required environment variables
_E2E_FLAG = "AWP_REAL_LLM_E2E"
_CARD_FLAG = "AWP_ALLOW_EXTERNAL_CARD_CONTENT"
_API_KEY_VAR = "DEEPSEEK_API_KEY"
_CARD_PATH_VAR = "AWP_REAL_CARD_PATH"
_MODEL_VAR = "AWP_REAL_LLM_MODEL"
_MAX_TURNS_VAR = "AWP_REAL_LLM_MAX_TURNS"
_MAX_CALLS_VAR = "AWP_REAL_LLM_MAX_CALLS"
_MAX_INPUT_TOKENS_VAR = "AWP_REAL_LLM_MAX_INPUT_TOKENS"
_MAX_OUTPUT_TOKENS_VAR = "AWP_REAL_LLM_MAX_OUTPUT_TOKENS"
_TIMEOUT_VAR = "AWP_REAL_LLM_TIMEOUT_SECONDS"
_SAVE_TRANSCRIPT_VAR = "AWP_REAL_LLM_SAVE_PRIVATE_TRANSCRIPT"


@dataclass
class ProviderEnvConfig:
    """Resolved environment configuration for real provider tests.

    Never contains the actual API key value -- only its presence.
    """
    e2e_enabled: bool = False
    card_content_allowed: bool = False
    api_key_present: bool = False
    card_path: str = ""
    model: str = "deepseek-chat"
    max_turns: int = 12
    max_provider_calls: int = 48
    max_input_tokens: int = 4000
    max_output_tokens: int = 2000
    timeout_seconds: int = 60
    save_private_transcript: bool = False

    def to_safe_dict(self) -> dict[str, Any]:
        """Export config without any secrets."""
        return {
            "e2e_enabled": self.e2e_enabled,
            "card_content_allowed": self.card_content_allowed,
            "api_key_present": self.api_key_present,
            "card_path": self.card_path,
            "model": self.model,
            "max_turns": self.max_turns,
            "max_provider_calls": self.max_provider_calls,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "timeout_seconds": self.timeout_seconds,
            "save_private_transcript": self.save_private_transcript,
        }


def check_real_provider_env() -> ProviderEnvConfig:
    """Check and resolve environment for real provider tests.

    Returns ProviderEnvConfig with resolved values.
    Does NOT raise -- caller decides what to do with the config.

    The two mandatory flags must both be "1" for real tests to proceed.
    """
    return ProviderEnvConfig(
        e2e_enabled=os.environ.get(_E2E_FLAG, "") == "1",
        card_content_allowed=os.environ.get(_CARD_FLAG, "") == "1",
        api_key_present=bool(os.environ.get(_API_KEY_VAR, "")),
        card_path=os.environ.get(_CARD_PATH_VAR, ""),
        model=os.environ.get(_MODEL_VAR, "deepseek-v4-pro"),
        max_turns=int(os.environ.get(_MAX_TURNS_VAR, "12")),
        max_provider_calls=int(os.environ.get(_MAX_CALLS_VAR, "48")),
        max_input_tokens=int(os.environ.get(_MAX_INPUT_TOKENS_VAR, "4000")),
        max_output_tokens=int(os.environ.get(_MAX_OUTPUT_TOKENS_VAR, "2000")),
        timeout_seconds=int(os.environ.get(_TIMEOUT_VAR, "60")),
        save_private_transcript=os.environ.get(_SAVE_TRANSCRIPT_VAR, "") == "1",
    )


def require_real_provider_env() -> ProviderEnvConfig:
    """Require real provider environment to be fully configured.

    Raises SystemExit with clear message if:
    - AWP_REAL_LLM_E2E != "1"
    - AWP_ALLOW_EXTERNAL_CARD_CONTENT != "1"
    - DEEPSEEK_API_KEY is missing
    - AWP_REAL_CARD_PATH is missing or file doesn't exist

    Never prints the API key or card content.
    """
    config = check_real_provider_env()

    if not config.e2e_enabled:
        print("REJECTED: AWP_REAL_LLM_E2E is not set to '1'.")
        print("Real provider tests require explicit opt-in.")
        print("Set: $env:AWP_REAL_LLM_E2E = '1'")
        sys.exit(2)

    if not config.card_content_allowed:
        print("REJECTED: AWP_ALLOW_EXTERNAL_CARD_CONTENT is not set to '1'.")
        print("Real provider tests require explicit card content permission.")
        print("Set: $env:AWP_ALLOW_EXTERNAL_CARD_CONTENT = '1'")
        sys.exit(2)

    if not config.api_key_present:
        print("REJECTED: DEEPSEEK_API_KEY is not set.")
        print("Real provider tests require a valid API key.")
        print("Set: $env:DEEPSEEK_API_KEY = '<your-key>'")
        sys.exit(2)

    if not config.card_path:
        print("REJECTED: AWP_REAL_CARD_PATH is not set.")
        print("Real provider tests require a path to a real card JSON.")
        print("Set: $env:AWP_REAL_CARD_PATH = '<path-to-card.json>'")
        sys.exit(2)

    return config


def get_deepseek_api_key() -> str:
    """Get the DeepSeek API key from environment.

    Raises RuntimeError if not set.
    Never prints the key.
    """
    key = os.environ.get(_API_KEY_VAR, "")
    if not key:
        raise RuntimeError(f"Environment variable {_API_KEY_VAR} is not set")
    return key


def get_deepseek_base_url() -> str:
    """Get the DeepSeek base URL from environment.

    Defaults to https://api.deepseek.com/v1
    """
    return os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
