"""Tests for the deterministic mapper that maps scan fields to provider entities."""

from unittest.mock import AsyncMock, Mock

import pytest

from namegnome_serve.core.deterministic_mapper import DeterministicMapper
from namegnome_serve.core.scanner import MediaFile


class TestDeterministicMapper:
    """Test the deterministic mapper for TV shows, movies, and music."""

    def test_mapper_initialization(self):
        """Test that mapper initializes with providers."""
        # Mock the providers to avoid API key requirements
        mock_tmdb = Mock()
        mock_tvdb = Mock()
        mock_mb = Mock()

        mapper = DeterministicMapper(
            tmdb=mock_tmdb, tvdb=mock_tvdb, musicbrainz=mock_mb
        )

        assert mapper.tmdb is not None
        assert mapper.tvdb is not None
        assert mapper.musicbrainz is not None

    @pytest.mark.asyncio
    async def test_map_tv_show_exact_match(self):
        """Test mapping TV show with exact title and year match."""
        # Mock TVDB provider
        mock_tvdb = AsyncMock()
        mock_tvdb.search_series.return_value = [
            {
                "id": "12345",
                "name": "Breaking Bad",
                "first_air_date": "2008-01-20",
                "overview": "A high school chemistry teacher...",
            }
        ]
        mock_tvdb.get_series_episodes.return_value = [
            {"id": "ep1", "name": "Pilot", "seasonNumber": 1, "number": 1}
        ]

        mapper = DeterministicMapper(tmdb=Mock(), tvdb=mock_tvdb, musicbrainz=Mock())

        # Create test media file
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
        assert result.confidence >= 0.75  # High confidence
        assert (
            str(result.dst_path)
            == "/tv/Breaking Bad/Season 01/Breaking Bad - S01E01 - Pilot.mkv"
        )
        assert result.sources[0].id == "12345"
        assert result.sources[0].provider == "tvdb"

    @pytest.mark.asyncio
    async def test_map_movie_exact_match(self):
        """Test mapping movie with exact title and year match."""
        # Mock TMDB provider
        mock_tmdb = AsyncMock()
        mock_tmdb.search_movie.return_value = [
            {
                "id": 12345,
                "title": "The Matrix",
                "release_date": "1999-03-31",
                "overview": "A computer hacker learns...",
            }
        ]
        mock_tmdb.get_movie_details.return_value = {
            "id": 12345,
            "title": "The Matrix",
            "release_date": "1999-03-31",
            "poster_url": "https://image.tmdb.org/t/p/original/poster.jpg",
        }

        mapper = DeterministicMapper(tmdb=mock_tmdb, tvdb=Mock(), musicbrainz=Mock())

        # Create test media file
        media_file = MediaFile(
            path="/movies/The Matrix (1999).mkv",
            size=2048,
            mtime=1234567890,
            parsed_title="The Matrix",
            parsed_year=1999,
        )

        result = await mapper.map_media_file(media_file, "movie")

        assert result is not None
        assert result.confidence >= 0.75  # High confidence
        assert result.dst_path == "/movies/The Matrix (1999)/The Matrix (1999).mkv"
        assert result.provider_id == "12345"
        assert result.provider == "TMDB"

    @pytest.mark.asyncio
    async def test_map_music_exact_match(self):
        """Test mapping music with exact artist and track match."""
        # Mock MusicBrainz provider
        mock_mb = AsyncMock()
        mock_mb.search_recording.return_value = [
            {
                "id": "rec-123",
                "title": "Bohemian Rhapsody",
                "artist-credit": [{"name": "Queen"}],
                "releases": [{"id": "rel-456", "title": "A Night at the Opera"}],
            }
        ]
        mock_mb.get_release_group.return_value = {
            "id": "rg-789",
            "title": "A Night at the Opera",
            "artist-credit": [{"name": "Queen"}],
        }

        mapper = DeterministicMapper(tmdb=Mock(), tvdb=Mock(), musicbrainz=mock_mb)

        # Create test media file
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
        assert result.confidence >= 0.75  # High confidence
        assert (
            result.dst_path
            == "/music/Queen/A Night at the Opera/01 - Bohemian Rhapsody.flac"
        )
        assert result.provider_id == "rec-123"
        assert result.provider == "MusicBrainz"

    @pytest.mark.asyncio
    async def test_map_tv_show_ambiguous_match(self):
        """Test mapping TV show with multiple matches requires disambiguation."""
        # Mock TVDB provider with multiple results
        mock_tvdb = AsyncMock()
        mock_tvdb.search_series.return_value = [
            {
                "id": "12345",
                "name": "The Office",
                "first_air_date": "2005-03-24",
                "overview": "US version",
            },
            {
                "id": "67890",
                "name": "The Office",
                "first_air_date": "2001-07-09",
                "overview": "UK version",
            },
        ]

        mapper = DeterministicMapper(tmdb=Mock(), tvdb=mock_tvdb, musicbrainz=Mock())

        # Create test media file
        media_file = MediaFile(
            path="/tv/The Office/S01E01.mkv",
            size=1024,
            mtime=1234567890,
            parsed_title="The Office",
            parsed_season=1,
            parsed_episode=1,
            parsed_year=None,  # No year to disambiguate
        )

        result = await mapper.map_media_file(media_file, "tv")

        assert result is None  # Should return None for ambiguous matches

    @pytest.mark.asyncio
    async def test_map_movie_no_match(self):
        """Test mapping movie with no provider matches."""
        # Mock TMDB provider with no results
        mock_tmdb = AsyncMock()
        mock_tmdb.search_movie.return_value = []

        mapper = DeterministicMapper(tmdb=mock_tmdb, tvdb=Mock(), musicbrainz=Mock())

        # Create test media file
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
    async def test_map_tv_show_with_episode_title(self):
        """Test mapping TV show with episode title from provider."""
        # Mock TVDB provider
        mock_tvdb = AsyncMock()
        mock_tvdb.search_series.return_value = [
            {"id": "12345", "name": "Breaking Bad", "first_air_date": "2008-01-20"}
        ]
        mock_tvdb.get_series_episodes.return_value = [
            {"id": "ep1", "name": "Pilot", "seasonNumber": 1, "number": 1}
        ]

        mapper = DeterministicMapper(tmdb=Mock(), tvdb=mock_tvdb, musicbrainz=Mock())

        # Create test media file
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
        # Episode title should be in the destination path
        assert "Pilot" in str(result.dst_path)

    @pytest.mark.asyncio
    async def test_map_music_with_album_artist(self):
        """Test mapping music with album and artist information."""
        # Mock MusicBrainz provider
        mock_mb = AsyncMock()
        mock_mb.search_recording.return_value = [
            {
                "id": "rec-123",
                "title": "Bohemian Rhapsody",
                "artist-credit": [{"name": "Queen"}],
                "releases": [{"id": "rel-456", "title": "A Night at the Opera"}],
            }
        ]
        mock_mb.get_release_group.return_value = {
            "id": "rg-789",
            "title": "A Night at the Opera",
            "artist-credit": [{"name": "Queen"}],
        }

        mapper = DeterministicMapper(tmdb=Mock(), tvdb=Mock(), musicbrainz=mock_mb)

        # Create test media file
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
        assert result.album_title == "A Night at the Opera"
        assert result.artist_name == "Queen"
