"""Base provider interface with security, rate limiting, and retry logic.

SECURITY REQUIREMENTS:
- API keys MUST come from environment variables only
- API keys MUST NEVER be hardcoded
- API keys MUST NEVER appear in logs or error messages
- Rate limits MUST be enforced to prevent API bans
- Retry logic with exponential backoff for resilience
"""

import os
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from typing import Any, TypeVar

import anyio
import httpx

from namegnome_serve.core.errors import NameGnomeError

T = TypeVar("T")


class ProviderError(NameGnomeError):
    """Base error for provider-related failures."""

    pass


class RateLimitError(ProviderError):
    """Raised when rate limit is exceeded."""

    pass


class ProviderUnavailableError(ProviderError):
    """Raised when provider API is unavailable."""

    pass


class BaseProvider(ABC):
    """Base class for metadata providers with security and resilience.

    Features:
    - Environment-only API key loading (never hardcoded)
    - Rate limiting per provider
    - Exponential backoff retry logic
    - Secure error handling (keys never exposed)
    """

    def __init__(
        self,
        provider_name: str,
        api_key_env_var: str | None = None,
        rate_limit_per_minute: int = 40,
        max_retries: int = 3,
    ):
        """Initialize provider with secure configuration.

        Args:
            provider_name: Name of the provider (for logging)
            api_key_env_var: Environment variable name containing API key
            rate_limit_per_minute: Max requests per minute (conservative)
            max_retries: Maximum retry attempts for failed requests

        Raises:
            ValueError: If API key required but not found in environment
        """
        self.provider_name = provider_name
        self.rate_limit_per_minute = rate_limit_per_minute
        self.max_retries = max_retries

        # Load API key from environment ONLY - never hardcode!
        self._api_key_env_var = api_key_env_var
        if api_key_env_var:
            self._api_key = os.getenv(api_key_env_var)
            if not self._api_key:
                raise ValueError(
                    f"{provider_name} API key not found in environment variable "
                    f"'{api_key_env_var}'. Please set it in your .env file."
                )
        else:
            self._api_key = None

        # Rate limiting: track request timestamps
        self._request_times: deque[float] = deque()

    def __str__(self) -> str:
        """String representation with API key MASKED for security."""
        if self._api_key_env_var:
            return f"{self.provider_name}Provider(api_key={self._api_key_env_var}=***)"
        return f"{self.provider_name}Provider(no_auth_required)"

    def __repr__(self) -> str:
        """Repr with API key MASKED for security."""
        return self.__str__()

    def check_rate_limit(self) -> bool:
        """Check if we're within rate limit, update tracking.

        Returns:
            True if request allowed, False if rate limited

        Raises:
            RateLimitError: If rate limit would be exceeded
        """
        now = time.time()
        minute_ago = now - 60

        # Remove timestamps older than 1 minute
        while self._request_times and self._request_times[0] < minute_ago:
            self._request_times.popleft()

        # Check if we're at limit
        if len(self._request_times) >= self.rate_limit_per_minute:
            return False

        # Record this request
        self._request_times.append(now)
        return True

    def calculate_backoff_delay(self, attempt: int, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff delay for retry attempt.

        Args:
            attempt: Retry attempt number (1-indexed)
            base_delay: Base delay in seconds (default 1.0)

        Returns:
            Delay in seconds (exponential: 1s, 2s, 4s, 8s...)
        """
        # Exponential backoff: 2^(attempt-1) * base_delay
        # Cap at 60 seconds max
        delay: float = min(base_delay * (2 ** (attempt - 1)), 60.0)
        return delay

    async def _execute_with_retry(
        self, func: Callable[[], Any], operation_name: str = "request"
    ) -> T:
        """Execute an async function with automatic retry on transient errors.

        Retries on:
        - 429 Too Many Requests (rate limit)
        - 500, 502, 503, 504 (server errors)
        - Network timeouts

        Does NOT retry on:
        - 4xx errors (except 429) - these are client errors

        Args:
            func: Async function to execute
            operation_name: Name of operation for error messages

        Returns:
            Result from func()

        Raises:
            ProviderError: After max retries exceeded or non-retriable error
        """
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                result: T = await func()
                return result

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                last_error = e

                # Determine if we should retry
                should_retry = status_code in (429, 500, 502, 503, 504)

                if not should_retry or attempt >= self.max_retries:
                    raise ProviderError(
                        f"{self.provider_name} {operation_name} failed: {e}"
                    ) from e

                # Wait with exponential backoff before retry
                delay = self.calculate_backoff_delay(attempt)
                await anyio.sleep(delay)
                continue

            except httpx.TimeoutException as e:
                last_error = e

                if attempt >= self.max_retries:
                    raise ProviderError(
                        f"{self.provider_name} {operation_name} timed out after "
                        f"{self.max_retries} attempts: {e}"
                    ) from e

                # Wait before retry
                delay = self.calculate_backoff_delay(attempt)
                await anyio.sleep(delay)
                continue

        # Should never reach here, but just in case
        raise ProviderError(
            f"{self.provider_name} {operation_name} failed after "
            f"{self.max_retries} retries"
        ) from last_error

    @property
    def api_key(self) -> str | None:
        """Get API key (for internal use only - never log this!)."""
        return self._api_key

    @abstractmethod
    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search for entities by name.

        Args:
            query: Search query string
            **kwargs: Provider-specific search parameters

        Returns:
            List of search result dictionaries

        Raises:
            ProviderError: On search failure
            RateLimitError: If rate limited
        """
        pass

    @abstractmethod
    async def get_details(self, entity_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Get detailed information for an entity.

        Args:
            entity_id: Unique entity identifier
            **kwargs: Provider-specific parameters

        Returns:
            Entity details dictionary, or None if not found

        Raises:
            ProviderError: On fetch failure
            RateLimitError: If rate limited
        """
        pass
