"""AWPV2Director — runs the Director agent.

Input: round_snapshot
Output: turn_brief, delegation_plan
"""

from __future__ import annotations

from typing import Any


class AWPV2Director:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"round_snapshot": ("ROUND_SNAPSHOT",)}}

    RETURN_TYPES = ("TURN_BRIEF", "DELEGATION_PLAN")
    RETURN_NAMES = ("turn_brief", "delegation_plan")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(self, round_snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        from ..contracts.round_snapshot import RoundSnapshot
        from ..runtime.director_runtime import DirectorRuntime, FakeDirectorAdapter

        snapshot = RoundSnapshot.from_dict(round_snapshot)
        adapter = FakeDirectorAdapter()
        director = DirectorRuntime(adapter)
        brief, plan = director.run(snapshot)
        return (brief.to_dict(), plan.to_dict())
