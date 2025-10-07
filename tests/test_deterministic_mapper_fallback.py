"""Tests for fallback chain logic in deterministic mapper."""

from unittest.mock import AsyncMock, Mock

import pytest

from namegnome_serve.core.deterministic_mapper import DeterministicMapper
from namegnome_serve.routes.schemas import MediaFile


@pytest.fixture(autouse=True)
def _set_theaudiodb_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure fallback chain can construct TheAudioDB provider in tests."""

    monkeypatch.setenv("THEAUDIODB_API_KEY", "test_key")


class TestDeterministicMapperFallback:
    """Test fallback chain logic for failed mappings."""

    @pytest.mark.asyncio
    async def test_tv_show_tmdb_fallback(self):
        """TV fallback should use TMDB when TVDB fails."""
        # Mock TVDB provider to fail
        mock_tvdb = AsyncMock()
        mock_tvdb.search_series.side_effect = Exception("TVDB API error")

        mock_tmdb = AsyncMock()
        mock_tmdb.search_tv.return_value = [
            {"id": 101, "name": "Breaking Bad", "first_air_date": "2008-01-20"}
        ]
        mock_tmdb.get_tv_episodes.return_value = [
            {
                "id": "tmdb-ep1",
                "season_number": 1,
                "episode_number": 1,
                "name": "Pilot",
            }
        ]

        mock_omdb = AsyncMock()
        mock_tvmaze = AsyncMock()

        mapper = DeterministicMapper(
            tmdb=mock_tmdb,
            tvdb=mock_tvdb,
            musicbrainz=Mock(),
            omdb=mock_omdb,
            tvmaze=mock_tvmaze,
        )

        media_file = MediaFile(
            path="/tv/Breaking Bad/S01E01.mkv",
            size=1024,
            mtime=1234567890,
            parsed_title="Breaking Bad",
            parsed_season=1,
            parsed_episode=1,
            parsed_year=2008,
        )

        result = await mapper.map_media_file(media_file, "tv")

        assert result is not None
        assert result.sources[0].provider == "tmdb"
        assert result.sources[0].id == "101"
        mock_tmdb.search_tv.assert_awaited_once_with("Breaking Bad", year=2008)
        mock_tmdb.get_tv_episodes.assert_awaited_once_with(101, season=1)
        mock_omdb.search_series.assert_not_called()
        mock_tvmaze.search_series.assert_not_called()

    @pytest.mark.asyncio
    async def test_tv_show_tvmaze_fallback(self):
        """TV fallback should end at TVMaze when all others fail."""

        mock_tvdb = AsyncMock()
        mock_tvdb.search_series.side_effect = Exception("TVDB API error")

        mock_tmdb = AsyncMock()
        mock_tmdb.search_tv.side_effect = Exception("TMDB API error")

        mock_omdb = AsyncMock()
        mock_omdb.search_series.side_effect = Exception("OMDb API error")

        mock_tvmaze = AsyncMock()
        mock_tvmaze.search_series.return_value = [
            {"id": 555, "name": "Breaking Bad", "premiered": "2008-01-20"}
        ]
        mock_tvmaze.get_episode.return_value = {
            "id": 999,
            "name": "Pilot",
            "season": 1,
            "number": 1,
        }

        mapper = DeterministicMapper(
            tmdb=mock_tmdb,
            tvdb=mock_tvdb,
            musicbrainz=Mock(),
            omdb=mock_omdb,
            tvmaze=mock_tvmaze,
        )

        media_file = MediaFile(
            path="/tv/Breaking Bad/S01E01.mkv",
            size=1024,
            mtime=1234567890,
            parsed_title="Breaking Bad",
            parsed_season=1,
            parsed_episode=1,
            parsed_year=2008,
        )

        result = await mapper.map_media_file(media_file, "tv")

        assert result is not None
        assert result.sources[0].provider == "tvmaze"
        assert result.sources[0].id == "555"
        mock_tmdb.search_tv.assert_awaited_once()
        mock_omdb.search_series.assert_awaited_once()
        mock_tvmaze.search_series.assert_awaited_once_with("Breaking Bad")

    @pytest.mark.asyncio
    async def test_movie_fallback_chain(self):
        """Test movie mapping with TMDB failure falls back to TVDB then OMDb."""
        # Mock TMDB provider to fail
        mock_tmdb = AsyncMock()
        mock_tmdb.search_movie.side_effect = Exception("TMDB API error")

        # Mock TVDB provider to fail
        mock_tvdb = AsyncMock()
        mock_tvdb.search_movie.side_effect = Exception("TVDB API error")

        # Mock OMDb provider to succeed
        mock_omdb = AsyncMock()
        mock_omdb.search_movie.return_value = [
            {"id": "tt0133093", "title": "The Matrix", "year": "1999", "type": "movie"}
        ]
        mock_omdb.get_movie_details.return_value = {
            "id": "tt0133093",
            "title": "The Matrix",
            "year": "1999",
            "poster": "https://example.com/poster.jpg",
        }

        mapper = DeterministicMapper(
            tmdb=mock_tmdb, tvdb=mock_tvdb, musicbrainz=Mock(), omdb=mock_omdb
        )

        media_file = MediaFile(
            path="/movies/The Matrix (1999).mkv",
            size=2048,
            mtime=1234567890,
            parsed_title="The Matrix",
            parsed_year=1999,
        )

        result = await mapper.map_media_file(media_file, "movie")

        assert result is not None
        assert result.sources[0].provider == "omdb"
        assert result.sources[0].id == "tt0133093"

    @pytest.mark.asyncio
    async def test_music_fallback_chain(self):
        """Test music mapping with MusicBrainz failure falls back to TheAudioDB."""
        # Mock MusicBrainz provider to fail
        mock_mb = AsyncMock()
        mock_mb.search_recording.side_effect = Exception("MusicBrainz API error")

        # Mock TheAudioDB provider to succeed
        mock_tadb = AsyncMock()
        mock_tadb.search_track.return_value = [
            {
                "idTrack": "11111",
                "strTrack": "Bohemian Rhapsody",
                "strArtist": "Queen",
                "strAlbum": "A Night at the Opera",
            }
        ]
        mock_tadb.get_track_details.return_value = {
            "idTrack": "11111",
            "strTrack": "Bohemian Rhapsody",
            "strArtist": "Queen",
            "strAlbum": "A Night at the Opera",
        }

        mapper = DeterministicMapper(
            tmdb=Mock(), tvdb=Mock(), musicbrainz=mock_mb, theaudiodb=mock_tadb
        )

        media_file = MediaFile(
            path="/music/Queen/A Night at the Opera/01 - Bohemian Rhapsody.flac",
            size=512,
            mtime=1234567890,
            parsed_title="Bohemian Rhapsody",
            parsed_artist="Queen",
            parsed_album="A Night at the Opera",
            parsed_track=1,
        )

        result = await mapper.map_media_file(media_file, "music")

        assert result is not None
        assert result.sources[0].provider == "theaudiodb"
        assert result.sources[0].id == "11111"

    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        """Test that all providers failing returns None."""
        # Mock all providers to fail
        mock_tmdb = AsyncMock()
        mock_tmdb.search_movie.side_effect = Exception("TMDB API error")

        mock_omdb = AsyncMock()
        mock_omdb.search_movie.side_effect = Exception("OMDb API error")

        mapper = DeterministicMapper(
            tmdb=mock_tmdb, tvdb=Mock(), musicbrainz=Mock(), omdb=mock_omdb
        )

        media_file = MediaFile(
            path="/movies/Unknown Movie (2023).mkv",
            size=2048,
            mtime=1234567890,
            parsed_title="Unknown Movie",
            parsed_year=2023,
        )

        result = await mapper.map_media_file(media_file, "movie")

        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_with_warnings(self):
        """Test that fallback mappings include warnings about provider failures."""
        # Mock primary provider to fail
        mock_tmdb = AsyncMock()
        mock_tmdb.search_movie.side_effect = Exception("TMDB API error")

        # Mock fallback provider to succeed
        mock_omdb = AsyncMock()
        mock_omdb.search_movie.return_value = [
            {"id": "tt12345", "title": "The Matrix", "year": "1999", "type": "movie"}
        ]
        mock_omdb.get_movie_details.return_value = {
            "id": "tt12345",
            "title": "The Matrix",
            "year": "1999",
        }

        mapper = DeterministicMapper(
            tmdb=mock_tmdb, tvdb=Mock(), musicbrainz=Mock(), omdb=mock_omdb
        )

        media_file = MediaFile(
            path="/movies/The Matrix (1999).mkv",
            size=2048,
            mtime=1234567890,
            parsed_title="The Matrix",
            parsed_year=1999,
        )

        result = await mapper.map_media_file(media_file, "movie")

        assert result is not None
        assert "TMDB API error" in result.warnings[0]
        assert result.sources[0].provider == "omdb"
