"""Deterministic mapper for mapping scan fields to provider entities."""

from pathlib import Path
from typing import Any

from namegnome_serve.metadata.providers import (
    MusicBrainzProvider,
    TheAudioDBProvider,
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
        omdb: Any | None = None,
        theaudiodb: TheAudioDBProvider | None = None,
    ):
        """Initialize mapper with provider clients and fallback providers."""
        self.tmdb = tmdb or TMDBProvider()
        self.tvdb = tvdb or TVDBProvider()
        self.musicbrainz = musicbrainz or MusicBrainzProvider()
        self.omdb = omdb
        self.theaudiodb = theaudiodb or TheAudioDBProvider()

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
        """Map TV show to TVDB entity with OMDb fallback."""
        if not media_file.parsed_title:
            return None

        warnings: list[str] = []

        # Try TVDB first
        try:
            search_results = await self.tvdb.search_series(media_file.parsed_title)

            if search_results and len(search_results) == 1:
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
                dst_path = self._build_tv_path(
                    show_name,
                    media_file.parsed_season,
                    media_file.parsed_episode,
                    episode_title,
                )

                return PlanItem(
                    src_path=media_file.path,
                    dst_path=dst_path,
                    reason=f"Matched TV show '{show_name}' with TVDB",
                    confidence=1.0,  # High confidence for exact matches
                    sources=[SourceRef(provider="tvdb", id=series_id)],
                    warnings=warnings,
                )
        except Exception as e:
            warnings.append(f"TVDB failed: {str(e)}")

        # TMDB doesn't have TV show methods, skip to OMDb

        # Try OMDb fallback if available
        if self.omdb:
            try:
                search_results = await self.omdb.search_series(
                    media_file.parsed_title, limit=5
                )

                if search_results and len(search_results) == 1:
                    series = search_results[0]
                    series_id = series["id"]

                    # Get episode details
                    episode_title = None
                    if media_file.parsed_season and media_file.parsed_episode:
                        try:
                            episode_info = await self.omdb.get_episode(
                                series_id,
                                media_file.parsed_season,
                                media_file.parsed_episode,
                            )
                            if episode_info:
                                episode_title = episode_info.get("Title")
                        except Exception as exc:
                            warnings.append(f"OMDb episode lookup failed: {exc}")

                    show_name = series["title"]
                    dst_path = self._build_tv_path(
                        show_name,
                        media_file.parsed_season,
                        media_file.parsed_episode,
                        episode_title,
                    )

                    return PlanItem(
                        src_path=media_file.path,
                        dst_path=dst_path,
                        reason=f"Matched TV show '{show_name}' with OMDb (fallback)",
                        confidence=0.7,  # Lower confidence for OMDb fallback
                        sources=[SourceRef(provider="omdb", id=series_id)],
                        warnings=warnings,
                    )
            except Exception as e:
                warnings.append(f"OMDb fallback failed: {str(e)}")

        return None

    async def _map_movie(self, media_file: MediaFile) -> PlanItem | None:
        """Map movie to TMDB entity with OMDb fallback."""
        if not media_file.parsed_title:
            return None

        warnings: list[str] = []

        # Try TMDB first
        try:
            search_results = await self.tmdb.search_movie(
                media_file.parsed_title, year=media_file.parsed_year
            )

            if search_results and len(search_results) == 1:
                movie = search_results[0]
                movie_id = movie["id"]

                # Get detailed movie information
                movie_details = await self.tmdb.get_movie_details(movie_id)
                if movie_details:
                    movie_title = movie_details["title"]
                    movie_year = media_file.parsed_year or "Unknown"
                    dst_path = self._build_movie_path(movie_title, movie_year)

                    return PlanItem(
                        src_path=media_file.path,
                        dst_path=dst_path,
                        reason=f"Matched movie '{movie_title}' with TMDB",
                        confidence=1.0,  # High confidence for exact matches
                        sources=[SourceRef(provider="tmdb", id=str(movie_id))],
                        warnings=warnings,
                    )
        except Exception as e:
            warnings.append(f"TMDB failed: {str(e)}")

        # TVDB doesn't have movie methods, skip to OMDb

        # Try OMDb fallback if available
        if self.omdb:
            try:
                search_results = await self.omdb.search_movie(media_file.parsed_title)

                if search_results and len(search_results) == 1:
                    movie = search_results[0]
                    movie_id = movie["id"]

                    # Get movie details
                    movie_details = await self.omdb.get_movie_details(movie_id)
                    if movie_details:
                        movie_title = movie_details["title"]
                        movie_year = media_file.parsed_year or "Unknown"
                        dst_path = self._build_movie_path(movie_title, movie_year)

                    return PlanItem(
                        src_path=media_file.path,
                        dst_path=dst_path,
                        reason=(f"Matched movie '{movie_title}' with OMDb (fallback)"),
                        confidence=0.7,  # Lower confidence for OMDb fallback
                        sources=[SourceRef(provider="omdb", id=str(movie_id))],
                        warnings=warnings,
                    )
            except Exception as e:
                warnings.append(f"OMDb fallback failed: {str(e)}")

        return None

    async def _map_music(self, media_file: MediaFile) -> PlanItem | None:
        """Map music to MusicBrainz entity with Last.fm fallback."""
        if not media_file.parsed_title or not media_file.parsed_artist:
            return None

        warnings: list[str] = []

        # Try MusicBrainz first
        try:
            # Search for recording by title and artist
            query = f"{media_file.parsed_title} AND artist:{media_file.parsed_artist}"
            search_results = await self.musicbrainz.search_recording(query)

            if search_results and len(search_results) == 1:
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
                track_number = media_file.parsed_track or 1

                dst_path = self._build_music_path(
                    artist_name, album_title, track_number, track_title
                )

                return PlanItem(
                    src_path=media_file.path,
                    dst_path=dst_path,
                    reason=(
                        f"Matched music '{track_title}' by '{artist_name}' with"
                        " MusicBrainz"
                    ),
                    confidence=1.0,  # High confidence for exact matches
                    sources=[SourceRef(provider="musicbrainz", id=recording_id)],
                    warnings=warnings,
                )
        except Exception as e:
            warnings.append(f"MusicBrainz failed: {str(e)}")

        # Try TheAudioDB fallback for music
        try:
            # Search for track by title and artist
            search_results = await self.theaudiodb.search_track(
                media_file.parsed_title, media_file.parsed_artist
            )

            if search_results and len(search_results) == 1:
                track = search_results[0]
                track_id = track["idTrack"]

                # Get detailed track information
                track_details = await self.theaudiodb.get_track_details(track_id)
                if track_details:
                    # Build destination path
                    artist_name = media_file.parsed_artist
                    track_title = media_file.parsed_title
                    album_title = media_file.parsed_album or "Unknown Album"
                    track_number = media_file.parsed_track or 1

                    dst_path = self._build_music_path(
                        artist_name, album_title, track_number, track_title
                    )

                    return PlanItem(
                        src_path=media_file.path,
                        dst_path=dst_path,
                        reason=(
                            f"Matched music '{track_title}' by '{artist_name}' with"
                            " TheAudioDB (fallback)"
                        ),
                        confidence=0.8,  # Lower confidence for fallback
                        sources=[SourceRef(provider="theaudiodb", id=track_id)],
                        warnings=warnings,
                    )
        except Exception as e:
            warnings.append(f"TheAudioDB fallback failed: {str(e)}")

        return None

    @staticmethod
    def _build_tv_path(
        show_name: str,
        season: int | None,
        episode_start: int | None,
        episode_title: str | None,
        episode_end: int | None = None,
    ) -> Path:
        season_value = season or 1
        start_value = episode_start or 1
        end_value = episode_end or start_value
        season_num = f"{season_value:02d}"
        start_num = f"{start_value:02d}"
        end_num = f"{end_value:02d}"
        season_dir = Path("/tv") / show_name / f"Season {season_num}"
        code = f"S{season_num}E{start_num}"
        if end_value != start_value:
            code = f"{code}-E{end_num}"
        if episode_title:
            filename = f"{show_name} - {code} - {episode_title}.mkv"
        else:
            filename = f"{show_name} - {code}.mkv"
        return season_dir / filename

    @staticmethod
    def _build_movie_path(title: str, year: str | int) -> Path:
        year_label = str(year)
        movie_dir = Path("/movies") / f"{title} ({year_label})"
        filename = f"{title} ({year_label}).mkv"
        return movie_dir / filename

    @staticmethod
    def _build_music_path(
        artist: str, album: str, track_number: int, track_title: str
    ) -> Path:
        track_label = f"{track_number:02d}"
        base_dir = Path("/music") / artist / album
        filename = f"{track_label} - {track_title}.flac"
        return base_dir / filename
