"""Tests for filename and directory parser.

Tests for extracting metadata from media filenames following MEDIA_CONVENTIONS.md:
- TV: Show Name - SxxEyy - Episode Title
- Movies: Movie Title (Year)
- Music: Track## - Track Title
"""

from pathlib import Path


def test_parser_import() -> None:
    """Test that parser module can be imported."""
    from namegnome_serve.core import parser

    assert parser is not None


def test_parse_filename_exists() -> None:
    """Test that parse_filename function exists."""
    from namegnome_serve.core.parser import parse_filename

    assert callable(parse_filename)


# ============================================================================
# TV Show Parsing Tests
# ============================================================================


def test_parse_tv_single_episode_basic() -> None:
    """Test parsing basic TV episode filename."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("Paw Patrol - S07E04 - Episode Title.mp4")
    result = parse_filename(path, media_type="tv")

    assert result["title"] == "Paw Patrol"
    assert result["season"] == 7
    assert result["episode"] == 4
    assert result["episode_title"] == "Episode Title"


def test_parse_tv_with_year() -> None:
    """Test parsing TV episode with year in show name."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("Show Name (2013)/Season 07/Show Name - S07E04.mp4")
    result = parse_filename(path, media_type="tv")

    assert result["title"] == "Show Name"
    assert result["year"] == 2013
    assert result["season"] == 7
    assert result["episode"] == 4


def test_parse_tv_multi_episode() -> None:
    """Test parsing multi-episode TV file."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("Show - S03E03-E04 - Title1 & Title2.mp4")
    result = parse_filename(path, media_type="tv")

    assert result["title"] == "Show"
    assert result["season"] == 3
    assert result["episode"] == 3  # Start episode
    assert result["episode_end"] == 4  # End episode
    assert "Title1" in result.get("episode_title", "")
    assert "Title2" in result.get("episode_title", "")


def test_parse_tv_various_separators() -> None:
    """Test TV parsing with different separators (dots, underscores)."""
    from namegnome_serve.core.parser import parse_filename

    # Dots as separators
    path1 = Path("Show.Name.S01E05.Episode.Title.mkv")
    result1 = parse_filename(path1, media_type="tv")
    assert result1["title"] == "Show Name"
    assert result1["season"] == 1
    assert result1["episode"] == 5

    # Underscores as separators
    path2 = Path("Show_Name_S01E05_Episode_Title.avi")
    result2 = parse_filename(path2, media_type="tv")
    assert result2["title"] == "Show Name"
    assert result2["season"] == 1
    assert result2["episode"] == 5


def test_parse_tv_no_episode_title() -> None:
    """Test TV parsing when episode title is missing."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("Paw Patrol - S07E04.mp4")
    result = parse_filename(path, media_type="tv")

    assert result["title"] == "Paw Patrol"
    assert result["season"] == 7
    assert result["episode"] == 4
    assert result.get("episode_title") is None or result.get("episode_title") == ""


def test_parse_tv_from_directory_path() -> None:
    """Test extracting show info from directory structure."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("/media/tv/Paw Patrol (2013)/Season 07/S07E04.mp4")
    result = parse_filename(path, media_type="tv")

    # Should extract show name from parent directory
    assert "Paw Patrol" in result["title"] or result["title"] == "Paw Patrol"
    assert result["season"] == 7
    assert result["episode"] == 4


# ============================================================================
# Movie Parsing Tests
# ============================================================================


def test_parse_movie_basic() -> None:
    """Test parsing basic movie filename."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("The Matrix (1999).mkv")
    result = parse_filename(path, media_type="movie")

    assert result["title"] == "The Matrix"
    assert result["year"] == 1999


def test_parse_movie_multi_word_title() -> None:
    """Test parsing movie with multi-word title."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("The Lord of the Rings The Fellowship of the Ring (2001).mkv")
    result = parse_filename(path, media_type="movie")

    assert "Lord of the Rings" in result["title"]
    assert result["year"] == 2001


def test_parse_movie_with_part() -> None:
    """Test parsing multi-part movie."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("Movie Title (2001) - Part 1.mkv")
    result = parse_filename(path, media_type="movie")

    assert result["title"] == "Movie Title"
    assert result["year"] == 2001
    assert result.get("part") == 1


def test_parse_movie_from_directory() -> None:
    """Test extracting movie info from directory structure."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("/media/movies/Danger Mouse (2015)/Danger Mouse (2015).mp4")
    result = parse_filename(path, media_type="movie")

    assert result["title"] == "Danger Mouse"
    assert result["year"] == 2015


def test_parse_movie_with_extra_metadata() -> None:
    """Test movie with extra metadata tags after year."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("The Matrix (1999) - 1080p - BluRay.mkv")
    result = parse_filename(path, media_type="movie")

    assert result["title"] == "The Matrix"
    assert result["year"] == 1999
    # Extra metadata should be ignored


# ============================================================================
# Music Parsing Tests
# ============================================================================


def test_parse_music_basic() -> None:
    """Test parsing basic music track filename."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("01 - Track Title.mp3")
    result = parse_filename(path, media_type="music")

    assert result["track"] == 1
    assert result["title"] == "Track Title"


def test_parse_music_two_digit_track() -> None:
    """Test parsing music with two-digit track number."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("12 - Another Track.flac")
    result = parse_filename(path, media_type="music")

    assert result["track"] == 12
    assert result["title"] == "Another Track"


def test_parse_music_from_directory() -> None:
    """Test extracting music metadata from directory structure."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("Artist Name/Album Title (2020)/03 - Song Title.mp3")
    result = parse_filename(path, media_type="music")

    assert result["track"] == 3
    assert result["title"] == "Song Title"
    # Artist and album could be extracted from directory
    assert result.get("artist") == "Artist Name" or result.get("artist") is None
    assert result.get("album") == "Album Title" or result.get("album") is None
    assert result.get("year") == 2020 or result.get("year") is None


def test_parse_music_without_hyphen() -> None:
    """Test parsing music track without hyphen separator."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("01 Track Title.mp3")
    result = parse_filename(path, media_type="music")

    assert result["track"] == 1
    assert "Track Title" in result["title"]


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


def test_parse_unparseable_filename() -> None:
    """Test handling of unparseable filename."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("random_file_with_no_metadata.mkv")
    result = parse_filename(path, media_type="tv")

    # Should return dict with None/empty values or minimal data
    assert isinstance(result, dict)
    # Title might be extracted as filename without extension
    assert result.get("title") is not None or result.get("season") is None


def test_parse_filename_normalizes_whitespace() -> None:
    """Test that parser normalizes multiple spaces and special chars."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("Show  Name - S01E01 -  Episode   Title.mp4")
    result = parse_filename(path, media_type="tv")

    # Should normalize multiple spaces to single space
    assert result["title"] == "Show Name"
    assert "Episode" in result.get("episode_title", "")


def test_parse_filename_handles_special_characters() -> None:
    """Test parsing filenames with special characters."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("Show's Name - S01E01 - Episode: The Beginning.mp4")
    result = parse_filename(path, media_type="tv")

    assert "Show" in result["title"]
    assert result["season"] == 1
    assert result["episode"] == 1


def test_parse_returns_consistent_structure() -> None:
    """Test that parser always returns expected keys."""
    from namegnome_serve.core.parser import parse_filename

    path = Path("Some File.mkv")
    result = parse_filename(path, media_type="tv")

    # Should always return a dict
    assert isinstance(result, dict)
    # Should have standard keys (may be None)
    assert "title" in result
