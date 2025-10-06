"""Tests for Pydantic schemas used in the scan/plan/apply pipeline.

Following TDD: These tests are written first and will fail until
schemas are implemented.
"""

from pathlib import Path


def test_source_ref_import() -> None:
    """Test that SourceRef can be imported and instantiated."""
    from namegnome_serve.routes.schemas import SourceRef

    source = SourceRef(provider="tmdb", id="12345")
    assert source.provider == "tmdb"
    assert source.id == "12345"


def test_source_ref_validation() -> None:
    """Test that SourceRef validates provider names."""
    from namegnome_serve.routes.schemas import SourceRef

    # Valid providers
    valid_providers = ["tmdb", "tvdb", "musicbrainz", "anilist", "omdb"]
    for provider in valid_providers:
        source = SourceRef(provider=provider, id="123")
        assert source.provider == provider


def test_confidence_level_enum() -> None:
    """Test that ConfidenceLevel enum exists with expected values."""
    from namegnome_serve.routes.schemas import ConfidenceLevel

    # Test enum values exist
    assert ConfidenceLevel.HIGH
    assert ConfidenceLevel.MEDIUM
    assert ConfidenceLevel.LOW
    assert ConfidenceLevel.NONE

    # Test string values
    assert ConfidenceLevel.HIGH.value == "high"
    assert ConfidenceLevel.MEDIUM.value == "medium"
    assert ConfidenceLevel.LOW.value == "low"
    assert ConfidenceLevel.NONE.value == "none"


def test_scan_result_basic() -> None:
    """Test basic ScanResult schema structure."""
    from namegnome_serve.routes.schemas import ScanResult

    result = ScanResult(
        root_path=Path("/media/tv"),
        media_type="tv",
        files=[],
        total_size=0,
        file_count=0,
    )
    assert result.root_path == Path("/media/tv")
    assert result.media_type == "tv"
    assert result.files == []
    assert result.total_size == 0
    assert result.file_count == 0


def test_scan_result_with_files() -> None:
    """Test ScanResult with file metadata."""
    from namegnome_serve.routes.schemas import MediaFile, ScanResult

    media_file = MediaFile(
        path=Path("/media/tv/show/S01E01.mkv"),
        size=1024000,
        hash=None,
        parsed_title="Show Name",
        parsed_season=1,
        parsed_episode=1,
        needs_disambiguation=False,
        anthology_candidate=False,
    )

    result = ScanResult(
        root_path=Path("/media/tv"),
        media_type="tv",
        files=[media_file],
        total_size=1024000,
        file_count=1,
    )
    assert len(result.files) == 1
    assert result.files[0].path == Path("/media/tv/show/S01E01.mkv")
    assert result.files[0].parsed_season == 1
    assert result.files[0].parsed_episode == 1


def test_media_file_with_hash() -> None:
    """Test MediaFile with optional hash field."""
    from namegnome_serve.routes.schemas import MediaFile

    file = MediaFile(
        path=Path("/media/Movie.mkv"),
        size=5000000,
        hash="abc123def456",
        parsed_title="Movie Title",
        parsed_year=2023,
        needs_disambiguation=True,
        anthology_candidate=False,
    )
    assert file.hash == "abc123def456"
    assert file.parsed_year == 2023
    assert file.needs_disambiguation is True


def test_plan_item_basic() -> None:
    """Test basic PlanItem schema structure."""
    from namegnome_serve.routes.schemas import PlanItem, SourceRef

    source = SourceRef(provider="tmdb", id="67890")

    item = PlanItem(
        src_path=Path("/media/old/file.mkv"),
        dst_path=Path("/media/new/Movie (2023)/Movie (2023).mkv"),
        reason="Matched to TMDB movie",
        confidence=0.95,
        sources=[source],
        warnings=[],
    )
    assert item.src_path == Path("/media/old/file.mkv")
    assert item.dst_path == Path("/media/new/Movie (2023)/Movie (2023).mkv")
    assert item.confidence == 0.95
    assert len(item.sources) == 1
    assert item.sources[0].provider == "tmdb"
    assert item.warnings == []


def test_plan_item_with_warnings() -> None:
    """Test PlanItem with confidence and warnings."""
    from namegnome_serve.routes.schemas import PlanItem, SourceRef

    sources = [
        SourceRef(provider="tvdb", id="12345"),
        SourceRef(provider="tmdb", id="67890"),
    ]

    item = PlanItem(
        src_path=Path("/media/show.mkv"),
        dst_path=Path("/media/Show/Season 01/Show - S01E01.mkv"),
        reason="Fuzzy match with anthology adjustment",
        confidence=0.65,
        sources=sources,
        warnings=["Episode title truncated", "Multiple provider matches"],
    )
    assert item.confidence == 0.65
    assert len(item.sources) == 2
    assert len(item.warnings) == 2
    assert "truncated" in item.warnings[0]


def test_plan_item_json_serialization() -> None:
    """Test that PlanItem can serialize to JSON."""
    from namegnome_serve.routes.schemas import PlanItem, SourceRef

    item = PlanItem(
        src_path=Path("/media/file.mkv"),
        dst_path=Path("/media/new.mkv"),
        reason="Test",
        confidence=1.0,
        sources=[SourceRef(provider="tmdb", id="123")],
        warnings=[],
    )

    # Pydantic v2 uses model_dump for dict conversion
    data = item.model_dump(mode="json")
    assert isinstance(data["src_path"], str)
    assert isinstance(data["dst_path"], str)
    assert data["confidence"] == 1.0


def test_apply_result_basic() -> None:
    """Test basic ApplyResult schema structure."""
    from namegnome_serve.routes.schemas import ApplyResult, RenameOutcome

    outcome = RenameOutcome(
        src_path=Path("/media/old.mkv"),
        dst_path=Path("/media/new.mkv"),
        status="success",
        error=None,
    )

    result = ApplyResult(
        outcomes=[outcome],
        successful_count=1,
        failed_count=0,
        skipped_count=0,
        rollback_token="rollback_20231006_123456",
    )
    assert result.successful_count == 1
    assert result.failed_count == 0
    assert len(result.outcomes) == 1
    assert result.rollback_token is not None


def test_apply_result_with_failures() -> None:
    """Test ApplyResult with failed operations."""
    from namegnome_serve.routes.schemas import ApplyResult, RenameOutcome

    outcomes = [
        RenameOutcome(
            src_path=Path("/media/file1.mkv"),
            dst_path=Path("/media/renamed1.mkv"),
            status="success",
            error=None,
        ),
        RenameOutcome(
            src_path=Path("/media/file2.mkv"),
            dst_path=Path("/media/renamed2.mkv"),
            status="failed",
            error="Destination already exists",
        ),
        RenameOutcome(
            src_path=Path("/media/file3.mkv"),
            dst_path=Path("/media/renamed3.mkv"),
            status="skipped",
            error="Source file modified since scan",
        ),
    ]

    result = ApplyResult(
        outcomes=outcomes,
        successful_count=1,
        failed_count=1,
        skipped_count=1,
        rollback_token="rollback_20231006_123456",
    )
    assert result.successful_count == 1
    assert result.failed_count == 1
    assert result.skipped_count == 1
    assert result.outcomes[1].status == "failed"
    assert "already exists" in result.outcomes[1].error


def test_rename_outcome_status_validation() -> None:
    """Test that RenameOutcome validates status values."""
    from namegnome_serve.routes.schemas import RenameOutcome

    # Valid statuses
    valid_statuses = ["success", "failed", "skipped"]
    for status in valid_statuses:
        outcome = RenameOutcome(
            src_path=Path("/media/file.mkv"),
            dst_path=Path("/media/renamed.mkv"),
            status=status,
            error=None,
        )
        assert outcome.status == status


def test_media_type_validation() -> None:
    """Test that media_type is validated in ScanResult."""
    from namegnome_serve.routes.schemas import ScanResult

    # Valid media types
    valid_types = ["tv", "movie", "music"]
    for media_type in valid_types:
        result = ScanResult(
            root_path=Path("/media"),
            media_type=media_type,
            files=[],
            total_size=0,
            file_count=0,
        )
        assert result.media_type == media_type


def test_schemas_roundtrip() -> None:
    """Test that schemas can roundtrip through JSON."""
    from namegnome_serve.routes.schemas import (
        MediaFile,
        ScanResult,
    )

    # Create a complete ScanResult
    media_file = MediaFile(
        path=Path("/media/show.mkv"),
        size=1024,
        hash="abc123",
        parsed_title="Show",
        parsed_season=1,
        parsed_episode=1,
        needs_disambiguation=False,
        anthology_candidate=False,
    )

    scan_result = ScanResult(
        root_path=Path("/media"),
        media_type="tv",
        files=[media_file],
        total_size=1024,
        file_count=1,
    )

    # Convert to JSON and back
    json_data = scan_result.model_dump(mode="json")
    reconstructed = ScanResult.model_validate(json_data)

    assert reconstructed.root_path == scan_result.root_path
    assert reconstructed.files[0].parsed_title == scan_result.files[0].parsed_title
