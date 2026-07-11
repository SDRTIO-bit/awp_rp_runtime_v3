"""Tests for RetryPolicy."""

import pytest
from awp_rp_runtime_v3.policies.retry_policy import RetryPolicy


class TestRetryPolicy:
    """Test RetryPolicy validation rules."""

    def setup_method(self):
        self.policy = RetryPolicy()

    def test_can_retry_first_time(self):
        result = self.policy.can_retry(0)
        assert result.valid

    def test_can_retry_within_limit(self):
        result = self.policy.can_retry(2)
        assert result.valid

    def test_cannot_retry_exceeded(self):
        result = self.policy.can_retry(3)
        assert not result.valid

    def test_continue_valid(self):
        result = self.policy.validate_continue("turn_1", "turn_1")
        assert result.valid

    def test_continue_no_previous(self):
        result = self.policy.validate_continue(None, None)
        assert not result.valid

    def test_continue_wrong_turn(self):
        result = self.policy.validate_continue("turn_1", "turn_2")
        assert not result.valid
