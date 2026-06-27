"""Provider configuration for LLM adapters.

Configuration is read from environment variables.
API keys are NEVER stored in code, traces, or database.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider.

    All sensitive values come from environment variables.
    """
    # API key environment variable name
    api_key_env: str = "AWP_LLM_API_KEY"

    # Base URL environment variable name
    base_url_env: str = "AWP_LLM_BASE_URL"

    # Model name
    model: str = "gpt-4o-mini"

    # Default max tokens
    default_max_tokens: int = 4000

    # Request timeout in seconds
    timeout_seconds: int = 60

    # Max retries for structured output
    max_retries: int = 2

    @property
    def api_key(self) -> str:
        """Get API key from environment. Never stored in code."""
        return os.environ.get(self.api_key_env, "")

    @property
    def base_url(self) -> str:
        """Get base URL from environment."""
        return os.environ.get(self.base_url_env, "https://api.openai.com/v1")

    @property
    def is_configured(self) -> bool:
        """Check if this provider is configured."""
        return bool(self.api_key)

    def to_safe_dict(self) -> dict[str, str]:
        """Export config WITHOUT sensitive values."""
        return {
            "api_key_env": self.api_key_env,
            "base_url_env": self.base_url_env,
            "model": self.model,
            "default_max_tokens": str(self.default_max_tokens),
            "timeout_seconds": str(self.timeout_seconds),
            "is_configured": str(self.is_configured),
            # Note: api_key is NEVER included
        }


# Default configurations for different agent roles
DIRECTOR_CONFIG = ProviderConfig(
    api_key_env="AWP_DIRECTOR_API_KEY",
    base_url_env="AWP_DIRECTOR_BASE_URL",
    model="gpt-4o-mini",
)

WRITER_CONFIG = ProviderConfig(
    api_key_env="AWP_WRITER_API_KEY",
    base_url_env="AWP_WRITER_BASE_URL",
    model="gpt-4o-mini",
)

REVISER_CONFIG = ProviderConfig(
    api_key_env="AWP_REVISER_API_KEY",
    base_url_env="AWP_REVISER_BASE_URL",
    model="gpt-4o-mini",  # Can use cheaper model for revisions
)
