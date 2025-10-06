"""Smoke tests to verify package structure and imports."""


def test_imports_core() -> None:
    """Test that core package can be imported."""
    import namegnome_serve.core  # noqa: F401


def test_imports_rules() -> None:
    """Test that rules package can be imported."""
    import namegnome_serve.rules  # noqa: F401


def test_imports_metadata() -> None:
    """Test that metadata package can be imported."""
    import namegnome_serve.metadata  # noqa: F401


def test_imports_cache() -> None:
    """Test that cache package can be imported."""
    import namegnome_serve.cache  # noqa: F401


def test_imports_chains() -> None:
    """Test that chains package can be imported."""
    import namegnome_serve.chains  # noqa: F401


def test_imports_routes() -> None:
    """Test that routes package can be imported."""
    import namegnome_serve.routes  # noqa: F401


def test_imports_mcp() -> None:
    """Test that mcp package can be imported."""
    import namegnome_serve.mcp  # noqa: F401


def test_imports_cli() -> None:
    """Test that cli package can be imported."""
    import namegnome_serve.cli  # noqa: F401


def test_imports_utils() -> None:
    """Test that utils package can be imported."""
    import namegnome_serve.utils  # noqa: F401


def test_sample_fixture(sample_media_files: list[dict[str, str]]) -> None:
    """Test that sample fixtures are available."""
    assert len(sample_media_files) == 3
    assert sample_media_files[0]["media_type"] == "tv"
    assert sample_media_files[1]["media_type"] == "movie"
    assert sample_media_files[2]["media_type"] == "music"
