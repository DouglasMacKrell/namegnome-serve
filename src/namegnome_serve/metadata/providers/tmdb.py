"""TMDB (The Movie Database) provider with dual auth and English filtering.

Security:
- Supports both API key (query param) and Bearer token (header)
- Auto-detects auth method by token format
- Never exposes keys in logs/errors

Features:
- English content prioritization (US > en > all)
- Rating normalization (0-10 → 0-1)
- Automatic retry/backoff via BaseProvider
"""

from typing import Any

import httpx

from namegnome_serve.metadata.providers.base import BaseProvider, ProviderError


class TMDBProvider(BaseProvider):
    """TMDB provider for movies with dual authentication support."""

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE = "https://image.tmdb.org/t/p/original"

    def __init__(self) -> None:
        """Initialize TMDB provider with auto-detected auth method."""
        super().__init__(
            provider_name="TMDB",
            api_key_env_var="TMDB_API_KEY",
            rate_limit_per_minute=40,  # Conservative: 40 req/10s = 40 req/min
            max_retries=3,
        )

        # httpx async client (context managed per request)
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=10.0)

    def _get_auth(self) -> tuple[dict[str, str], dict[str, Any]]:
        """Get auth headers and params based on key format.

        Returns:
            (headers, params) tuple for httpx request
        """
        api_key = self.api_key
        if not api_key:
            raise ProviderError("TMDB API key not configured")

        # Detect Bearer token: starts with "eyJ" and length > 100
        is_bearer = api_key.startswith("eyJ") and len(api_key) > 100

        if is_bearer:
            # Use Bearer token in Authorization header
            return {"Authorization": f"Bearer {api_key}"}, {}
        else:
            # Use API key as query parameter
            return {}, {"api_key": api_key, "language": "en-US"}

    def _filter_english_images(
        self, images: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Filter images to prioritize English content.

        Priority: US region > English language > non-English filtered > all

        Args:
            images: List of image dicts from TMDB

        Returns:
            Best English image or None
        """
        if not images:
            return None

        # Priority 1: US region
        us_images = [img for img in images if img.get("iso_3166_1") == "US"]
        if us_images:
            candidates = us_images
        else:
            # Priority 2: English language
            en_images = [img for img in images if img.get("iso_639_1") == "en"]
            if en_images:
                candidates = en_images
            else:
                # Priority 3: Filter out known non-English
                non_english = ["ru", "de", "fr", "es", "it", "pt", "ja", "ko", "zh"]
                candidates = [
                    img
                    for img in images
                    if not any(
                        lang in img.get("file_path", "").lower() for lang in non_english
                    )
                ] or images

        # Select best by vote_average, prefer PNG for logos
        return max(
            candidates,
            key=lambda x: (
                x.get("vote_average", 0),
                x.get("file_path", "").endswith(".png"),
                x.get("iso_3166_1") == "US",
            ),
        )

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search for movies by title.

        Args:
            query: Movie title to search
            **kwargs: Optional 'year' for filtering

        Returns:
            List of search results
        """
        headers, params = self._get_auth()
        params["query"] = query

        if "year" in kwargs:
            params["year"] = kwargs["year"]

        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        async def _do_search() -> list[dict[str, Any]]:
            try:
                response = await self._client.get(
                    f"{self.BASE_URL}/search/movie", headers=headers, params=params
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                results: list[dict[str, Any]] = data.get("results", [])
                return results
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return []
                raise  # Let retry wrapper handle it

        return await self._execute_with_retry(_do_search, "search")

    async def get_details(self, entity_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Alias for get_movie_details for BaseProvider interface."""
        return await self.get_movie_details(int(entity_id))

    async def search_movie(
        self, title: str, year: int | None = None
    ) -> list[dict[str, Any]]:
        """Search for movies by title and optional year."""
        return await self.search(title, year=year)

    async def search_tv(
        self, title: str, year: int | None = None
    ) -> list[dict[str, Any]]:
        """Search for television series by title and optional year."""

        headers, params = self._get_auth()
        params["query"] = title
        if year is not None:
            params["first_air_date_year"] = year

        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        async def _do_search() -> list[dict[str, Any]]:
            try:
                response = await self._client.get(
                    f"{self.BASE_URL}/search/tv", headers=headers, params=params
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                results = data.get("results", [])
                if not isinstance(results, list):
                    return []
                return [dict(item) for item in results]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return []
                raise

        return await self._execute_with_retry(_do_search, "search_tv")

    async def get_tv_episodes(
        self, series_id: int, season: int | None = None
    ) -> list[dict[str, Any]]:
        """Fetch episodes for a TV series.

        Args:
            series_id: TMDB series identifier
            season: Optional season number to limit lookup
        """

        headers, params = self._get_auth()

        async def _fetch_season(season_number: int) -> list[dict[str, Any]]:
            if not self.check_rate_limit():
                raise ProviderError(f"{self.provider_name} rate limit exceeded")

            async def _do_fetch() -> list[dict[str, Any]]:
                response = await self._client.get(
                    f"{self.BASE_URL}/tv/{series_id}/season/{season_number}",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
                episodes = payload.get("episodes", [])
                if not isinstance(episodes, list):
                    return []
                return [dict(item) for item in episodes]

            return await self._execute_with_retry(
                _do_fetch, f"get_tv_episodes:{season_number}"
            )

        if season is not None:
            return await _fetch_season(season)

        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        async def _do_details() -> dict[str, Any]:
            response = await self._client.get(
                f"{self.BASE_URL}/tv/{series_id}", headers=headers, params=params
            )
            response.raise_for_status()
            details_raw = response.json()
            return dict(details_raw)

        details: dict[str, Any] = await self._execute_with_retry(
            _do_details, "get_tv_details"
        )

        episodes: list[dict[str, Any]] = []
        for season_info in details.get("seasons", []):
            season_number = season_info.get("season_number")
            if season_number in (None, 0):
                continue
            try:
                season_episodes = await _fetch_season(season_number)
                episodes.extend(season_episodes)
            except ProviderError:
                continue

        return episodes

    async def get_movie_details(self, movie_id: int) -> dict[str, Any] | None:
        """Get detailed movie information including images.

        Args:
            movie_id: TMDB movie ID

        Returns:
            Movie details with poster_url, logo_url, normalized rating
        """
        headers, params = self._get_auth()

        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        async def _do_get_details() -> dict[str, Any] | None:
            try:
                # Get movie details
                response = await self._client.get(
                    f"{self.BASE_URL}/movie/{movie_id}", headers=headers, params=params
                )
                response.raise_for_status()
                details: dict[str, Any] = response.json()

                # Get images
                if not self.check_rate_limit():
                    raise ProviderError(f"{self.provider_name} rate limit exceeded")

                img_params = params.copy()
                if "api_key" in img_params:
                    img_params["include_image_language"] = "en,en-US,null"

                img_response = await self._client.get(
                    f"{self.BASE_URL}/movie/{movie_id}/images",
                    headers=headers,
                    params=img_params,
                )
                img_response.raise_for_status()
                images: dict[str, Any] = img_response.json()

                # Add best poster
                if images.get("posters"):
                    best_poster = self._filter_english_images(images["posters"])
                    if best_poster:
                        details["poster_url"] = (
                            f"{self.IMAGE_BASE}{best_poster['file_path']}"
                        )

                # Add best logo
                if images.get("logos"):
                    best_logo = self._filter_english_images(images["logos"])
                    if best_logo:
                        details["logo_url"] = (
                            f"{self.IMAGE_BASE}{best_logo['file_path']}"
                        )

                # Normalize rating to 0-1
                vote_avg = details.get("vote_average", 0.0)
                details["vote_average"] = self._normalize_rating(vote_avg)

                return details

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise  # Let retry wrapper handle it

        return await self._execute_with_retry(_do_get_details, "get_movie_details")

    def _normalize_rating(self, rating: float | int | None) -> float:
        """Normalize 0-10 rating to 0-1 range.

        Args:
            rating: Rating on 0-10 scale

        Returns:
            Rating on 0-1 scale, rounded to 2 decimals
        """
        if rating is None:
            return 0.0
        try:
            value = float(rating)
        except (TypeError, ValueError):
            return 0.0

        # Clamp to 0-10 range
        value = max(0.0, min(10.0, value))

        return round(value / 10.0, 2)

    async def __aenter__(self) -> "TMDBProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - close client."""
        await self._client.aclose()
