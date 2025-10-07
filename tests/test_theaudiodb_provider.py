"""Unit tests for TheAudioDB provider."""

from unittest.mock import AsyncMock, Mock

import pytest

from namegnome_serve.metadata.providers.theaudiodb import TheAudioDBProvider


@pytest.fixture(autouse=True)
def _set_theaudiodb_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure provider initialization sees a deterministic API key."""
    monkeypatch.setenv("THEAUDIODB_API_KEY", "test_key")


class TestTheAudioDBProvider:
    """Test TheAudioDB provider functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test provider initialization."""
        provider = TheAudioDBProvider()
        assert provider.provider_name == "TheAudioDB"
        assert provider.api_key == "test_key"
        assert provider.rate_limit_per_minute == 30

    @pytest.mark.asyncio
    async def test_user_agent_header(self):
        """Test that User-Agent header is set correctly."""
        provider = TheAudioDBProvider()
        assert "User-Agent" in provider._client.headers
        assert "NameGnome" in provider._client.headers["User-Agent"]

    @pytest.mark.asyncio
    async def test_search_artist(self):
        """Test artist search functionality."""
        provider = TheAudioDBProvider()

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "artists": [
                {
                    "idArtist": "12345",
                    "strArtist": "Queen",
                    "strBiographyEN": "British rock band",
                    "strCountry": "United Kingdom",
                }
            ]
        }
        mock_response.raise_for_status.return_value = None

        provider._client.get = AsyncMock(return_value=mock_response)

        results = await provider.search_artist("Queen")

        assert len(results) == 1
        assert results[0]["strArtist"] == "Queen"
        assert results[0]["idArtist"] == "12345"

    @pytest.mark.asyncio
    async def test_search_artist_no_results(self):
        """Test artist search with no results."""
        provider = TheAudioDBProvider()

        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = {"artists": None}
        mock_response.raise_for_status.return_value = None

        provider._client.get = AsyncMock(return_value=mock_response)

        results = await provider.search_artist("Nonexistent Artist")

        assert results == []

    @pytest.mark.asyncio
    async def test_get_artist_details(self):
        """Test getting artist details."""
        provider = TheAudioDBProvider()

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "artists": [
                {
                    "idArtist": "12345",
                    "strArtist": "Queen",
                    "strBiographyEN": "British rock band formed in 1970",
                    "strCountry": "United Kingdom",
                    "strGenre": "Rock",
                    "strArtistLogo": "https://example.com/logo.png",
                }
            ]
        }
        mock_response.raise_for_status.return_value = None

        provider._client.get = AsyncMock(return_value=mock_response)

        details = await provider.get_artist_details("12345")

        assert details is not None
        assert details["strArtist"] == "Queen"
        assert details["idArtist"] == "12345"
        assert "British rock band" in details["strBiographyEN"]

    @pytest.mark.asyncio
    async def test_search_album(self):
        """Test album search functionality."""
        provider = TheAudioDBProvider()

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "album": [
                {
                    "idAlbum": "67890",
                    "strAlbum": "A Night at the Opera",
                    "strArtist": "Queen",
                    "intYearReleased": "1975",
                }
            ]
        }
        mock_response.raise_for_status.return_value = None

        provider._client.get = AsyncMock(return_value=mock_response)

        results = await provider.search_album("A Night at the Opera", "Queen")

        assert len(results) == 1
        assert results[0]["strAlbum"] == "A Night at the Opera"
        assert results[0]["strArtist"] == "Queen"

    @pytest.mark.asyncio
    async def test_search_track(self):
        """Test track search functionality."""
        provider = TheAudioDBProvider()

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "track": [
                {
                    "idTrack": "11111",
                    "strTrack": "Bohemian Rhapsody",
                    "strArtist": "Queen",
                    "strAlbum": "A Night at the Opera",
                }
            ]
        }
        mock_response.raise_for_status.return_value = None

        provider._client.get = AsyncMock(return_value=mock_response)

        results = await provider.search_track("Bohemian Rhapsody", "Queen")

        assert len(results) == 1
        assert results[0]["strTrack"] == "Bohemian Rhapsody"
        assert results[0]["strArtist"] == "Queen"

    @pytest.mark.asyncio
    async def test_get_artist_artwork(self):
        """Test getting artist artwork."""
        provider = TheAudioDBProvider()

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "artists": [
                {
                    "idArtist": "12345",
                    "strArtist": "Queen",
                    "strArtistLogo": "https://example.com/logo.png",
                    "strArtistBanner": "https://example.com/banner.png",
                    "strArtistClearart": "https://example.com/clearart.png",
                    "strArtistFanart": "https://example.com/fanart.png",
                }
            ]
        }
        mock_response.raise_for_status.return_value = None

        provider._client.get = AsyncMock(return_value=mock_response)

        artwork = await provider.get_artist_artwork("12345")

        assert artwork is not None
        assert artwork["logos"] == "https://example.com/logo.png"
        assert artwork["banners"] == "https://example.com/banner.png"
        assert artwork["clearart"] == "https://example.com/clearart.png"
        assert artwork["fanart"] == "https://example.com/fanart.png"

    @pytest.mark.asyncio
    async def test_get_album_artwork(self):
        """Test getting album artwork."""
        provider = TheAudioDBProvider()

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "album": [
                {
                    "idAlbum": "67890",
                    "strAlbum": "A Night at the Opera",
                    "strAlbumThumb": "https://example.com/thumb.jpg",
                    "strAlbumSpine": "https://example.com/spine.jpg",
                }
            ]
        }
        mock_response.raise_for_status.return_value = None

        provider._client.get = AsyncMock(return_value=mock_response)

        artwork = await provider.get_album_artwork("67890")

        assert artwork is not None
        assert artwork["cover"] == "https://example.com/thumb.jpg"
        assert artwork["backdrop"] == "https://example.com/spine.jpg"

    @pytest.mark.asyncio
    async def test_http_error_handling(self):
        """Test HTTP error handling."""
        provider = TheAudioDBProvider()

        # Mock HTTP error
        provider._client.get = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception, match="Network error"):
            await provider.search_artist("Queen")

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        async with TheAudioDBProvider() as provider:
            assert isinstance(provider, TheAudioDBProvider)
            assert provider._client is not None
