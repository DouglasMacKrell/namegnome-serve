"""Metadata providers for TMDB, TVDB, and MusicBrainz.

Security: All API keys must be loaded from environment variables.
Rate limiting: Each provider enforces conservative limits to prevent bans.
"""

from namegnome_serve.metadata.providers.base import (
    BaseProvider,
    ProviderError,
    ProviderUnavailableError,
    RateLimitError,
)
from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider
from namegnome_serve.metadata.providers.omdb import OMDbProvider
from namegnome_serve.metadata.providers.tmdb import TMDBProvider
from namegnome_serve.metadata.providers.tvdb import TVDBProvider

__all__ = [
    "BaseProvider",
    "ProviderError",
    "ProviderUnavailableError",
    "RateLimitError",
    "TMDBProvider",
    "TVDBProvider",
    "MusicBrainzProvider",
    "OMDbProvider",
]
