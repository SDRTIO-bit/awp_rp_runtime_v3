"""ToolPermissionRuntime — checks tool calls against allowlist.

V1 default: all tools denied unless explicitly allowed.
"""

from __future__ import annotations


class ToolPermissionRuntime:
    """Checks whether a tool call is allowed for a given envelope."""

    def is_tool_allowed(self, allowed_tools: list[str], tool_name: str) -> bool:
        """Check if a tool is in the allowlist. Empty list = all denied."""
        return tool_name in allowed_tools

    def check_tool_call(
        self, allowed_tools: list[str], tool_name: str
    ) -> tuple[bool, str]:
        """Returns (allowed, reason)."""
        if not allowed_tools:
            return False, "No tools are allowed for this task"
        if tool_name not in allowed_tools:
            return False, f"Tool '{tool_name}' is not in allowlist: {allowed_tools}"
        return True, "Tool is allowed"
