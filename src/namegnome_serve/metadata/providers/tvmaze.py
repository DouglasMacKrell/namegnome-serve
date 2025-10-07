"""TVMaze provider for free TV metadata lookups."""

from __future__ import annotations

from typing import Any

import httpx

from namegnome_serve.metadata.providers.base import BaseProvider, ProviderError


class TVMazeProvider(BaseProvider):
    """TVMaze API wrapper (no authentication required)."""

    BASE_URL = "https://api.tvmaze.com"

    def __init__(self) -> None:
        super().__init__(
            provider_name="TVMaze",
            api_key_env_var=None,
            rate_limit_per_minute=40,
            max_retries=3,
        )
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=10.0)

    async def search_series(self, name: str) -> list[dict[str, Any]]:
        """Search for a TV series by name."""

        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        async def _do_search() -> list[dict[str, Any]]:
            try:
                response = await self._client.get(
                    f"{self.BASE_URL}/search/shows",
                    params={"q": name},
                )
                response.raise_for_status()
                data = response.json()
                return [entry.get("show", {}) for entry in data if entry.get("show")]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return []
                raise

        return await self._execute_with_retry(_do_search, "search_series")

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Compatibility shim for BaseProvider interface."""
        return await self.search_series(query)

    async def get_details(self, entity_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """TVMaze does not expose a general details endpoint we rely on."""
        return None

    async def get_episode(
        self, series_id: int | str, season: int, episode: int
    ) -> dict[str, Any] | None:
        """Fetch a specific episode by season and episode number."""

        if not self.check_rate_limit():
            raise ProviderError(f"{self.provider_name} rate limit exceeded")

        async def _do_get() -> dict[str, Any] | None:
            try:
                response = await self._client.get(
                    f"{self.BASE_URL}/shows/{series_id}/episodebynumber",
                    params={"season": season, "number": episode},
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                return data
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return None
                raise

        return await self._execute_with_retry(_do_get, "get_episode")

    async def __aenter__(self) -> TVMazeProvider:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._client.aclose()
