"""Deterministic mapper for mapping scan fields to provider entities."""

from pathlib import Path
from typing import Any

from namegnome_serve.core.anthology import interval_simplify
from namegnome_serve.metadata.providers import (
    MusicBrainzProvider,
    TheAudioDBProvider,
    TMDBProvider,
    TVDBProvider,
    TVMazeProvider,
)
from namegnome_serve.routes.schemas import (
    EpisodeSegment,
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
        tvmaze: TVMazeProvider | None = None,
    ):
        """Initialize mapper with provider clients and fallback providers."""
        self.tmdb = tmdb or TMDBProvider()
        self.tvdb = tvdb or TVDBProvider()
        self.musicbrainz = musicbrainz or MusicBrainzProvider()
        self.omdb = omdb
        self.theaudiodb = theaudiodb or TheAudioDBProvider()
        self.tvmaze = tvmaze or TVMazeProvider()

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
        if media_type == "movie":
            return await self._map_movie(media_file)
        if media_type == "music":
            return await self._map_music(media_file)
        return None

    @staticmethod
    def _extract_year(value: Any) -> int | None:
        """Extract four-digit year from provider payload."""

        if value is None:
            return None

        if isinstance(value, int):
            return value

        text = str(value)
        for token in text.split("-"):
            if token.isdigit() and len(token) == 4:
                return int(token)
        return None

    async def _map_tv_show(self, media_file: MediaFile) -> PlanItem | None:
        """Map TV show using TVDB primary and TMDB→OMDb→TVMaze fallbacks."""
        if not media_file.parsed_title:
            return None

        warnings: list[str] = []

        # Try TVDB first
        try:
            search_results = await self.tvdb.search_series(media_file.parsed_title)

            if search_results:
                if len(search_results) > 1:
                    warnings.append(
                        "TVDB returned multiple matches; requires disambiguation."
                    )
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
                    sources=[SourceRef(provider="tvdb", id=str(series_id))],
                    warnings=warnings,
                )
        except Exception as e:
            warnings.append(f"TVDB failed: {str(e)}")

        # TMDB fallback
        try:
            search_results = await self.tmdb.search_tv(
                media_file.parsed_title, year=media_file.parsed_year
            )

            if search_results and len(search_results) == 1:
                series = search_results[0]
                series_id = series["id"]
                show_name_raw = series.get("name") or series.get("original_name")
                show_name = str(
                    show_name_raw or media_file.parsed_title or "Unknown Series"
                )

                episode_title = None
                if media_file.parsed_season and media_file.parsed_episode:
                    try:
                        episodes = await self.tmdb.get_tv_episodes(
                            series_id, season=media_file.parsed_season
                        )
                        for episode in episodes:
                            if (
                                episode.get("episode_number")
                                == media_file.parsed_episode
                            ):
                                episode_title = episode.get("name")
                                break
                    except Exception as exc:
                        warnings.append(f"TMDB episode lookup failed: {exc}")

                dst_path = self._build_tv_path(
                    show_name,
                    media_file.parsed_season,
                    media_file.parsed_episode,
                    episode_title,
                )

                return PlanItem(
                    src_path=media_file.path,
                    dst_path=dst_path,
                    reason=f"Matched TV show '{show_name}' with TMDB (fallback)",
                    confidence=0.85,
                    sources=[SourceRef(provider="tmdb", id=str(series_id))],
                    warnings=warnings,
                )
        except Exception as e:
            warnings.append(f"TMDB fallback failed: {str(e)}")

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

                    show_name = str(
                        series.get("title")
                        or media_file.parsed_title
                        or "Unknown Series"
                    )
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

        # Final fallback: TVMaze (free, no auth)
        try:
            search_results = await self.tvmaze.search_series(media_file.parsed_title)

            if search_results:
                preferred = None
                if media_file.parsed_year:
                    for candidate in search_results:
                        candidate_year = self._extract_year(
                            candidate.get("premiered") or candidate.get("ended")
                        )
                        if candidate_year == media_file.parsed_year:
                            preferred = candidate
                            break
                preferred = preferred or search_results[0]

                series_id = preferred.get("id")
                if series_id is not None:
                    episode_title = None
                    if media_file.parsed_season and media_file.parsed_episode:
                        try:
                            episode_data = await self.tvmaze.get_episode(
                                series_id,
                                media_file.parsed_season,
                                media_file.parsed_episode,
                            )
                            if episode_data:
                                episode_title = episode_data.get("name")
                        except Exception as exc:
                            warnings.append(f"TVMaze episode lookup failed: {exc}")

                    show_name = str(
                        preferred.get("name")
                        or media_file.parsed_title
                        or "Unknown Series"
                    )
                    dst_path = self._build_tv_path(
                        show_name,
                        media_file.parsed_season,
                        media_file.parsed_episode,
                        episode_title,
                    )

                    return PlanItem(
                        src_path=media_file.path,
                        dst_path=dst_path,
                        reason=f"Matched TV show '{show_name}' with TVMaze (fallback)",
                        confidence=0.6,
                        sources=[SourceRef(provider="tvmaze", id=str(series_id))],
                        warnings=warnings,
                    )
        except Exception as e:
            warnings.append(f"TVMaze fallback failed: {str(e)}")

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

    async def map_anthology_segments(self, media_file: MediaFile) -> list[PlanItem]:
        """Attempt deterministic anthology mapping using TVDB episodes."""

        if not media_file.anthology_candidate or not media_file.segments:
            return []
        if not media_file.parsed_title or not media_file.parsed_season:
            return []

        series_results = await self._lookup_tvdb_series(media_file.parsed_title)
        if not series_results or len(series_results) != 1:
            return []

        series = series_results[0]
        series_id = series.get("id")
        episodes = await self._fetch_tvdb_episodes(series_id)
        if not episodes:
            return []

        simplify = interval_simplify(media_file, episodes)
        if simplify.punt_to_llm or simplify.confidence < 0.9:
            media_file.needs_disambiguation = True
            return []

        plan_items = self._build_anthology_plan_items(
            media_file=media_file,
            series=series,
            episodes=episodes,
            confidence=simplify.confidence,
            warnings=simplify.warnings,
            segments=simplify.segments,
        )
        return plan_items

    async def _lookup_tvdb_series(self, title: str) -> list[dict[str, Any]] | None:
        try:
            return await self.tvdb.search_series(title)
        except Exception:
            return None

    async def _fetch_tvdb_episodes(self, series_id: Any) -> list[dict[str, Any]]:
        if series_id is None:
            return []
        try:
            return await self.tvdb.get_series_episodes(series_id)
        except Exception:
            return []

    def _build_anthology_plan_items(
        self,
        *,
        media_file: MediaFile,
        series: dict[str, Any],
        episodes: list[dict[str, Any]],
        confidence: float,
        warnings: list[str],
        segments: list[EpisodeSegment],
    ) -> list[PlanItem]:
        season = media_file.parsed_season
        if season is None:
            return []

        show_name = str(
            series.get("name")
            or series.get("seriesName")
            or media_file.parsed_title
            or "Unknown Series"
        )

        series_id = series.get("id")
        episode_lookup: dict[int, dict[str, Any]] = {}
        for episode in episodes:
            season_number = (
                episode.get("seasonNumber")
                or episode.get("SeasonNumber")
                or episode.get("airedSeason")
                or episode.get("season")
            )
            number = (
                episode.get("number")
                or episode.get("episodeNumber")
                or episode.get("airedEpisodeNumber")
            )
            if season_number is None or number is None:
                continue
            if int(season_number) != season:
                continue
            episode_lookup[int(number)] = episode

        plan_items: list[PlanItem] = []
        for segment in segments:
            start = getattr(segment, "start", None)
            end = getattr(segment, "end", None)
            if start is None or end is None:
                continue

            episode_numbers = list(range(start, end + 1))
            titles: list[str] = []
            for number in episode_numbers:
                episode_data = episode_lookup.get(number)
                if not episode_data:
                    continue
                title = (
                    episode_data.get("name")
                    or episode_data.get("episodeName")
                    or episode_data.get("title")
                )
                if title:
                    titles.append(str(title))

            combined_title = " & ".join(titles) if titles else None
            dst_path = self._build_tv_path(
                show_name,
                season,
                start,
                combined_title,
                episode_end=end,
            )
            reason = (
                f"Deterministic anthology span S{season:02d}E{start:02d}-E{end:02d}"
                if end != start
                else f"Deterministic anthology match S{season:02d}E{start:02d}"
            )
            plan_items.append(
                PlanItem(
                    src_path=media_file.path,
                    dst_path=dst_path,
                    reason=reason,
                    confidence=confidence,
                    sources=[SourceRef(provider="tvdb", id=str(series_id))],
                    warnings=list(warnings),
                )
            )

        return plan_items

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
