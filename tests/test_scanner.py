"""Tests for the recursive file scanner.

Tests for scanning directories to discover media files, filter by extension,
and collect filesystem metadata.
"""

import hashlib
from pathlib import Path

import pytest


@pytest.fixture
def temp_media_tree(tmp_path: Path) -> Path:
    """Create a temporary media directory tree for testing.

    Structure:
        media/
            tv/
                Show Name/
                    Season 01/
                        Show - S01E01.mkv
                        Show - S01E02.mp4
                    Season 02/
                        Show - S02E01.avi
            movies/
                Movie (2023).mkv
                Another Movie (2020).mp4
            music/
                Artist/
                    Album (2020)/
                        01 - Track.mp3
                        02 - Track.flac
            ignored/
                readme.txt
                image.jpg
    """
    # Create TV structure
    tv_dir = tmp_path / "media" / "tv" / "Show Name"
    s01_dir = tv_dir / "Season 01"
    s02_dir = tv_dir / "Season 02"
    s01_dir.mkdir(parents=True)
    s02_dir.mkdir(parents=True)

    (s01_dir / "Show - S01E01.mkv").write_text("fake video content")
    (s01_dir / "Show - S01E02.mp4").write_text("fake video content")
    (s02_dir / "Show - S02E01.avi").write_text("fake video content")

    # Create movie structure
    movies_dir = tmp_path / "media" / "movies"
    movies_dir.mkdir(parents=True)
    (movies_dir / "Movie (2023).mkv").write_text("fake movie content")
    (movies_dir / "Another Movie (2020).mp4").write_text("fake movie content")

    # Create music structure
    music_dir = tmp_path / "media" / "music" / "Artist" / "Album (2020)"
    music_dir.mkdir(parents=True)
    (music_dir / "01 - Track.mp3").write_text("fake audio content")
    (music_dir / "02 - Track.flac").write_text("fake audio content")

    # Create ignored files
    ignored_dir = tmp_path / "media" / "ignored"
    ignored_dir.mkdir(parents=True)
    (ignored_dir / "readme.txt").write_text("readme")
    (ignored_dir / "image.jpg").write_text("fake image")

    return tmp_path / "media"


def test_scanner_import() -> None:
    """Test that scanner module can be imported."""
    from namegnome_serve.core import scanner

    assert scanner is not None


def test_scan_function_exists() -> None:
    """Test that scan function exists with correct signature."""
    from namegnome_serve.core.scanner import scan

    assert callable(scan)


def test_scan_tv_directory(temp_media_tree: Path) -> None:
    """Test scanning TV directory returns correct files."""
    from namegnome_serve.core.scanner import scan

    tv_path = temp_media_tree / "tv"
    result = scan(paths=[tv_path], media_type="tv", with_hash=False)

    # Should find 3 TV files
    assert result.file_count == 3
    assert len(result.files) == 3

    # Should have correct root path
    assert result.root_path == tv_path
    assert result.media_type == "tv"

    # Check file paths are correct
    file_paths = {f.path for f in result.files}
    assert tv_path / "Show Name" / "Season 01" / "Show - S01E01.mkv" in file_paths
    assert tv_path / "Show Name" / "Season 01" / "Show - S01E02.mp4" in file_paths
    assert tv_path / "Show Name" / "Season 02" / "Show - S02E01.avi" in file_paths


def test_scan_movie_directory(temp_media_tree: Path) -> None:
    """Test scanning movie directory returns correct files."""
    from namegnome_serve.core.scanner import scan

    movies_path = temp_media_tree / "movies"
    result = scan(paths=[movies_path], media_type="movie", with_hash=False)

    assert result.file_count == 2
    assert len(result.files) == 2
    assert result.media_type == "movie"

    file_paths = {f.path for f in result.files}
    assert movies_path / "Movie (2023).mkv" in file_paths
    assert movies_path / "Another Movie (2020).mp4" in file_paths


def test_scan_music_directory(temp_media_tree: Path) -> None:
    """Test scanning music directory returns correct files."""
    from namegnome_serve.core.scanner import scan

    music_path = temp_media_tree / "music"
    result = scan(paths=[music_path], media_type="music", with_hash=False)

    assert result.file_count == 2
    assert len(result.files) == 2
    assert result.media_type == "music"

    file_paths = {f.path for f in result.files}
    assert music_path / "Artist" / "Album (2020)" / "01 - Track.mp3" in file_paths
    assert music_path / "Artist" / "Album (2020)" / "02 - Track.flac" in file_paths


def test_scan_filters_by_extension(temp_media_tree: Path) -> None:
    """Test that scan filters files by media type extension."""
    from namegnome_serve.core.scanner import scan

    # Scanning TV should not return music files
    # Note: TV and movie extensions overlap (.mkv, .mp4, .avi), so this will
    # find both TV and movie files. The parser (T2-02) will distinguish them.
    result = scan(paths=[temp_media_tree], media_type="tv", with_hash=False)

    # Should find TV files (3) + movie files (2) = 5, but NOT music (2)
    assert result.file_count == 5

    # Verify no .mp3 or .flac files in results (music extensions)
    for file in result.files:
        assert file.path.suffix not in [".mp3", ".flac"]


def test_scan_collects_file_size(temp_media_tree: Path) -> None:
    """Test that scan collects file size metadata."""
    from namegnome_serve.core.scanner import scan

    tv_path = temp_media_tree / "tv"
    result = scan(paths=[tv_path], media_type="tv", with_hash=False)

    # All files should have size > 0
    for file in result.files:
        assert file.size > 0

    # Total size should be sum of file sizes
    total = sum(f.size for f in result.files)
    assert result.total_size == total


def test_scan_without_hash(temp_media_tree: Path) -> None:
    """Test that scan without hash flag doesn't compute hashes."""
    from namegnome_serve.core.scanner import scan

    tv_path = temp_media_tree / "tv"
    result = scan(paths=[tv_path], media_type="tv", with_hash=False)

    # All files should have None for hash
    for file in result.files:
        assert file.hash is None


def test_scan_with_hash(temp_media_tree: Path) -> None:
    """Test that scan with hash flag computes SHA-256 hashes."""
    from namegnome_serve.core.scanner import scan

    tv_path = temp_media_tree / "tv"
    result = scan(paths=[tv_path], media_type="tv", with_hash=True)

    # All files should have a hash value
    for file in result.files:
        assert file.hash is not None
        assert len(file.hash) == 64  # SHA-256 hex digest length

    # Verify hash is actually correct for one file
    test_file = tv_path / "Show Name" / "Season 01" / "Show - S01E01.mkv"
    expected_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()

    matching_file = next(f for f in result.files if f.path == test_file)
    assert matching_file.hash == expected_hash


def test_scan_multiple_paths(temp_media_tree: Path) -> None:
    """Test scanning multiple paths at once."""
    from namegnome_serve.core.scanner import scan

    tv_path = temp_media_tree / "tv"
    movies_path = temp_media_tree / "movies"

    # Scan both TV and movies as movies (should find all .mkv/.mp4/.avi)
    result = scan(paths=[tv_path, movies_path], media_type="movie", with_hash=False)

    # Should find: 3 TV files + 2 movie files = 5 total
    assert result.file_count == 5


def test_scan_empty_directory(tmp_path: Path) -> None:
    """Test scanning an empty directory."""
    from namegnome_serve.core.scanner import scan

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = scan(paths=[empty_dir], media_type="tv", with_hash=False)

    assert result.file_count == 0
    assert len(result.files) == 0
    assert result.total_size == 0


def test_scan_nonexistent_path() -> None:
    """Test scanning a nonexistent path raises appropriate error."""
    from namegnome_serve.core.scanner import scan

    fake_path = Path("/nonexistent/path/to/media")

    with pytest.raises((FileNotFoundError, ValueError)):
        scan(paths=[fake_path], media_type="tv", with_hash=False)


def test_scan_ignores_hidden_files(tmp_path: Path) -> None:
    """Test that scan ignores hidden files (starting with .)."""
    from namegnome_serve.core.scanner import scan

    media_dir = tmp_path / "media"
    media_dir.mkdir()

    # Create regular and hidden files
    (media_dir / "show.mkv").write_text("content")
    (media_dir / ".hidden.mkv").write_text("content")
    (media_dir / ".DS_Store").write_text("content")

    result = scan(paths=[media_dir], media_type="tv", with_hash=False)

    # Should only find the non-hidden file
    assert result.file_count == 1
    assert result.files[0].path.name == "show.mkv"


def test_scan_result_immutability() -> None:
    """Test that ScanResult is properly structured."""
    from namegnome_serve.routes.schemas import ScanResult

    # Should be able to create a ScanResult
    result = ScanResult(
        root_path=Path("/media"),
        media_type="tv",
        files=[],
        total_size=0,
        file_count=0,
    )

    assert result.media_type == "tv"
    assert result.file_count == 0
