"""AniDB provider for anime metadata (fallback for TVDB).

AniDB specifics:
- Requires API key (client registration required)
- VERY STRICT rate limits: 1 request per 2 seconds
- XML-based API: http://api.anidb.net:9001/httpapi
- Anime details: ?request=anime&aid={anime_id}&client={client}
  &clientver={ver}&protover=1
- Client name and version REQUIRED
- No text search support (requires anime ID)

Security:
- API key loaded from ANIDB_API_KEY environment variable
- STRICT rate limiting enforced (30 req/min = 1 per 2 seconds)
- Client identification required
"""

import xml.etree.ElementTree as ET
from typing import Any

import httpx

from namegnome_serve.metadata.providers.base import BaseProvider, ProviderError


class AniDBProvider(BaseProvider):
    """AniDB provider for anime metadata (fallback for TVDB)."""

    BASE_URL = "http://api.anidb.net:9001/httpapi"
    CLIENT_NAME = "namegnomeserve"
    CLIENT_VERSION = "1"

    def __init__(self) -> None:
        """Initialize AniDB provider."""
        super().__init__(
            provider_name="AniDB",
            api_key_env_var="ANIDB_API_KEY",
            rate_limit_per_minute=30,  # STRICT: 1 per 2 seconds
            max_retries=3,
        )

        # httpx async client
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search is not supported by AniDB API (requires anime ID).

        Raises:
            NotImplementedError: AniDB doesn't support text search
        """
        raise NotImplementedError(
            "AniDB API does not support text search. "
            "Use get_anime_details() with a known anime ID."
        )

    async def get_details(self, entity_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Get anime details by AniDB ID.

        Args:
            entity_id: AniDB anime ID
            **kwargs: Unused for AniDB

        Returns:
            Anime details or None if not found
        """
        return await self.get_anime_details(entity_id)

    async def get_anime_details(self, anime_id: str) -> dict[str, Any] | None:
        """Get anime details by AniDB ID.

        Args:
            anime_id: AniDB anime ID

        Returns:
            Anime details dict with title, episode count, rating, or None
        """
        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        params = {
            "request": "anime",
            "client": self.CLIENT_NAME,
            "clientver": self.CLIENT_VERSION,
            "protover": "1",
            "aid": anime_id,
        }

        try:
            response = await self._client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            xml_data = response.text

            # Parse XML response
            root = ET.fromstring(xml_data)

            # Extract relevant fields
            details: dict[str, Any] = {}

            # Title (prefer English official, fallback to main)
            titles = root.find("titles")
            if titles is not None:
                english_title = None
                main_title = None
                for title in titles.findall("title"):
                    if (
                        title.get("type") == "official"
                        and title.get("{http://www.w3.org/XML/1998/namespace}lang")
                        == "en"
                    ):
                        english_title = title.text
                    if title.get("type") == "main":
                        main_title = title.text

                details["title"] = english_title or main_title or "Unknown"

            # Episode count
            episode_count = root.find("episodecount")
            if episode_count is not None and episode_count.text:
                details["episode_count"] = int(episode_count.text)

            # Type
            anime_type = root.find("type")
            if anime_type is not None and anime_type.text:
                details["type"] = anime_type.text

            # Dates
            start_date = root.find("startdate")
            if start_date is not None and start_date.text:
                details["start_date"] = start_date.text

            end_date = root.find("enddate")
            if end_date is not None and end_date.text:
                details["end_date"] = end_date.text

            # Rating
            ratings = root.find("ratings")
            if ratings is not None:
                permanent = ratings.find("permanent")
                if permanent is not None and permanent.text:
                    details["rating_normalized"] = self._normalize_rating(
                        permanent.text
                    )

            return details

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise ProviderError(f"AniDB get_anime_details failed: {e}") from e
        except ET.ParseError as e:
            raise ProviderError(f"AniDB XML parse error: {e}") from e

    def _normalize_rating(self, rating: str | None) -> float:
        """Normalize AniDB rating (0-10) to 0-1 scale.

        Args:
            rating: AniDB rating string (e.g., "8.50")

        Returns:
            Normalized rating (0-1)
        """
        if not rating or rating == "":
            return 0.0

        try:
            value = float(rating)
            # Clamp to 0-10 range
            value = max(0.0, min(10.0, value))
            return round(value / 10.0, 2)
        except (ValueError, TypeError):
            return 0.0

    async def __aenter__(self) -> "AniDBProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - close client."""
        await self._client.aclose()
