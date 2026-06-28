"""Provider Guardrail Config -- hard limits for real provider calls.

schemaId: awp.rp.provider-guardrail-config.v1

All real provider tests must have hard ceilings.
Never contains API keys or card content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA_ID = "awp.rp.provider-guardrail-config.v1"
SCHEMA_VERSION = 1


@dataclass
class ProviderGuardrailConfig:
    """Hard limits for real provider test execution.

    Any limit exceeded → fail closed, no more calls.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    max_turns: int = 12
    max_provider_calls: int = 48
    max_input_tokens_per_call: int = 4000
    max_output_tokens_per_call: int = 2000
    max_wall_clock_seconds_per_turn: int = 120
    max_retry_per_call: int = 1
    timeout_seconds: int = 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "max_turns": self.max_turns,
            "max_provider_calls": self.max_provider_calls,
            "max_input_tokens_per_call": self.max_input_tokens_per_call,
            "max_output_tokens_per_call": self.max_output_tokens_per_call,
            "max_wall_clock_seconds_per_turn": self.max_wall_clock_seconds_per_turn,
            "max_retry_per_call": self.max_retry_per_call,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderGuardrailConfig:
        return cls(
            max_turns=data.get("max_turns", 12),
            max_provider_calls=data.get("max_provider_calls", 48),
            max_input_tokens_per_call=data.get("max_input_tokens_per_call", 4000),
            max_output_tokens_per_call=data.get("max_output_tokens_per_call", 2000),
            max_wall_clock_seconds_per_turn=data.get("max_wall_clock_seconds_per_turn", 120),
            max_retry_per_call=data.get("max_retry_per_call", 1),
            timeout_seconds=data.get("timeout_seconds", 60),
        )

    def to_safe_summary(self) -> dict[str, Any]:
        """Export limits without any secrets."""
        return self.to_dict()
