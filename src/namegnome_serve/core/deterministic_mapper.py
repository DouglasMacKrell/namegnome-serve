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
        if not media_file.parsed_title:
            return None

        # Search for movie by title and year
        search_results = await self.tmdb.search_movie(
            media_file.parsed_title, year=media_file.parsed_year
        )

        if not search_results:
            return None

        # If multiple results, require disambiguation
        if len(search_results) > 1:
            return None

        movie = search_results[0]
        movie_id = movie["id"]

        # Get detailed movie information
        movie_details = await self.tmdb.get_movie_details(movie_id)
        if not movie_details:
            return None

        # Build destination path
        movie_title = movie_details["title"]
        movie_year = media_file.parsed_year or "Unknown"
        dst_path = (
            f"/movies/{movie_title} ({movie_year})/{movie_title} ({movie_year}).mkv"
        )

        return PlanItem(
            src_path=media_file.path,
            dst_path=Path(dst_path),
            reason=f"Matched movie '{movie_title}' with TMDB",
            confidence=1.0,  # High confidence for exact matches
            sources=[SourceRef(provider="tmdb", id=str(movie_id))],
            warnings=[],
        )

    async def _map_music(self, media_file: MediaFile) -> PlanItem | None:
        """Map music to MusicBrainz entity."""
        if not media_file.parsed_title or not media_file.parsed_artist:
            return None

        # Search for recording by title and artist
        query = f"{media_file.parsed_title} AND artist:{media_file.parsed_artist}"
        search_results = await self.musicbrainz.search_recording(query)

        if not search_results:
            return None

        # If multiple results, require disambiguation
        if len(search_results) > 1:
            return None

        recording = search_results[0]
        recording_id = recording["id"]

        # Get release group information if available
        if recording.get("releases"):
            release_id = recording["releases"][0]["id"]
            await self.musicbrainz.get_release_group(release_id)

        # Build destination path
        artist_name = media_file.parsed_artist
        track_title = media_file.parsed_title
        album_title = media_file.parsed_album or "Unknown Album"
        track_num = (
            f"{media_file.parsed_track:02d}" if media_file.parsed_track else "01"
        )

        dst_path = (
            f"/music/{artist_name}/{album_title}/{track_num} - {track_title}.flac"
        )

        return PlanItem(
            src_path=media_file.path,
            dst_path=Path(dst_path),
            reason=f"Matched music '{track_title}' by '{artist_name}' with MusicBrainz",
            confidence=1.0,  # High confidence for exact matches
            sources=[SourceRef(provider="musicbrainz", id=recording_id)],
            warnings=[],
        )
