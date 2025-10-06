"""Deterministic mapper for mapping scan fields to provider entities."""

from namegnome_serve.metadata.providers import (
    MusicBrainzProvider,
    TMDBProvider,
    TVDBProvider,
)
from namegnome_serve.routes.schemas import MediaFile, PlanItem


class DeterministicMapper:
    """Maps scan fields to provider entities without LLM when possible.

    This mapper handles:
    - Exact title + year matches for movies/TV
    - Exact artist + track matches for music
    - Episode title resolution for TV shows
    - Album/artist resolution for music
    """

    def __init__(
        self,
        tmdb: TMDBProvider | None = None,
        tvdb: TVDBProvider | None = None,
        musicbrainz: MusicBrainzProvider | None = None,
    ):
        """Initialize mapper with provider clients."""
        self.tmdb = tmdb or TMDBProvider()
        self.tvdb = tvdb or TVDBProvider()
        self.musicbrainz = musicbrainz or MusicBrainzProvider()

    async def map_media_file(
        self, media_file: MediaFile, media_type: str
    ) -> PlanItem | None:
        """Map a media file to a provider entity.

        Args:
            media_file: The scanned media file to map
            media_type: Type of media ('tv', 'movie', or 'music')

        Returns:
            PlanItem with mapping details, or None if no match/ambiguous
        """
        if media_type == "tv":
            return await self._map_tv_show(media_file)
        elif media_type == "movie":
            return await self._map_movie(media_file)
        elif media_type == "music":
            return await self._map_music(media_file)
        else:
            return None

    async def _map_tv_show(self, media_file: MediaFile) -> PlanItem | None:
        """Map TV show to TVDB entity."""
        # TODO: Implement TV show mapping
        return None

    async def _map_movie(self, media_file: MediaFile) -> PlanItem | None:
        """Map movie to TMDB entity."""
        # TODO: Implement movie mapping
        return None

    async def _map_music(self, media_file: MediaFile) -> PlanItem | None:
        """Map music to MusicBrainz entity."""
        # TODO: Implement music mapping
        return None
