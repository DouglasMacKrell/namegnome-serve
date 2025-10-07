"""Tests for core custom exceptions.

Tests for typed exceptions used throughout the application for
disambiguation, provider failures, and other error conditions.
"""


def test_errors_import() -> None:
    """Test that errors module can be imported."""
    from namegnome_serve.core import errors

    assert errors is not None


def test_disambiguation_required_basic() -> None:
    """Test basic DisambiguationRequired exception."""
    from namegnome_serve.core.errors import DisambiguationRequired

    exc = DisambiguationRequired(
        field="title",
        candidates=[
            {"id": "123", "name": "Show (2015)", "year": 2015},
            {"id": "456", "name": "Show (2020)", "year": 2020},
        ],
        suggested_id="123",
    )

    assert exc.field == "title"
    assert len(exc.candidates) == 2
    assert exc.suggested_id == "123"
    assert "title" in str(exc)


def test_disambiguation_required_with_token() -> None:
    """Test DisambiguationRequired with disambiguation token."""
    from namegnome_serve.core.errors import DisambiguationRequired

    exc = DisambiguationRequired(
        field="series",
        candidates=[
            {"id": "789", "name": "Movie A"},
            {"id": "012", "name": "Movie B"},
        ],
        suggested_id="789",
        disambiguation_token="disambig_20231006_123456",
    )

    assert exc.disambiguation_token == "disambig_20231006_123456"
    assert "disambig_20231006_123456" in str(exc)


def test_disambiguation_required_no_suggestion() -> None:
    """Test DisambiguationRequired without suggested ID."""
    from namegnome_serve.core.errors import DisambiguationRequired

    exc = DisambiguationRequired(
        field="artist",
        candidates=[
            {"id": "111", "name": "Artist One"},
            {"id": "222", "name": "Artist Two"},
        ],
    )

    assert exc.suggested_id is None
    assert len(exc.candidates) == 2


def test_disambiguation_to_dict() -> None:
    """Test DisambiguationRequired to_dict method for API responses."""
    from namegnome_serve.core.errors import DisambiguationRequired

    exc = DisambiguationRequired(
        field="movie",
        candidates=[{"id": "333", "title": "Movie Title"}],
        suggested_id="333",
    )

    data = exc.to_dict()
    assert data["status"] == "disambiguation_required"
    assert data["field"] == "movie"
    assert data["candidates"] == [{"id": "333", "title": "Movie Title"}]
    assert data["suggested_id"] == "333"


def test_provider_unavailable_basic() -> None:
    """Test basic ProviderUnavailable exception."""
    from namegnome_serve.core.errors import ProviderUnavailable

    exc = ProviderUnavailable(
        provider="tmdb",
        reason="API rate limit exceeded",
    )

    assert exc.provider == "tmdb"
    assert exc.reason == "API rate limit exceeded"
    assert "tmdb" in str(exc)
    assert "rate limit" in str(exc)


def test_provider_unavailable_with_retry_after() -> None:
    """Test ProviderUnavailable with retry_after timestamp."""
    from namegnome_serve.core.errors import ProviderUnavailable

    exc = ProviderUnavailable(
        provider="tvdb",
        reason="Service temporarily unavailable",
        retry_after=3600,
    )

    assert exc.retry_after == 3600
    assert "3600" in str(exc) or "retry" in str(exc).lower()


def test_provider_unavailable_to_dict() -> None:
    """Test ProviderUnavailable to_dict method for API responses."""
    from namegnome_serve.core.errors import ProviderUnavailable

    exc = ProviderUnavailable(
        provider="musicbrainz",
        reason="Network timeout",
        retry_after=60,
    )

    data = exc.to_dict()
    assert data["error"] == "provider_unavailable"
    assert data["provider"] == "musicbrainz"
    assert data["reason"] == "Network timeout"
    assert data["retry_after"] == 60


def test_base_namegnome_error() -> None:
    """Test that custom exceptions inherit from base NameGnomeError."""
    from namegnome_serve.core.errors import (
        DisambiguationRequired,
        NameGnomeError,
        ProviderUnavailable,
    )

    # Both should inherit from base error
    assert issubclass(DisambiguationRequired, NameGnomeError)
    assert issubclass(ProviderUnavailable, NameGnomeError)

    # Base error should inherit from Exception
    assert issubclass(NameGnomeError, Exception)


def test_exceptions_are_instantiable() -> None:
    """Test that exceptions can be raised and caught."""
    from namegnome_serve.core.errors import (
        DisambiguationRequired,
        NameGnomeError,
        ProviderUnavailable,
    )

    # Test DisambiguationRequired
    try:
        raise DisambiguationRequired(
            field="test", candidates=[{"id": "1"}], suggested_id="1"
        )
    except NameGnomeError as e:
        assert isinstance(e, DisambiguationRequired)

    # Test ProviderUnavailable
    try:
        raise ProviderUnavailable(provider="test", reason="testing")
    except NameGnomeError as e:
        assert isinstance(e, ProviderUnavailable)


def test_error_repr() -> None:
    """Test that errors have useful repr strings."""
    from namegnome_serve.core.errors import ProviderUnavailable

    exc = ProviderUnavailable(provider="tmdb", reason="Test")
    repr_str = repr(exc)

    assert "ProviderUnavailable" in repr_str
    assert "tmdb" in repr_str
