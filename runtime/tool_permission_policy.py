"""ToolPermissionPolicy — unified permission checking for all tool calls.

Default: deny. Only explicit allowlist permits execution.
Isolated by cardId + sessionId. Scoped to snapshot allowed fields.
"""

from __future__ import annotations

from ..contracts.tool_permission import ToolPermission
from ..contracts.tool_plan import PlannedToolRequest
from ..contracts.round_snapshot import RoundSnapshot
from .tool_registry import ToolRegistry


class ToolPermissionPolicy:
    """Unified permission checking for all tool calls.

    Default principle: DENY.
    Only explicitly allowed tools in the correct scope are permitted.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def check(
        self,
        request: PlannedToolRequest,
        snapshot: RoundSnapshot,
    ) -> ToolPermission:
        """Check if a tool request is permitted.

        Returns ToolPermission with allowed=True/False and reason.
        """
        # 1. Tool must be registered
        if not self.registry.is_registered(request.tool_id):
            return ToolPermission(
                tool_id=request.tool_id,
                request_id=request.request_id,
                card_id=snapshot.card_id,
                session_id=snapshot.session_id,
                allowed=False,
                reason=f"Tool '{request.tool_id}' is not registered",
            )

        reg = self.registry.get(request.tool_id)

        # 2. Tool must be side-effect-free (V1)
        if not reg.side_effect_free:
            return ToolPermission(
                tool_id=request.tool_id,
                request_id=request.request_id,
                card_id=snapshot.card_id,
                session_id=snapshot.session_id,
                allowed=False,
                reason=f"Tool '{request.tool_id}' has side effects (not allowed in V1)",
            )

        # 3. Tool must not write state
        if reg.can_write_state:
            return ToolPermission(
                tool_id=request.tool_id,
                request_id=request.request_id,
                card_id=snapshot.card_id,
                session_id=snapshot.session_id,
                allowed=False,
                reason=f"Tool '{request.tool_id}' can write state (not allowed)",
            )

        # 4. Tool must not write memory
        if reg.can_write_memory:
            return ToolPermission(
                tool_id=request.tool_id,
                request_id=request.request_id,
                card_id=snapshot.card_id,
                session_id=snapshot.session_id,
                allowed=False,
                reason=f"Tool '{request.tool_id}' can write memory (not allowed)",
            )

        # 5. Tool must not delegate
        if reg.can_delegate:
            return ToolPermission(
                tool_id=request.tool_id,
                request_id=request.request_id,
                card_id=snapshot.card_id,
                session_id=snapshot.session_id,
                allowed=False,
                reason=f"Tool '{request.tool_id}' can delegate (not allowed)",
            )

        # 6. Input must not contain environment variables, file paths, network URLs
        input_str = str(request.input).lower()
        blocked_patterns = ["env", "file://", "http://", "https://", "os.", "subprocess", "import"]
        for pattern in blocked_patterns:
            if pattern in input_str:
                return ToolPermission(
                    tool_id=request.tool_id,
                    request_id=request.request_id,
                    card_id=snapshot.card_id,
                    session_id=snapshot.session_id,
                    allowed=False,
                    reason=f"Tool input contains blocked pattern: '{pattern}'",
                )

        # All checks passed
        return ToolPermission(
            permission_id=f"perm_{request.request_id}",
            tool_id=request.tool_id,
            request_id=request.request_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            allowed=True,
            reason="All permission checks passed",
            constraints=[
                f"scope: card={snapshot.card_id}, session={snapshot.session_id}",
                f"side_effect_free: True",
                f"timeout_ms: {reg.default_timeout_ms}",
            ],
        )
