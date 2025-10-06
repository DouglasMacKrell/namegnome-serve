"""Core constants for NameGnome Serve.

This module defines constants used throughout the application:
- Media file extensions for TV shows, movies, and music
- Supported metadata providers
- Configuration values for caching and retries
"""

# ============================================================================
# Media File Extensions
# ============================================================================

#: Video file extensions for TV shows
TV_EXTENSIONS: tuple[str, ...] = (
    ".mkv",
    ".mp4",
    ".avi",
    ".m4v",
    ".ts",
    ".mpg",
    ".mpeg",
    ".wmv",
    ".flv",
    ".webm",
)

#: Video file extensions for movies (includes additional formats like .iso)
MOVIE_EXTENSIONS: tuple[str, ...] = (
    ".mkv",
    ".mp4",
    ".avi",
    ".m4v",
    ".iso",
    ".img",
    ".mpg",
    ".mpeg",
    ".wmv",
    ".flv",
    ".webm",
    ".ts",
)

#: Audio file extensions for music
MUSIC_EXTENSIONS: tuple[str, ...] = (
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
    ".ape",
    ".alac",
)

#: All media extensions combined
ALL_MEDIA_EXTENSIONS: set[str] = (
    set(TV_EXTENSIONS) | set(MOVIE_EXTENSIONS) | set(MUSIC_EXTENSIONS)
)

# ============================================================================
# Media Types
# ============================================================================

#: Valid media type identifiers
MEDIA_TYPES: tuple[str, ...] = ("tv", "movie", "music")

# ============================================================================
# Metadata Providers
# ============================================================================

#: Supported metadata provider identifiers
SUPPORTED_PROVIDERS: tuple[str, ...] = (
    "tmdb",
    "tvdb",
    "musicbrainz",
    "anilist",
    "omdb",
)

#: Display names for metadata providers
PROVIDER_NAMES: dict[str, str] = {
    "tmdb": "The Movie Database",
    "tvdb": "TheTVDB",
    "musicbrainz": "MusicBrainz",
    "anilist": "AniList",
    "omdb": "OMDb",
}

# ============================================================================
# Cache Configuration
# ============================================================================

#: Default cache TTL in seconds (12 hours)
DEFAULT_CACHE_TTL: int = 43200

#: Cache TTL for different entity types (in seconds)
CACHE_TTL_BY_TYPE: dict[str, int] = {
    "series": 86400,  # 24 hours
    "episode": 43200,  # 12 hours
    "movie": 86400,  # 24 hours
    "album": 43200,  # 12 hours
    "track": 43200,  # 12 hours
}

# ============================================================================
# Provider Configuration
# ============================================================================

#: Maximum number of retry attempts for provider API calls
MAX_PROVIDER_RETRIES: int = 3

#: Timeout for provider API calls in seconds
PROVIDER_TIMEOUT: int = 30

#: Backoff multiplier for exponential backoff (seconds)
PROVIDER_BACKOFF_MULTIPLIER: float = 0.5

#: Maximum backoff time in seconds
PROVIDER_MAX_BACKOFF: int = 60

# ============================================================================
# API Configuration
# ============================================================================

#: Default confidence threshold for auto-apply (0.0 to 1.0)
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.75

#: Confidence threshold for medium confidence (manual review suggested)
MEDIUM_CONFIDENCE_THRESHOLD: float = 0.40

#: Maximum number of disambiguation candidates to return
MAX_DISAMBIGUATION_CANDIDATES: int = 10
