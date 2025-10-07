"""Tests for core constants module.

Tests for media file extensions, supported providers, and other
configuration constants used throughout the application.
"""


def test_constants_import() -> None:
    """Test that constants module can be imported."""
    from namegnome_serve.core import constants

    assert constants is not None


def test_tv_extensions() -> None:
    """Test that TV video extensions are defined."""
    from namegnome_serve.core.constants import TV_EXTENSIONS

    # Should contain common video formats
    assert ".mkv" in TV_EXTENSIONS
    assert ".mp4" in TV_EXTENSIONS
    assert ".avi" in TV_EXTENSIONS
    assert ".m4v" in TV_EXTENSIONS
    assert ".ts" in TV_EXTENSIONS

    # Should be lowercase for consistency
    for ext in TV_EXTENSIONS:
        assert ext.startswith(".")
        assert ext == ext.lower()


def test_movie_extensions() -> None:
    """Test that movie video extensions are defined."""
    from namegnome_serve.core.constants import MOVIE_EXTENSIONS

    # Should contain common video formats
    assert ".mkv" in MOVIE_EXTENSIONS
    assert ".mp4" in MOVIE_EXTENSIONS
    assert ".avi" in MOVIE_EXTENSIONS
    assert ".m4v" in MOVIE_EXTENSIONS
    assert ".iso" in MOVIE_EXTENSIONS

    # Should be lowercase for consistency
    for ext in MOVIE_EXTENSIONS:
        assert ext.startswith(".")
        assert ext == ext.lower()


def test_music_extensions() -> None:
    """Test that music audio extensions are defined."""
    from namegnome_serve.core.constants import MUSIC_EXTENSIONS

    # Should contain common audio formats
    assert ".mp3" in MUSIC_EXTENSIONS
    assert ".flac" in MUSIC_EXTENSIONS
    assert ".m4a" in MUSIC_EXTENSIONS
    assert ".ogg" in MUSIC_EXTENSIONS
    assert ".wav" in MUSIC_EXTENSIONS

    # Should be lowercase for consistency
    for ext in MUSIC_EXTENSIONS:
        assert ext.startswith(".")
        assert ext == ext.lower()


def test_all_media_extensions() -> None:
    """Test that ALL_MEDIA_EXTENSIONS combines all types."""
    from namegnome_serve.core.constants import (
        ALL_MEDIA_EXTENSIONS,
        MOVIE_EXTENSIONS,
        MUSIC_EXTENSIONS,
        TV_EXTENSIONS,
    )

    # Should be a set of all extensions
    assert isinstance(ALL_MEDIA_EXTENSIONS, set)

    # Should contain extensions from all categories
    assert ".mkv" in ALL_MEDIA_EXTENSIONS  # TV/Movie
    assert ".mp3" in ALL_MEDIA_EXTENSIONS  # Music
    assert ".flac" in ALL_MEDIA_EXTENSIONS  # Music

    # Should be union of all extension types
    expected_all = set(TV_EXTENSIONS) | set(MOVIE_EXTENSIONS) | set(MUSIC_EXTENSIONS)
    assert ALL_MEDIA_EXTENSIONS == expected_all


def test_supported_providers() -> None:
    """Test that supported metadata providers are defined."""
    from namegnome_serve.core.constants import SUPPORTED_PROVIDERS

    # Should contain known providers
    assert "tmdb" in SUPPORTED_PROVIDERS
    assert "tvdb" in SUPPORTED_PROVIDERS
    assert "musicbrainz" in SUPPORTED_PROVIDERS
    assert "anilist" in SUPPORTED_PROVIDERS
    assert "omdb" in SUPPORTED_PROVIDERS

    # All providers should be lowercase
    for provider in SUPPORTED_PROVIDERS:
        assert provider == provider.lower()


def test_provider_names() -> None:
    """Test that provider display names are defined."""
    from namegnome_serve.core.constants import PROVIDER_NAMES

    # Should map provider IDs to display names
    assert PROVIDER_NAMES["tmdb"] == "The Movie Database"
    assert PROVIDER_NAMES["tvdb"] == "TheTVDB"
    assert PROVIDER_NAMES["musicbrainz"] == "MusicBrainz"
    assert PROVIDER_NAMES["anilist"] == "AniList"
    assert PROVIDER_NAMES["omdb"] == "OMDb"


def test_media_types() -> None:
    """Test that valid media types are defined."""
    from namegnome_serve.core.constants import MEDIA_TYPES

    assert "tv" in MEDIA_TYPES
    assert "movie" in MEDIA_TYPES
    assert "music" in MEDIA_TYPES
    assert len(MEDIA_TYPES) == 3


def test_default_cache_ttl() -> None:
    """Test that default cache TTL is defined."""
    from namegnome_serve.core.constants import DEFAULT_CACHE_TTL

    # Should be a reasonable number of seconds (e.g., 12 hours)
    assert isinstance(DEFAULT_CACHE_TTL, int)
    assert DEFAULT_CACHE_TTL > 0
    assert DEFAULT_CACHE_TTL == 43200  # 12 hours in seconds


def test_max_provider_retries() -> None:
    """Test that max provider retries is defined."""
    from namegnome_serve.core.constants import MAX_PROVIDER_RETRIES

    assert isinstance(MAX_PROVIDER_RETRIES, int)
    assert MAX_PROVIDER_RETRIES >= 3


def test_provider_timeout() -> None:
    """Test that provider timeout is defined."""
    from namegnome_serve.core.constants import PROVIDER_TIMEOUT

    assert isinstance(PROVIDER_TIMEOUT, int)
    assert PROVIDER_TIMEOUT > 0
    assert PROVIDER_TIMEOUT <= 60  # Reasonable timeout


def test_extensions_are_frozen() -> None:
    """Test that extension collections are tuples (immutable)."""
    from namegnome_serve.core.constants import (
        MOVIE_EXTENSIONS,
        MUSIC_EXTENSIONS,
        TV_EXTENSIONS,
    )

    # Should be tuples for immutability
    assert isinstance(TV_EXTENSIONS, tuple)
    assert isinstance(MOVIE_EXTENSIONS, tuple)
    assert isinstance(MUSIC_EXTENSIONS, tuple)


def test_providers_are_frozen() -> None:
    """Test that provider collections are tuples (immutable)."""
    from namegnome_serve.core.constants import SUPPORTED_PROVIDERS

    assert isinstance(SUPPORTED_PROVIDERS, tuple)
