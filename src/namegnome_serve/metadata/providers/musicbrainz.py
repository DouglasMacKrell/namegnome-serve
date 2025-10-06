"""MusicBrainz provider for music metadata (no API key required).

MusicBrainz specifics:
- NO API key required (free, open data)
- STRICT rate limit: 1 request per second (50 req/min to be safe)
- MUST include User-Agent header with contact info
- Search: /ws/2/recording, /ws/2/artist, /ws/2/release-group
- All responses are JSON (fmt=json parameter)

Security:
- No API key needed
- User-Agent header identifies our application
- Rate limiting strictly enforced (50 req/min = ~1.2 req/sec)
"""

from typing import Any

import httpx

from namegnome_serve.metadata.providers.base import BaseProvider, ProviderError


class MusicBrainzProvider(BaseProvider):
    """MusicBrainz provider for music recordings, artists, and albums."""

    BASE_URL = "https://musicbrainz.org/ws/2"
    USER_AGENT = (
        "NameGnomeServe/1.0 (https://github.com/DouglasMacKrell/namegnome-serve)"
    )

    def __init__(self) -> None:
        """Initialize MusicBrainz provider (no API key needed)."""
        super().__init__(
            provider_name="MusicBrainz",
            api_key_env_var="",  # No API key required!
            rate_limit_per_minute=50,  # Conservative: ~1 req/sec
            max_retries=3,
        )

        # httpx async client
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=10.0)

    def _get_headers(self) -> dict[str, str]:
        """Get headers with required User-Agent.

        Returns:
            Headers dict with User-Agent and Accept
        """
        return {"User-Agent": self.USER_AGENT, "Accept": "application/json"}

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search for recordings by query.

        Args:
            query: Recording name to search
            **kwargs: Unused for MusicBrainz

        Returns:
            List of recording results
        """
        return await self.search_recording(query)

    async def get_details(self, entity_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Get release group details by ID.

        Args:
            entity_id: MusicBrainz release group ID
            **kwargs: Unused for MusicBrainz

        Returns:
            Release group details or None if not found
        """
        return await self.get_release_group(entity_id)

    async def search_recording(
        self, query: str, limit: int = 25
    ) -> list[dict[str, Any]]:
        """Search for music recordings.

        Args:
            query: Recording title to search
            limit: Max results to return

        Returns:
            List of matching recordings
        """
        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/recording",
                headers=self._get_headers(),
                params={"query": query, "limit": limit, "fmt": "json"},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            results: list[dict[str, Any]] = data.get("recordings", [])
            return results

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            elif e.response.status_code == 503:
                # Rate limit exceeded - retry once after delay
                if not self.check_rate_limit():
                    raise ProviderError(
                        f"{self.provider_name} rate limit exceeded"
                    ) from e

                response = await self._client.get(
                    f"{self.BASE_URL}/recording",
                    headers=self._get_headers(),
                    params={"query": query, "limit": limit, "fmt": "json"},
                )
                response.raise_for_status()
                retry_data = response.json()
                retry_results: list[dict[str, Any]] = retry_data.get("recordings", [])
                return retry_results

            raise ProviderError(f"MusicBrainz search failed: {e}") from e

    async def search_artist(self, name: str, limit: int = 25) -> list[dict[str, Any]]:
        """Search for artists by name.

        Args:
            name: Artist name to search
            limit: Max results to return

        Returns:
            List of matching artists
        """
        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/artist",
                headers=self._get_headers(),
                params={"query": name, "limit": limit, "fmt": "json"},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            results: list[dict[str, Any]] = data.get("artists", [])
            return results

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            elif e.response.status_code == 503:
                # Rate limit exceeded - retry once after delay
                if not self.check_rate_limit():
                    raise ProviderError(
                        f"{self.provider_name} rate limit exceeded"
                    ) from e

                response = await self._client.get(
                    f"{self.BASE_URL}/artist",
                    headers=self._get_headers(),
                    params={"query": name, "limit": limit, "fmt": "json"},
                )
                response.raise_for_status()
                retry_data = response.json()
                retry_results: list[dict[str, Any]] = retry_data.get("artists", [])
                return retry_results

            raise ProviderError(f"MusicBrainz search failed: {e}") from e

    async def get_release_group(self, release_group_id: str) -> dict[str, Any] | None:
        """Get release group (album) details.

        Args:
            release_group_id: MusicBrainz release group ID

        Returns:
            Release group details or None if not found
        """
        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/release-group/{release_group_id}",
                headers=self._get_headers(),
                params={"fmt": "json"},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (400, 404):
                # 400 = invalid UUID, 404 = not found
                return None
            raise ProviderError(f"MusicBrainz get_release_group failed: {e}") from e

    def _format_recording(self, raw_recording: dict[str, Any]) -> dict[str, Any]:
        """Format raw MusicBrainz recording data.

        Args:
            raw_recording: Raw recording dict from MusicBrainz API

        Returns:
            Formatted recording dict
        """
        # Extract artist from artist-credit array
        artist_credit = raw_recording.get("artist-credit", [])
        artist_name = None
        if artist_credit and len(artist_credit) > 0:
            artist_name = artist_credit[0].get("artist", {}).get("name")

        return {
            "recording_id": raw_recording.get("id"),
            "title": raw_recording.get("title"),
            "duration_ms": raw_recording.get("length"),
            "artist": artist_name,
        }

    async def __aenter__(self) -> "MusicBrainzProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - close client."""
        await self._client.aclose()
