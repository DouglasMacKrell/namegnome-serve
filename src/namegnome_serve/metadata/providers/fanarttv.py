"""FanartTV provider for high-quality artwork (posters, logos, backgrounds).

FanartTV specifics:
- Requires API key (free tier available)
- Specialized in high-quality artwork for movies and TV
- Movies: https://webservice.fanart.tv/v3/movies/{tmdb_id}?api_key={key}
- TV: https://webservice.fanart.tv/v3/tv/{tvdb_id}?api_key={key}
- Returns various artwork types: posters, logos, backgrounds, banners
- Language filtering: Prefer English artwork
- Conservative rate limit: 40 req/min (no official limit specified)

Security:
- API key loaded from FANARTTV_API_KEY environment variable
- Rate limiting enforced to be respectful of free tier
"""

from typing import Any

import httpx

from namegnome_serve.metadata.providers.base import BaseProvider, ProviderError


class FanartTVProvider(BaseProvider):
    """FanartTV provider for high-quality artwork (fallback for TMDB/TVDB)."""

    BASE_URL = "https://webservice.fanart.tv/v3"

    def __init__(self) -> None:
        """Initialize FanartTV provider."""
        super().__init__(
            provider_name="FanartTV",
            api_key_env_var="FANARTTV_API_KEY",
            rate_limit_per_minute=40,  # Conservative, no official limit
            max_retries=3,
        )

        # httpx async client
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search is not supported by FanartTV (artwork only).

        Raises:
            NotImplementedError: FanartTV doesn't support search
        """
        raise NotImplementedError(
            "FanartTV is an artwork provider and does not support search. "
            "Use get_movie_artwork() or get_tv_artwork() with known IDs."
        )

    async def get_details(self, entity_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Get artwork by entity ID.

        Args:
            entity_id: TMDB ID (movies) or TVDB ID (TV)
            **kwargs: Must include 'media_type' ('movie' or 'tv')

        Returns:
            Artwork details or None if not found
        """
        media_type = kwargs.get("media_type")
        if media_type == "movie":
            return await self.get_movie_artwork(entity_id)
        elif media_type == "tv":
            return await self.get_tv_artwork(entity_id)
        else:
            raise ValueError(f"Invalid media_type: {media_type}. Use 'movie' or 'tv'.")

    async def get_movie_artwork(self, tmdb_id: str) -> dict[str, Any] | None:
        """Get movie artwork by TMDB ID.

        Args:
            tmdb_id: TMDB movie ID

        Returns:
            Movie artwork dict with posters, logos, backgrounds, or None
        """
        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/movies/{tmdb_id}",
                params={"api_key": self._api_key},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise ProviderError(f"FanartTV get_movie_artwork failed: {e}") from e

    async def get_tv_artwork(self, tvdb_id: str) -> dict[str, Any] | None:
        """Get TV show artwork by TVDB ID.

        Args:
            tvdb_id: TVDB series ID

        Returns:
            TV artwork dict with posters, logos, backgrounds, or None
        """
        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/tv/{tvdb_id}", params={"api_key": self._api_key}
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise ProviderError(f"FanartTV get_tv_artwork failed: {e}") from e

    def _filter_english(
        self, artwork_list: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Filter artwork list to prefer English language.

        Args:
            artwork_list: List of artwork items with 'lang' field

        Returns:
            Best English artwork item, or first item if no English found
        """
        if not artwork_list:
            return None

        # Prefer English
        english = [item for item in artwork_list if item.get("lang") == "en"]
        if english:
            return english[0]

        # Fallback to first available
        return artwork_list[0] if artwork_list else None

    async def __aenter__(self) -> "FanartTVProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - close client."""
        await self._client.aclose()
