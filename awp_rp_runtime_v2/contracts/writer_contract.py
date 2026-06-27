"""WriterContract — the input contract for Writer.

schemaId: awp.rp.writer-contract.v1

Writer receives this contract and produces player-visible RP text.
Writer does NOT use tools, delegate, write state, or write memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.writer-contract.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WriterContract:
    """Input contract for Writer.

    Writer produces player-visible RP text based on this contract.
    Writer must NOT: use tools, delegate, write state, write memory,
    output JSON, output debug info, or output analysis.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    turn_id: str = ""

    # Core inputs
    round_snapshot_summary: str = ""  # Key facts from RoundSnapshot
    turn_brief: dict[str, Any] = field(default_factory=dict)  # Director's TurnBrief
    adopted_suggestions: list[dict[str, Any]] = field(default_factory=list)

    # Writer constraints
    min_length: int = 1000  # Minimum character count
    max_length: int = 5000  # Maximum character count
    style: str = "narrative"  # narrative | dialogue | mixed
    language: str = "zh"  # Output language

    # Character constraints
    focus_characters: list[str] = field(default_factory=list)
    perspective: str = "third_person"  # first_person | third_person | omniscient

    # Format constraints
    format_requirements: list[str] = field(default_factory=list)

    # Prohibitions for Writer
    prohibitions: list[str] = field(default_factory=lambda: [
        "Must not use tools or make tool calls",
        "Must not delegate to sub-agents",
        "Must not write to CardState, TurnRecord, or Memory",
        "Must not output JSON, debug info, or analysis",
        "Must not expose sub-agent suggestions to player",
        "Must not modify variables or event flags directly",
    ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "turn_id": self.turn_id,
            "round_snapshot_summary": self.round_snapshot_summary,
            "turn_brief": self.turn_brief,
            "adopted_suggestions": self.adopted_suggestions,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "style": self.style,
            "language": self.language,
            "focus_characters": self.focus_characters,
            "perspective": self.perspective,
            "format_requirements": self.format_requirements,
            "prohibitions": self.prohibitions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WriterContract:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            turn_id=data.get("turn_id", ""),
            round_snapshot_summary=data.get("round_snapshot_summary", ""),
            turn_brief=data.get("turn_brief", {}),
            adopted_suggestions=data.get("adopted_suggestions", []),
            min_length=data.get("min_length", 1000),
            max_length=data.get("max_length", 5000),
            style=data.get("style", "narrative"),
            language=data.get("language", "zh"),
            focus_characters=data.get("focus_characters", []),
            perspective=data.get("perspective", "third_person"),
            format_requirements=data.get("format_requirements", []),
            prohibitions=data.get("prohibitions", [
                "Must not use tools or make tool calls",
                "Must not delegate to sub-agents",
                "Must not write to CardState, TurnRecord, or Memory",
                "Must not output JSON, debug info, or analysis",
                "Must not expose sub-agent suggestions to player",
                "Must not modify variables or event flags directly",
            ]),
        )
