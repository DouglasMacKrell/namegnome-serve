"""Deterministic mapper for mapping scan fields to provider entities."""

from pathlib import Path

from namegnome_serve.metadata.providers import (
    MusicBrainzProvider,
    TMDBProvider,
    TVDBProvider,
)
from namegnome_serve.routes.schemas import (
    MediaFile,
    PlanItem,
    SourceRef,
)


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
        if not media_file.parsed_title:
            return None

        # Search for series by title
        search_results = await self.tvdb.search_series(media_file.parsed_title)

        if not search_results:
            return None

        # If multiple results, require disambiguation
        if len(search_results) > 1:
            return None

        series = search_results[0]
        series_id = series["id"]

        # Get episode details if we have season/episode info
        episode_title = None
        if media_file.parsed_season and media_file.parsed_episode:
            episodes = await self.tvdb.get_series_episodes(series_id)
            for episode in episodes:
                if (
                    episode.get("seasonNumber") == media_file.parsed_season
                    and episode.get("number") == media_file.parsed_episode
                ):
                    episode_title = episode.get("name")
                    break

        # Build destination path
        show_name = series["name"]
        season_num = (
            f"{media_file.parsed_season:02d}" if media_file.parsed_season else "01"
        )
        episode_num = (
            f"{media_file.parsed_episode:02d}" if media_file.parsed_episode else "01"
        )

        if episode_title:
            dst_path = (
                f"/tv/{show_name}/Season {season_num}/"
                f"{show_name} - S{season_num}E{episode_num} - {episode_title}.mkv"
            )
        else:
            dst_path = (
                f"/tv/{show_name}/Season {season_num}/"
                f"{show_name} - S{season_num}E{episode_num}.mkv"
            )

        return PlanItem(
            src_path=media_file.path,
            dst_path=Path(dst_path),
            reason=f"Matched TV show '{show_name}' with TVDB",
            confidence=1.0,  # High confidence for exact matches
            sources=[SourceRef(provider="tvdb", id=series_id)],
            warnings=[],
        )

    async def _map_movie(self, media_file: MediaFile) -> PlanItem | None:
        """Map movie to TMDB entity."""
        # TODO: Implement movie mapping
        return None

    async def _map_music(self, media_file: MediaFile) -> PlanItem | None:
        """Map music to MusicBrainz entity."""
        # TODO: Implement music mapping
        return None
