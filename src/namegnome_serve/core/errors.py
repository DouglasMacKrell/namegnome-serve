"""Custom exceptions for NameGnome Serve.

This module defines typed exceptions used throughout the application for
error handling and API responses.
"""

from typing import Any


class NameGnomeError(Exception):
    """Base exception for all NameGnome Serve errors.

    All custom exceptions should inherit from this base class to allow
    for broad exception handling when needed.
    """

    pass


class DisambiguationRequired(NameGnomeError):
    """Raised when multiple provider matches exist and user input is needed.

    This exception is used during the plan phase when a title matches multiple
    entities in a metadata provider and the system cannot automatically
    determine which one is correct.

    Attributes:
        field: The field that requires disambiguation (e.g., 'title', 'series')
        candidates: List of candidate entities that match
        suggested_id: Optional ID of the suggested/most likely match
        disambiguation_token: Optional token for resuming the operation
    """

    def __init__(
        self,
        field: str,
        candidates: list[dict[str, Any]],
        suggested_id: str | None = None,
        disambiguation_token: str | None = None,
    ) -> None:
        """Initialize DisambiguationRequired exception.

        Args:
            field: Field requiring disambiguation
            candidates: List of matching candidates
            suggested_id: Suggested match ID (optional)
            disambiguation_token: Token for resuming operation (optional)
        """
        self.field = field
        self.candidates = candidates
        self.suggested_id = suggested_id
        self.disambiguation_token = disambiguation_token

        message = f"Disambiguation required for field '{field}': "
        message += f"{len(candidates)} candidates found"
        if suggested_id:
            message += f" (suggested: {suggested_id})"
        if disambiguation_token:
            message += f" [token: {disambiguation_token}]"

        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses.

        Returns:
            Dictionary representation suitable for JSON responses
        """
        result: dict[str, Any] = {
            "status": "disambiguation_required",
            "field": self.field,
            "candidates": self.candidates,
        }

        if self.suggested_id is not None:
            result["suggested_id"] = self.suggested_id

        if self.disambiguation_token is not None:
            result["disambiguation_token"] = self.disambiguation_token

        return result

    def __repr__(self) -> str:
        """Return repr string for debugging."""
        return (
            f"DisambiguationRequired(field={self.field!r}, "
            f"candidates={len(self.candidates)}, "
            f"suggested_id={self.suggested_id!r})"
        )


class ProviderUnavailable(NameGnomeError):
    """Raised when a metadata provider is unavailable or rate-limited.

    This exception is used when external metadata providers (TMDB, TVDB, etc.)
    return errors, are rate-limited, or are otherwise unavailable.

    Attributes:
        provider: The provider that is unavailable (e.g., 'tmdb', 'tvdb')
        reason: Human-readable reason for the unavailability
        retry_after: Optional seconds to wait before retrying
    """

    def __init__(
        self,
        provider: str,
        reason: str,
        retry_after: int | None = None,
    ) -> None:
        """Initialize ProviderUnavailable exception.

        Args:
            provider: Provider identifier
            reason: Reason for unavailability
            retry_after: Seconds to wait before retry (optional)
        """
        self.provider = provider
        self.reason = reason
        self.retry_after = retry_after

        message = f"Provider '{provider}' unavailable: {reason}"
        if retry_after is not None:
            message += f" (retry after {retry_after}s)"

        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses.

        Returns:
            Dictionary representation suitable for JSON responses
        """
        result: dict[str, Any] = {
            "error": "provider_unavailable",
            "provider": self.provider,
            "reason": self.reason,
        }

        if self.retry_after is not None:
            result["retry_after"] = self.retry_after

        return result

    def __repr__(self) -> str:
        """Return repr string for debugging."""
        return (
            f"ProviderUnavailable(provider={self.provider!r}, "
            f"reason={self.reason!r}, "
            f"retry_after={self.retry_after})"
        )
