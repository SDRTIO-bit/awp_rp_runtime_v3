"""Model Profile Registry — controlled model configuration.

Profiles replace free-form model strings.  Each profileId resolves to a
fixed (provider, model, baseUrl, timeout, token_budget, retry_policy)
tuple.  Unknown profileIds fail closed.  API workflows cannot override
api_key, base_url, or token hard limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelProfile:
    """Immutable model configuration profile."""

    profile_id: str
    provider: str  # "deepseek", "openai", "fake"
    model: str
    base_url: str
    timeout_seconds: int = 60
    default_max_tokens: int = 4000
    max_retries: int = 1
    api_key_env: str = ""  # env var name — never the actual key
    token_hard_limit: int = 50_000  # per-turn cumulative

    def to_safe_dict(self) -> dict[str, Any]:
        """Export without secrets."""
        return {
            "profile_id": self.profile_id,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "default_max_tokens": self.default_max_tokens,
            "max_retries": self.max_retries,
            "api_key_env": self.api_key_env,
            "token_hard_limit": self.token_hard_limit,
        }


# ── Canonical whitelist ─────────────────────────────────────────────────────

_PROFILES: dict[str, ModelProfile] = {}


def _register(profile: ModelProfile) -> None:
    _PROFILES[profile.profile_id] = profile


# DeepSeek production profiles
_register(ModelProfile(
    profile_id="deepseek-v4-pro-director",
    provider="deepseek",
    model="deepseek-v4-pro",
    base_url="https://api.deepseek.com",
    timeout_seconds=120,
    default_max_tokens=4000,
    max_retries=2,
    api_key_env="DEEPSEEK_API_KEY",
    token_hard_limit=50_000,
))

_register(ModelProfile(
    profile_id="deepseek-v4-flash-writer",
    provider="deepseek",
    model="deepseek-v4-flash",
    base_url="https://api.deepseek.com",
    timeout_seconds=60,
    default_max_tokens=4000,
    max_retries=1,
    api_key_env="DEEPSEEK_API_KEY",
    token_hard_limit=50_000,
))

# Simulated player profile (low-cost model, isolated token budget).
# Used ONLY by the user-simulation harness, never by the RP turn pipeline.
_register(ModelProfile(
    profile_id="simulated-player-v1",
    provider="deepseek",
    model="deepseek-v4-flash",
    base_url="https://api.deepseek.com",
    timeout_seconds=60,
    default_max_tokens=1000,
    max_retries=1,
    api_key_env="DEEPSEEK_API_KEY",
    token_hard_limit=20_000,
))

# Fake simulated player for offline harness tests
_register(ModelProfile(
    profile_id="fake-player",
    provider="fake",
    model="fake_player_v1",
    base_url="",
    timeout_seconds=5,
    default_max_tokens=0,
    max_retries=0,
    api_key_env="",
    token_hard_limit=0,
))

# Fake profiles for testing
_register(ModelProfile(
    profile_id="fake-director",
    provider="fake",
    model="fake_director_v1",
    base_url="",
    timeout_seconds=5,
    default_max_tokens=0,
    max_retries=0,
    api_key_env="",
    token_hard_limit=0,
))

_register(ModelProfile(
    profile_id="fake-writer",
    provider="fake",
    model="fake_writer_v1",
    base_url="",
    timeout_seconds=5,
    default_max_tokens=0,
    max_retries=0,
    api_key_env="",
    token_hard_limit=0,
))


class ModelProfileRegistry:
    """Resolve profileId → ModelProfile.  Fail closed on unknown."""

    @staticmethod
    def resolve(profile_id: str) -> ModelProfile:
        """Resolve a profile ID to a ModelProfile.

        Raises ValueError for unknown profile IDs (fail closed).
        """
        profile = _PROFILES.get(profile_id)
        if profile is None:
            known = sorted(_PROFILES.keys())
            raise ValueError(
                f"Unknown model profile: '{profile_id}'. "
                f"Known profiles: {known}"
            )
        return profile

    @staticmethod
    def is_valid(profile_id: str) -> bool:
        """Check if a profile ID is in the whitelist."""
        return profile_id in _PROFILES

    @staticmethod
    def list_profiles() -> list[str]:
        """Return all registered profile IDs."""
        return sorted(_PROFILES.keys())
