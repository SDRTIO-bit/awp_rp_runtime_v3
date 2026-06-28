"""ConditionEvaluator — safe condition evaluation against CardState.

Evaluates structured condition objects (NOT arbitrary expressions).
Used by ConditionWorldbookActivator to determine worldbook entry activation.

Supported operators:
  equals, notEquals, gt, gte, lt, lte,
  exists, contains, boolean, and, or, not

Absolutely forbidden:
  eval, exec, arbitrary Python expressions, arbitrary JS expressions
  model-written condition execution logic

All conditions are pure data objects parsed from worldbook entry conditions
declared in the CardDefinition at version-lock time.
"""

from __future__ import annotations

from typing import Any

# Supported operators (whitelist)
SUPPORTED_OPERATORS = frozenset({
    "equals", "notEquals",
    "gt", "gte", "lt", "lte",
    "exists", "contains",
    "boolean",
    "and", "or", "not",
})


class ConditionEvaluationError(Exception):
    """Raised when a condition is malformed or uses unsupported features."""
    pass


class ConditionEvaluator:
    """Evaluates structured condition objects against CardState.

    Input: a condition dict like:
        {"op": "equals", "path": "variables.favorability", "value": 10}
        {"op": "and", "conditions": [...]}

    Output: bool (the condition's truth value).

    The evaluator never executes code. It only reads values from a
    provided state dict using dot-separated paths.
    """

    def evaluate(
        self,
        condition: dict[str, Any],
        state_context: dict[str, Any],
    ) -> bool:
        """Evaluate a single condition against the state context.

        Args:
            condition: A structured condition object with 'op' key.
            state_context: The CardState as a dict (variables, event_flags, etc.)

        Returns:
            bool: Whether the condition is satisfied.

        Raises:
            ConditionEvaluationError: If the condition is malformed or unsupported.
        """
        if not isinstance(condition, dict):
            raise ConditionEvaluationError(
                f"Condition must be a dict, got {type(condition).__name__}"
            )

        op = condition.get("op")
        if not op or not isinstance(op, str):
            raise ConditionEvaluationError(
                f"Condition must have an 'op' string, got: {op!r}"
            )

        if op not in SUPPORTED_OPERATORS:
            raise ConditionEvaluationError(
                f"Unsupported operator '{op}'. "
                f"Supported: {sorted(SUPPORTED_OPERATORS)}"
            )

        handler = getattr(self, f"_eval_{op}", None)
        if handler is None:
            raise ConditionEvaluationError(
                f"No handler for operator '{op}'"
            )

        return handler(condition, state_context)

    # ── Value resolution ─────────────────────────────────────────────────

    def _resolve_path(
        self, path: str, state_context: dict[str, Any]
    ) -> tuple[bool, Any]:
        """Resolve a dot-separated path in the state context.

        Returns (found, value). If not found, (False, None).
        """
        if not path or not isinstance(path, str):
            return False, None

        parts = path.split(".")
        current = state_context
        for part in parts:
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    return False, None
            else:
                return False, None

        return True, current

    def _resolve_value(
        self, raw_value: Any, state_context: dict[str, Any]
    ) -> Any:
        """Resolve a value that might be a path reference.

        If the value is a dict with '_path' key, resolve it from state.
        Otherwise return as-is.
        """
        if isinstance(raw_value, dict) and "_path" in raw_value:
            _, resolved = self._resolve_path(raw_value["_path"], state_context)
            return resolved
        return raw_value

    # ── Comparison operators ─────────────────────────────────────────────

    def _eval_equals(self, condition: dict, state: dict) -> bool:
        path = condition.get("path", "")
        expected = self._resolve_value(condition.get("value"), state)
        found, actual = self._resolve_path(path, state)
        if not found:
            return False
        return actual == expected

    def _eval_notEquals(self, condition: dict, state: dict) -> bool:
        return not self._eval_equals(condition, state)

    def _eval_gt(self, condition: dict, state: dict) -> bool:
        path = condition.get("path", "")
        threshold = self._resolve_value(condition.get("value"), state)
        found, actual = self._resolve_path(path, state)
        if not found:
            return False
        if not isinstance(actual, (int, float)) or not isinstance(threshold, (int, float)):
            return False
        return actual > threshold

    def _eval_gte(self, condition: dict, state: dict) -> bool:
        path = condition.get("path", "")
        threshold = self._resolve_value(condition.get("value"), state)
        found, actual = self._resolve_path(path, state)
        if not found:
            return False
        if not isinstance(actual, (int, float)) or not isinstance(threshold, (int, float)):
            return False
        return actual >= threshold

    def _eval_lt(self, condition: dict, state: dict) -> bool:
        path = condition.get("path", "")
        threshold = self._resolve_value(condition.get("value"), state)
        found, actual = self._resolve_path(path, state)
        if not found:
            return False
        if not isinstance(actual, (int, float)) or not isinstance(threshold, (int, float)):
            return False
        return actual < threshold

    def _eval_lte(self, condition: dict, state: dict) -> bool:
        path = condition.get("path", "")
        threshold = self._resolve_value(condition.get("value"), state)
        found, actual = self._resolve_path(path, state)
        if not found:
            return False
        if not isinstance(actual, (int, float)) or not isinstance(threshold, (int, float)):
            return False
        return actual <= threshold

    # ── Existence / containment ──────────────────────────────────────────

    def _eval_exists(self, condition: dict, state: dict) -> bool:
        path = condition.get("path", "")
        found, value = self._resolve_path(path, state)
        if not found:
            return False
        return value is not None

    def _eval_contains(self, condition: dict, state: dict) -> bool:
        path = condition.get("path", "")
        expected_item = self._resolve_value(condition.get("value"), state)
        found, actual = self._resolve_path(path, state)
        if not found:
            return False
        if isinstance(actual, (list, tuple)):
            return expected_item in actual
        if isinstance(actual, str) and isinstance(expected_item, str):
            return expected_item in actual
        if isinstance(actual, dict):
            return expected_item in actual
        return False

    def _eval_boolean(self, condition: dict, state: dict) -> bool:
        """Evaluate a path as a boolean truth value."""
        path = condition.get("path", "")
        found, value = self._resolve_path(path, state)
        if not found:
            return False
        return bool(value)

    # ── Logical operators ────────────────────────────────────────────────

    def _eval_and(self, condition: dict, state: dict) -> bool:
        sub_conditions = condition.get("conditions", [])
        if not isinstance(sub_conditions, list):
            raise ConditionEvaluationError("'and' requires a 'conditions' list")
        if len(sub_conditions) == 0:
            return True  # vacuous truth
        return all(
            self.evaluate(sub, state) for sub in sub_conditions
        )

    def _eval_or(self, condition: dict, state: dict) -> bool:
        sub_conditions = condition.get("conditions", [])
        if not isinstance(sub_conditions, list):
            raise ConditionEvaluationError("'or' requires a 'conditions' list")
        if len(sub_conditions) == 0:
            return False
        return any(
            self.evaluate(sub, state) for sub in sub_conditions
        )

    def _eval_not(self, condition: dict, state: dict) -> bool:
        sub_condition = condition.get("condition")
        if not isinstance(sub_condition, dict):
            raise ConditionEvaluationError("'not' requires a 'condition' dict")
        return not self.evaluate(sub_condition, state)
