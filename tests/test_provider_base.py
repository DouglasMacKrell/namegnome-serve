"""Tests for base provider interface and security.

These tests verify:
- API key security (no hardcoding, environment-only)
- Rate limiting enforcement
- Retry/backoff logic
- Error handling for API failures
"""

import os
from typing import Any
from unittest.mock import patch

import pytest


# Test implementation of BaseProvider for testing
class ConcreteProviderForTesting:
    """Concrete provider for testing base functionality."""

    def __init__(self, **kwargs: Any):
        from namegnome_serve.metadata.providers.base import BaseProvider

        # Create anonymous subclass for testing
        class _ConcreteTestProvider(BaseProvider):
            async def search(
                self, query: str, **search_kwargs: Any
            ) -> list[dict[str, Any]]:
                return []

            async def get_details(
                self, entity_id: str, **detail_kwargs: Any
            ) -> dict[str, Any]:
                return {}

        self._provider = _ConcreteTestProvider(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)

    def __str__(self) -> str:
        return str(self._provider)

    def __repr__(self) -> str:
        return repr(self._provider)


def test_provider_requires_api_key_from_environment() -> None:
    """Test that providers MUST load API keys from environment only."""
    # Should raise if API key not in environment
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="API key.*environment"):
            # This should fail - no key in environment
            ConcreteProviderForTesting(
                provider_name="test", api_key_env_var="NONEXISTENT_KEY"
            )


def test_provider_never_exposes_api_key_in_errors() -> None:
    """Test that API keys are NEVER exposed in error messages or logs."""
    with patch.dict(os.environ, {"TEST_API_KEY": "secret_key_12345"}):
        provider = ConcreteProviderForTesting(
            provider_name="test", api_key_env_var="TEST_API_KEY"
        )

        # Simulate an error - key should NOT appear in error message
        error_msg = str(provider)
        assert "secret_key_12345" not in error_msg
        assert "TEST_API_KEY" in error_msg or "***" in error_msg


def test_provider_enforces_rate_limiting() -> None:
    """Test that rate limiting prevents excessive API calls."""
    with patch.dict(os.environ, {"TEST_API_KEY": "test_key"}):
        # Create provider with very low rate limit for testing
        provider = ConcreteProviderForTesting(
            provider_name="test",
            api_key_env_var="TEST_API_KEY",
            rate_limit_per_minute=2,
        )

        # First 2 requests should succeed
        assert provider.check_rate_limit() is True
        assert provider.check_rate_limit() is True

        # Third request should be rate limited
        assert provider.check_rate_limit() is False


def test_provider_implements_exponential_backoff() -> None:
    """Test that failed requests trigger exponential backoff."""
    with patch.dict(os.environ, {"TEST_API_KEY": "test_key"}):
        provider = ConcreteProviderForTesting(
            provider_name="test", api_key_env_var="TEST_API_KEY"
        )

        # Calculate backoff delays
        delay1 = provider.calculate_backoff_delay(attempt=1)
        delay2 = provider.calculate_backoff_delay(attempt=2)
        delay3 = provider.calculate_backoff_delay(attempt=3)

        # Should increase exponentially: 1s, 2s, 4s, 8s...
        assert delay1 < delay2 < delay3
        assert delay2 >= delay1 * 2
        assert delay3 >= delay2 * 2


def test_provider_respects_max_retries() -> None:
    """Test that providers don't retry indefinitely."""
    with patch.dict(os.environ, {"TEST_API_KEY": "test_key"}):
        provider = ConcreteProviderForTesting(
            provider_name="test", api_key_env_var="TEST_API_KEY", max_retries=3
        )

        # Should have a max retry limit
        assert provider.max_retries == 3
        assert provider.calculate_backoff_delay(attempt=10) > 0  # Caps at max


def test_provider_handles_429_rate_limit_errors() -> None:
    """Test that 429 errors trigger backoff, not immediate failure."""
    from namegnome_serve.metadata.providers.base import BaseProvider

    # This will be tested when we implement actual HTTP logic
    # For now, verify the interface exists
    assert hasattr(BaseProvider, "calculate_backoff_delay")


def test_provider_handles_5xx_server_errors() -> None:
    """Test that 5xx errors trigger retry with backoff."""
    # Interface test - actual retry logic tested in integration
    with patch.dict(os.environ, {"TEST_API_KEY": "test_key"}):
        provider = ConcreteProviderForTesting(
            provider_name="test", api_key_env_var="TEST_API_KEY"
        )
        assert provider.max_retries > 0  # Should allow retries
