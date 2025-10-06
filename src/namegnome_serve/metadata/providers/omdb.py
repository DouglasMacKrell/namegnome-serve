"""OMDb provider for movie metadata (fallback for TMDB).

OMDb specifics:
- Requires API key (free tier: 1,000 requests/day)
- Simple REST API using IMDb data
- Search: http://www.omdbapi.com/?s={query}&apikey={key}
- Details: http://www.omdbapi.com/?i={imdb_id}&apikey={key}
- Returns "Response": "True" or "False" for success/failure
- Conservative rate limit: 900/day = ~37/hour = ~1 per 2 minutes

Security:
- API key loaded from OMDB_API_KEY environment variable
- Rate limiting enforced to stay within free tier limits
"""

from typing import Any

import httpx

from namegnome_serve.metadata.providers.base import BaseProvider, ProviderError


class OMDbProvider(BaseProvider):
    """OMDb provider for movies (fallback for TMDB)."""

    BASE_URL = "http://www.omdbapi.com/"

    def __init__(self) -> None:
        """Initialize OMDb provider."""
        super().__init__(
            provider_name="OMDb",
            api_key_env_var="OMDB_API_KEY",
            rate_limit_per_minute=1,  # Conservative: ~900/day = 1 per ~2 minutes
            max_retries=3,
        )

        # httpx async client
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search for movies by title.

        Args:
            query: Movie title to search
            **kwargs: Optional 'year' for filtering

        Returns:
            List of search results
        """

        async def _do_search() -> list[dict[str, Any]]:
            return await self.search_movie(query, year=kwargs.get("year"))

        return await self._execute_with_retry(_do_search, "search")

    async def get_details(self, entity_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Get movie details by IMDb ID.

        Args:
            entity_id: IMDb ID (e.g., "tt3521164")
            **kwargs: Unused for OMDb

        Returns:
            Movie details or None if not found
        """

        async def _do_get_details() -> dict[str, Any] | None:
            return await self.get_movie_details(entity_id)

        return await self._execute_with_retry(_do_get_details, "get_details")

    async def search_movie(
        self, title: str, year: int | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Search for movies by title and optional year.

        Args:
            title: Movie title to search
            year: Optional release year
            limit: Optional maximum number of results to return

        Returns:
            List of matching movies
        """
        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        params: dict[str, Any] = {"apikey": self._api_key, "s": title, "type": "movie"}

        if year:
            params["y"] = str(year)

        try:
            response = await self._client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()

            # OMDb returns "Response": "True" or "False"
            if data.get("Response") == "True":
                results: list[dict[str, Any]] = data.get("Search", [])
                if limit is not None:
                    return results[:limit]
                return results
            else:
                # No results or error
                return []

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise ProviderError(f"OMDb search failed: {e}") from e

    async def get_movie_details(self, imdb_id: str) -> dict[str, Any] | None:
        """Get detailed movie information by IMDb ID.

        Args:
            imdb_id: IMDb ID (e.g., "tt3521164")

        Returns:
            Movie details with normalized rating, or None if not found
        """
        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        params = {"apikey": self._api_key, "i": imdb_id, "plot": "full"}

        try:
            response = await self._client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()

            # OMDb returns "Response": "True" or "False"
            if data.get("Response") == "True":
                # Add normalized rating
                imdb_rating = data.get("imdbRating")
                data["imdb_rating_normalized"] = self._normalize_rating(imdb_rating)
                return data
            else:
                # Not found
                return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise ProviderError(f"OMDb get_movie_details failed: {e}") from e

    def _normalize_rating(self, rating: str | None) -> float:
        """Normalize IMDb rating (0-10) to 0-1 scale.

        Args:
            rating: IMDb rating string (e.g., "7.6", "N/A")

        Returns:
            Normalized rating (0-1)
        """
        if not rating or rating == "N/A":
            return 0.0

        try:
            value = float(rating)
            # Clamp to 0-10 range
            value = max(0.0, min(10.0, value))
            return round(value / 10.0, 2)
        except (ValueError, TypeError):
            return 0.0

    async def __aenter__(self) -> "OMDbProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - close client."""
        await self._client.aclose()
