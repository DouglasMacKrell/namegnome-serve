"""TheAudioDB provider for music metadata and artwork.

Security:
- No API key required (free service)
- User-Agent required for identification
- Rate limits: 1 request per second

Features:
- Music metadata and artwork
- Artist, album, and track information
- High-quality artwork (logos, banners, clearart)
- Automatic retry/backoff via BaseProvider
"""

from typing import Any, cast

import httpx

from namegnome_serve.metadata.providers.base import BaseProvider


class TheAudioDBProvider(BaseProvider):
    """TheAudioDB provider for music metadata and artwork."""

    BASE_URL = "https://www.theaudiodb.com/api/v1/json"
    USER_AGENT = "NameGnome/1.0 (https://github.com/namegnome/namegnome-serve)"

    def __init__(self) -> None:
        """Initialize TheAudioDB provider."""
        super().__init__(
            provider_name="TheAudioDB",
            api_key_env_var="THEAUDIODB_API_KEY",  # API key required
            rate_limit_per_minute=30,  # Free limit: 30 requests per minute
            max_retries=3,
        )

        # httpx async client (context managed per request)
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=10.0, headers={"User-Agent": self.USER_AGENT}
        )

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search for music by query string.

        Args:
            query: Search query (artist name, track title, etc.)
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        # TheAudioDB doesn't have a general search endpoint
        # We'll implement specific search methods instead
        raise NotImplementedError(
            "Use specific search methods like search_artist or search_track"
        )

    async def get_details(self, entity_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Get detailed information about a music entity.

        Args:
            entity_id: Entity ID
            **kwargs: Additional parameters

        Returns:
            Detailed entity information or None
        """
        # TheAudioDB doesn't have a general details endpoint
        # We'll implement specific detail methods instead
        raise NotImplementedError("Use specific detail methods like get_artist_details")

    async def search_artist(self, artist_name: str) -> list[dict[str, Any]]:
        """Search for artist by name.

        Args:
            artist_name: Name of the artist to search for

        Returns:
            List of artist search results
        """

        async def _do_search() -> list[dict[str, Any]]:
            url = f"{self.BASE_URL}/{self.api_key}/search.php"
            params = {"s": artist_name}

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = cast(dict[str, Any], response.json())
            artists = cast(list[dict[str, Any]] | None, data.get("artists"))
            if artists:
                return artists
            return []

        return await self._execute_with_retry(_do_search)

    async def get_artist_details(self, artist_id: str) -> dict[str, Any] | None:
        """Get detailed artist information.

        Args:
            artist_id: TheAudioDB artist ID

        Returns:
            Artist details or None
        """

        async def _do_get_details() -> dict[str, Any] | None:
            url = f"{self.BASE_URL}/{self.api_key}/artist.php"
            params = {"i": artist_id}

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = cast(dict[str, Any], response.json())
            artists = cast(list[dict[str, Any]] | None, data.get("artists"))
            if artists and len(artists) > 0:
                return artists[0]
            return None

        return await self._execute_with_retry(_do_get_details)

    async def search_album(
        self, album_name: str, artist_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Search for album by name and optionally artist.

        Args:
            album_name: Name of the album to search for
            artist_name: Optional artist name to narrow search

        Returns:
            List of album search results
        """

        async def _do_search() -> list[dict[str, Any]]:
            url = f"{self.BASE_URL}/{self.api_key}/searchalbum.php"
            params: dict[str, Any] = {}
            if artist_name:
                params["s"] = artist_name
            if album_name:
                params["a"] = album_name
                params.setdefault("s", album_name)
            if "s" not in params:
                params["s"] = album_name

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = cast(dict[str, Any], response.json())
            albums = cast(list[dict[str, Any]] | None, data.get("album"))
            if albums:
                return albums
            return []

        return await self._execute_with_retry(_do_search)

    async def get_album_details(self, album_id: str) -> dict[str, Any] | None:
        """Get detailed album information.

        Args:
            album_id: TheAudioDB album ID

        Returns:
            Album details or None
        """

        async def _do_get_details() -> dict[str, Any] | None:
            url = f"{self.BASE_URL}/{self.api_key}/album.php"
            params = {"m": album_id}

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = cast(dict[str, Any], response.json())
            albums = cast(list[dict[str, Any]] | None, data.get("album"))
            if albums and len(albums) > 0:
                return albums[0]
            return None

        return await self._execute_with_retry(_do_get_details)

    async def search_track(
        self, track_name: str, artist_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Search for track by name and optionally artist.

        Args:
            track_name: Name of the track to search for
            artist_name: Optional artist name to narrow search

        Returns:
            List of track search results
        """

        async def _do_search() -> list[dict[str, Any]]:
            url = f"{self.BASE_URL}/{self.api_key}/searchtrack.php"
            params: dict[str, Any] = {"t": track_name}
            if artist_name:
                params["s"] = artist_name
            else:
                params.setdefault("s", track_name)

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = cast(dict[str, Any], response.json())
            tracks = cast(list[dict[str, Any]] | None, data.get("track"))
            if tracks:
                return tracks
            return []

        return await self._execute_with_retry(_do_search)

    async def get_track_details(self, track_id: str) -> dict[str, Any] | None:
        """Get detailed track information.

        Args:
            track_id: TheAudioDB track ID

        Returns:
            Track details or None
        """

        async def _do_get_details() -> dict[str, Any] | None:
            url = f"{self.BASE_URL}/{self.api_key}/track.php"
            params = {"h": track_id}

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = cast(dict[str, Any], response.json())
            tracks = cast(list[dict[str, Any]] | None, data.get("track"))
            if tracks and len(tracks) > 0:
                return tracks[0]
            return None

        return await self._execute_with_retry(_do_get_details)

    async def get_artist_artwork(self, artist_id: str) -> dict[str, Any] | None:
        """Get artist artwork (logos, banners, clearart).

        Args:
            artist_id: TheAudioDB artist ID

        Returns:
            Artist artwork information or None
        """

        async def _do_get_artwork() -> dict[str, Any] | None:
            url = f"{self.BASE_URL}/{self.api_key}/artist.php"
            params = {"i": artist_id}

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = cast(dict[str, Any], response.json())
            artists = cast(list[dict[str, Any]] | None, data.get("artists"))
            if artists and len(artists) > 0:
                artist = artists[0]
                return {
                    "logos": artist.get("strArtistLogo", ""),
                    "banners": artist.get("strArtistBanner", ""),
                    "clearart": artist.get("strArtistClearart", ""),
                    "fanart": artist.get("strArtistFanart", ""),
                }
            return None

        return await self._execute_with_retry(_do_get_artwork)

    async def get_album_artwork(self, album_id: str) -> dict[str, Any] | None:
        """Get album artwork (covers, backdrops).

        Args:
            album_id: TheAudioDB album ID

        Returns:
            Album artwork information or None
        """

        async def _do_get_artwork() -> dict[str, Any] | None:
            url = f"{self.BASE_URL}/{self.api_key}/album.php"
            params = {"m": album_id}

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            if data.get("album") and len(data["album"]) > 0:
                album = data["album"][0]
                return {
                    "cover": album.get("strAlbumThumb", ""),
                    "backdrop": album.get("strAlbumSpine", ""),
                }
            return None

        return await self._execute_with_retry(_do_get_artwork)

    async def __aenter__(self) -> "TheAudioDBProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._client.aclose()
