"""Pydantic schemas for the scan/plan/apply pipeline.

These schemas define the data structures used throughout the NameGnome Serve API:
- ScanResult: Output from the scan phase
- PlanItem: Individual rename operation in a plan
- ApplyResult: Results from executing a plan

All schemas use Pydantic v2 for validation and serialization.
"""

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class EpisodeSegment(BaseModel):
    """Segment metadata for anthology-aware TV parsing."""

    start: int | None = None
    end: int | None = None
    title_tokens: list[str] = Field(default_factory=list)
    raw_span: str | None = None
    source: Literal["filename", "dirname", "both", "unknown"] = "unknown"

    @model_validator(mode="after")
    def validate_bounds(self) -> "EpisodeSegment":
        if (
            isinstance(self.start, int)
            and isinstance(self.end, int)
            and self.end < self.start
        ):
            raise ValueError("segment end cannot be less than start")
        return self


class ConfidenceLevel(str, Enum):
    """Confidence level for LLM-assisted matching operations.

    Attributes:
        HIGH: High confidence match (>= 0.75)
        MEDIUM: Medium confidence match (0.40 - 0.74)
        LOW: Low confidence match (< 0.40)
        NONE: No LLM matching attempted (deterministic only)
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class SourceRef(BaseModel):
    """Reference to an external metadata provider entity.

    Attributes:
        provider: Name of the metadata provider (tmdb, tvdb, musicbrainz, etc.)
        id: Provider-specific entity ID
    """

    provider: Literal[
        "tmdb",
        "tvdb",
        "musicbrainz",
        "anilist",
        "omdb",
        "theaudiodb",
        "tvmaze",
    ]
    id: str

    model_config = {"frozen": True}


class MediaFile(BaseModel):
    """Metadata for a single media file discovered during scan.

    Attributes:
        path: Absolute or relative path to the file
        size: File size in bytes
        hash: Optional SHA-256 hash (if --with-hash enabled)
        parsed_title: Extracted show/movie/track name
        parsed_season: Season number (TV only)
        parsed_episode: Episode number (TV only)
        parsed_year: Year (movies/music)
        parsed_track: Track number (music only)
        parsed_artist: Artist name (music only)
        parsed_album: Album name (music only)
        needs_disambiguation: True if multiple provider matches possible
        anthology_candidate: True if file may contain multiple episodes
    """

    path: Path
    size: int
    hash: str | None = None
    parsed_title: str | None = None
    parsed_season: int | None = None
    parsed_episode: int | None = None
    parsed_year: int | None = None
    parsed_track: int | None = None
    parsed_artist: str | None = None
    parsed_album: str | None = None
    needs_disambiguation: bool = False
    anthology_candidate: bool = False
    segments: list[EpisodeSegment] = Field(default_factory=list)

    @field_serializer("path")
    def serialize_path(self, path: Path) -> str:
        """Serialize Path to string for JSON."""
        return str(path)


class ScanResult(BaseModel):
    """Results from scanning a directory tree for media files.

    Attributes:
        root_path: Root directory that was scanned
        media_type: Type of media ('tv', 'movie', or 'music')
        files: List of discovered media files with metadata
        total_size: Total size of all files in bytes
        file_count: Number of files discovered
    """

    root_path: Path
    media_type: Literal["tv", "movie", "music"]
    files: list[MediaFile]
    total_size: int
    file_count: int

    @field_serializer("root_path")
    def serialize_root_path(self, root_path: Path) -> str:
        """Serialize Path to string for JSON."""
        return str(root_path)


class PlanItem(BaseModel):
    """A single planned rename operation.

    Attributes:
        src_path: Current file path
        dst_path: Target file path after rename
        reason: Human-readable explanation for this rename
        confidence: Confidence score (0.0 - 1.0) for this match
        sources: List of provider references used for this match
        warnings: List of warnings or caveats about this rename
    """

    src_path: Path
    dst_path: Path
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[SourceRef]
    warnings: list[str] = Field(default_factory=list)

    @field_serializer("src_path", "dst_path")
    def serialize_paths(self, path: Path) -> str:
        """Serialize Path to string for JSON."""
        return str(path)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v


class RenameOutcome(BaseModel):
    """Result of a single rename operation.

    Attributes:
        src_path: Original file path
        dst_path: Target file path
        status: Operation status ('success', 'failed', or 'skipped')
        error: Error message if status is 'failed' or 'skipped'
    """

    src_path: Path
    dst_path: Path
    status: Literal["success", "failed", "skipped"]
    error: str | None = None

    @field_serializer("src_path", "dst_path")
    def serialize_paths(self, path: Path) -> str:
        """Serialize Path to string for JSON."""
        return str(path)


class ApplyResult(BaseModel):
    """Results from applying a rename plan.

    Attributes:
        outcomes: List of individual rename outcomes
        successful_count: Number of successful renames
        failed_count: Number of failed renames
        skipped_count: Number of skipped renames
        rollback_token: Token to use for rollback/undo operation
    """

    outcomes: list[RenameOutcome]
    successful_count: int
    failed_count: int
    skipped_count: int
    rollback_token: str | None = None
