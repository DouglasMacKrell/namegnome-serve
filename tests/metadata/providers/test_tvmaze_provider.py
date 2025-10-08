"""Tests for TVMaze provider integration (no auth required)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_tvmaze_search_series_returns_shows() -> None:
    """Search should unwrap show payloads and honor query parameter."""

    from namegnome_serve.metadata.providers.tvmaze import TVMazeProvider

    provider = TVMazeProvider()

    mock_response = AsyncMock()
    mock_response.json = Mock(
        return_value=[
            {"score": 1.0, "show": {"id": 42, "name": "Firebuds", "premiered": "2022"}},
            {"score": 0.9, "show": {"id": 84, "name": "Firebug", "premiered": None}},
        ]
    )
    mock_response.raise_for_status = Mock()

    with patch.object(provider._client, "get", return_value=mock_response) as mock_get:
        results = await provider.search_series("Firebuds")

    assert results == [
        {"id": 42, "name": "Firebuds", "premiered": "2022"},
        {"id": 84, "name": "Firebug", "premiered": None},
    ]
    mock_get.assert_called_once()
    url = mock_get.call_args.args[0]
    params = mock_get.call_args.kwargs["params"]
    assert url.endswith("/search/shows")
    assert params == {"q": "Firebuds"}


@pytest.mark.asyncio
async def test_tvmaze_search_alias_calls_series_search() -> None:
    """Generic search should delegate to search_series."""

    from namegnome_serve.metadata.providers.tvmaze import TVMazeProvider

    provider = TVMazeProvider()
    provider.search_series = AsyncMock(return_value=[{"id": 1}])  # type: ignore[attr-defined]

    results = await provider.search("Alias")

    assert results == [{"id": 1}]
    provider.search_series.assert_awaited_once_with("Alias")


@pytest.mark.asyncio
async def test_tvmaze_get_episode_returns_payload() -> None:
    """Episode lookup should fetch by season/number and return JSON body."""

    from namegnome_serve.metadata.providers.tvmaze import TVMazeProvider

    provider = TVMazeProvider()

    mock_response = AsyncMock()
    payload = {
        "id": 999,
        "name": "Pilot",
        "season": 1,
        "number": 1,
    }
    mock_response.json = Mock(return_value=payload)
    mock_response.raise_for_status = Mock()

    with patch.object(provider._client, "get", return_value=mock_response) as mock_get:
        episode = await provider.get_episode(42, season=1, episode=1)

    assert episode == payload
    mock_get.assert_called_once()
    url = mock_get.call_args.args[0]
    params = mock_get.call_args.kwargs["params"]
    assert url.endswith("/shows/42/episodebynumber")
    assert params == {"season": 1, "number": 1}


@pytest.mark.asyncio
async def test_tvmaze_get_episode_handles_not_found() -> None:
    """404 responses should yield None for missing episodes."""

    from namegnome_serve.metadata.providers.tvmaze import TVMazeProvider

    provider = TVMazeProvider()

    mock_response = AsyncMock()
    request = httpx.Request("GET", "https://api.tvmaze.com/shows/42/episodebynumber")
    response_obj = httpx.Response(404, request=request)
    mock_response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "Not found",
            request=request,
            response=response_obj,
        )
    )

    with patch.object(provider._client, "get", return_value=mock_response):
        episode = await provider.get_episode(42, season=99, episode=1)

    assert episode is None
