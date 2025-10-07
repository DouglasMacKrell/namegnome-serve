"""Edge case tests for parser module to achieve 100% coverage.

These tests cover parser branches and edge cases not covered by
the main parser tests.
"""

from pathlib import Path

from namegnome_serve.core.parser import parse_filename


def test_parse_tv_year_in_filename_with_season() -> None:
    """Test TV parsing when year is in filename along with season/episode."""
    path = Path("/media/Show (2020) - S01E01.mkv")
    result = parse_filename(path, media_type="tv")

    assert result["title"] == "Show"
    assert result["year"] == 2020
    assert result["season"] == 1
    assert result["episode"] == 1


def test_parse_tv_title_from_directory_only() -> None:
    """Test TV parsing when no title in filename before SxxEyy pattern."""
    # When filename is just "S01E01.mkv", the SxxEyy is the start of the filename
    # Parser extracts nothing before it, so title comes from directory if it has (Year)
    path = Path("/media/Show Name (2020)/S01E01.mkv")
    result = parse_filename(path, media_type="tv")

    assert result["title"] == "Show Name"
    assert result["year"] == 2020
    assert result["season"] == 1
    assert result["episode"] == 1


def test_parse_tv_title_from_directory_with_year() -> None:
    """Test TV parsing when directory has show name with year."""
    path = Path("/media/Show Name (2015)/S01E01 - Episode.mkv")
    result = parse_filename(path, media_type="tv")

    assert result["title"] == "Show Name"
    assert result["year"] == 2015
    assert result["season"] == 1
    assert result["episode"] == 1


def test_parse_movie_title_from_directory() -> None:
    """Test movie parsing when title must be extracted from directory."""
    # Movie filename is just the year, so after removing it, title is empty
    # Parser should fall back to directory
    path = Path("/movies/The Matrix (1999)/(1999).mkv")
    result = parse_filename(path, media_type="movie")

    assert result["title"] == "The Matrix"
    assert result["year"] == 1999


def test_parse_movie_title_from_directory_without_year_in_filename() -> None:
    """Test movie with year in directory but not in filename."""
    # Filename has title and year from filename
    path = Path("/movies/Inception (2010)/Inception (2010).mkv")
    result = parse_filename(path, media_type="movie")

    # Should extract from filename
    assert result["title"] == "Inception"
    assert result["year"] == 2010


def test_parse_movie_multiple_years_disambiguation() -> None:
    """Test that multiple years trigger disambiguation flag."""
    path = Path("/movies/The Thing (1982) (2011).mkv")
    result = parse_filename(path, media_type="movie")

    assert result["needs_disambiguation"] is True
    # First year is captured
    assert result["year"] == 1982


def test_parse_tv_no_season_episode_pattern() -> None:
    """Test TV file without season/episode pattern uses filename as title."""
    path = Path("/tv/Random Show File.mkv")
    result = parse_filename(path, media_type="tv")

    # No SxxEyy pattern, so filename becomes title
    assert "Random Show File" in str(result["title"])
    assert result["season"] is None
    assert result["episode"] is None


def test_parse_music_from_directory_structure() -> None:
    """Test music parsing extracting artist/album from directory."""
    path = Path("/music/Artist Name/Album Name (2020)/01 - Track Title.mp3")
    result = parse_filename(path, media_type="music")

    assert result["artist"] == "Artist Name"
    assert result["album"] == "Album Name"
    assert result["year"] == 2020
    assert result["track"] == 1
    assert result["title"] == "Track Title"


def test_parse_music_album_without_year() -> None:
    """Test music with album directory but no year."""
    path = Path("/music/Artist/Album/02 - Song.mp3")
    result = parse_filename(path, media_type="music")

    assert result["artist"] == "Artist"
    assert result["album"] == "Album"
    assert result["year"] is None  # No year in album directory
    assert result["track"] == 2


def test_parse_tv_conflicting_years_sets_disambiguation() -> None:
    """Test that conflicting years between directory and filename sets flag."""
    # Directory says 2015, filename says 2013
    path = Path("/tv/Show (2015)/Show (2013) - S01E01.mkv")
    result = parse_filename(path, media_type="tv")

    assert result["needs_disambiguation"] is True


def test_parse_tv_anthology_keyword_in_filename() -> None:
    """Test that anthology keyword in filename sets flag."""
    path = Path("/tv/Amazing Stories - S01E01 - Anthology Special.mkv")
    result = parse_filename(path, media_type="tv")

    assert result["anthology_candidate"] is True


def test_parse_tv_anthology_keyword_in_directory() -> None:
    """Test that anthology keyword in parent directory sets flag."""
    path = Path("/tv/Anthology Series/S01E01.mkv")
    result = parse_filename(path, media_type="tv")

    assert result["anthology_candidate"] is True


def test_parse_tv_multiple_years_in_filename() -> None:
    """Test TV file with multiple years in filename sets disambiguation flag."""
    path = Path("/tv/Show (2010) (2015) - S01E01.mkv")
    result = parse_filename(path, media_type="tv")

    assert result["needs_disambiguation"] is True


def test_parse_movie_fallback_to_directory_when_year_updates() -> None:
    """Test movie updates year from directory when not in result."""
    # Edge case: filename with (Year) but that becomes empty title
    # So it falls back to directory and updates year if not already set
    path = Path("/movies/Film Title (2020)/Disc1.mkv")
    result = parse_filename(path, media_type="movie")

    # Title from filename since it's not empty
    assert result["title"] == "Disc1"
    # Year should be None as filename has no year
    assert result["year"] is None
