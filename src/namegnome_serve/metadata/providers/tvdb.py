"""TVDB v3 API provider with JWT authentication and token caching.

TVDB v3 (Legacy) API specifics:
- Auth: POST /login with {"apikey": "KEY"} → JWT token
- Token cached for 24hrs (refresh on 401)
- All requests use Bearer {token} header
- Search: GET /search/series?name=...
- Episodes: GET /series/{id}/episodes (paginated)

Security:
- API key from environment only (never hardcoded)
- Token cached in memory (no disk storage for security)
- Rate limiting enforced (40 req/min conservative)
"""

import inspect
from typing import Any

import httpx

from namegnome_serve.metadata.providers.base import BaseProvider, ProviderError


class TVDBProvider(BaseProvider):
    """TVDB v3 provider for TV series with JWT authentication."""

    BASE_URL = "https://api.thetvdb.com"

    def __init__(self) -> None:
        """Initialize TVDB v3 provider with JWT auth."""
        super().__init__(
            provider_name="TVDB",
            api_key_env_var="TVDB_API_KEY",
            rate_limit_per_minute=40,  # Conservative: no official limit
            max_retries=3,
        )

        # httpx async client
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=10.0)

        # JWT token cache (in-memory)
        self._auth_token: str | None = None

    async def _get_auth_token(self) -> str:
        """Get JWT authentication token (cached or fresh).

        Returns:
            JWT token string

        Raises:
            ProviderError: On authentication failure
        """
        # Return cached token if available
        if self._auth_token:
            return self._auth_token

        # Authenticate to get new token
        if not self.api_key:
            raise ProviderError("TVDB API key not configured")

        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        try:
            response = await self._client.post(
                f"{self.BASE_URL}/login", json={"apikey": self.api_key}
            )
            response.raise_for_status()
            data = response.json()
            if inspect.isawaitable(data):
                data = await data
            data = dict(data)
            token: str = data["token"]

            # Cache token
            self._auth_token = token
            return token

        except httpx.HTTPStatusError as e:
            raise ProviderError(f"TVDB authentication failed: {e}") from e

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get headers with Bearer token for API requests.

        Returns:
            Headers dict with Authorization and Accept
        """
        token = await self._get_auth_token()
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def _request_with_reauth(
        self, method: str, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Make API request with automatic re-auth on 401.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL
            **kwargs: Additional request parameters

        Returns:
            Response JSON data

        Raises:
            ProviderError: On request failure (non-401)
        """
        headers = await self._get_auth_headers()
        kwargs["headers"] = headers

        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        try:
            if method.upper() == "GET":
                response = await self._client.get(url, **kwargs)
            elif method.upper() == "POST":
                response = await self._client.post(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            data = response.json()
            if inspect.isawaitable(data):
                data = await data
            data = dict(data)
            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Token expired - clear cache and retry once
                self._auth_token = None
                headers = await self._get_auth_headers()
                kwargs["headers"] = headers

                if method.upper() == "GET":
                    response = await self._client.get(url, **kwargs)
                else:
                    response = await self._client.post(url, **kwargs)

                response.raise_for_status()
                result = response.json()
                if inspect.isawaitable(result):
                    result = await result
                result = dict(result)
                return result

            elif e.response.status_code == 404:
                # Return empty for not found
                return {"data": []}

            raise ProviderError(f"TVDB request failed: {e}") from e

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search for TV series by name.

        Args:
            query: Series name to search
            **kwargs: Unused for TVDB

        Returns:
            List of series results
        """
        return await self.search_series(query)

    async def get_details(self, entity_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Get series details by ID.

        Args:
            entity_id: TVDB series ID
            **kwargs: Unused for TVDB

        Returns:
            Series details or None if not found
        """

        async def _do_get_details() -> dict[str, Any] | None:
            try:
                data = await self._request_with_reauth(
                    "GET", f"{self.BASE_URL}/series/{entity_id}"
                )
                return data.get("data")
            except ProviderError:
                return None

        return await self._execute_with_retry(_do_get_details, "get_details")

    async def search_series(self, name: str) -> list[dict[str, Any]]:
        """Search for TV series by name.

        Args:
            name: Series name to search

        Returns:
            List of matching series
        """

        async def _do_search() -> list[dict[str, Any]]:
            try:
                data = await self._request_with_reauth(
                    "GET", f"{self.BASE_URL}/search/series", params={"name": name}
                )
                results: list[dict[str, Any]] = data.get("data", [])
                return results
            except ProviderError:
                return []

        return await self._execute_with_retry(_do_search, "search_series")

    async def get_series_episodes(self, series_id: int) -> list[dict[str, Any]]:
        """Get all episodes for a TV series (handles pagination).

        Args:
            series_id: TVDB series ID

        Returns:
            List of all episodes
        """
        all_episodes: list[dict[str, Any]] = []
        page = 1

        while True:
            try:
                data = await self._request_with_reauth(
                    "GET",
                    f"{self.BASE_URL}/series/{series_id}/episodes",
                    params={"page": page},
                )

                episodes: list[dict[str, Any]] = data.get("data", [])
                all_episodes.extend(episodes)

                # Check for next page
                links = data.get("links", {})
                if "next" in links and links["next"]:
                    page += 1
                else:
                    break

            except ProviderError:
                break

        return all_episodes

    def _format_episode(self, raw_episode: dict[str, Any]) -> dict[str, Any]:
        """Format raw TVDB episode data to standardized format.

        Args:
            raw_episode: Raw episode dict from TVDB API

        Returns:
            Formatted episode dict
        """
        return {
            "episode_id": raw_episode.get("id"),
            "season": raw_episode.get("airedSeason"),
            "episode": raw_episode.get("airedEpisodeNumber"),
            "title": raw_episode.get("episodeName"),
            "overview": raw_episode.get("overview"),
            "air_date": raw_episode.get("firstAired"),
        }

    async def __aenter__(self) -> "TVDBProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - close client."""
        await self._client.aclose()
