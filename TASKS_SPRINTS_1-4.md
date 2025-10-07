<!-- TASKS_SPRINTS_1-4.md | NameGome Serve | FULL | Restored + Appended (no deletions) -->

# 📝 TASKS — Sprints 0–4 (Full)

Each ticket includes **Title**, **Goal**, **Steps**, and **Done When** acceptance criteria. Follow in order.
**Note:** To avoid renumber collisions while preserving existing tickets, newly added items are appended with the next numbers.

---

## 🧭 Sprint 0 — Environment & LLM Setup

### 🎯 Goal
Prepare the development environment, set up local LLMs via Ollama, and ensure LangChain/LangServe interop.

### 🪜 Tickets

#### 🧰 T0-01 — Install & Verify Toolchain (Poetry, Python 3.12, Git)
- **Goal:** Baseline dev workstation readiness.
- **Steps:**
  1. Install Python ≥ 3.12 (`pyenv` recommended). Verify with `python --version`.
  2. Install Poetry: `curl -sSL https://install.python-poetry.org | python3 -`.
  3. Ensure `git` is installed and configured (`git --version`).
  4. Configure Poetry to create venvs in project: `poetry config virtualenvs.in-project true`.
  5. Create project folder `namegnome-serve` and `git init`.
- **Done When:** `python --version`, `poetry --version`, `git --version` succeed; repo initialized.

#### 🤖 T0-02 — Install Ollama & Pull Model
- **Goal:** Local LLM available.
- **Steps:**
  1. Install Ollama (macOS DMG or `brew install ollama`).
  2. Start service: `ollama serve` (keep running in a terminal).
  3. Pull model: `ollama pull llama3:8b`.
  4. Test: `ollama run llama3:8b "Say hello"`.
- **Done When:** Model responds locally with a valid output.

#### 🧱 T0-03 — Project Scaffolding with Poetry
- **Goal:** Create Python package and base deps.
- **Steps:**
  1. `poetry init -n`.
  2. `poetry add fastapi pydantic httpx rich structlog anyio uvicorn langchain langserve typer`.
  3. `poetry add --group dev black ruff mypy pytest pytest-cov`.
  4. Create directories: `src/namegnome_serve/{core,rules,metadata,fs,prompts,cli,chains,routes,mcp,utils}` and `tests`.
  5. Add `__init__.py` to each package.
- **Done When:** `poetry run pytest -q` collects without import errors.

#### 🔧 T0-04 — Lint/Type/Test Baseline
- **Goal:** Enforce quality gates from day 1.
- **Steps:**
  1. Configure `pyproject.toml` for `black`, `ruff` (code only), `mypy --strict`.
  2. Add `.gitignore` including `.venv/`, `.ruff_cache/`, etc.
  3. Add pre-commit (optional) or document Poetry commands.
- **Done When:** `poetry run ruff check .`, `poetry run black --check .`, `poetry run mypy .` pass.

#### 🧩 T0-05 — Ollama Modelfile & Profile
- **Goal:** Stable, repeatable local model configuration.
- **Steps:**
  1. Create `models/namegnome/Modelfile` with `FROM llama3:8b` and tuned params (temperature, context window).
  2. `ollama create namegnome -f models/namegnome/Modelfile`.
  3. Smoke test: `ollama run namegnome "You are NameGnome's assistant. Reply 'OK'"`.
- **Done When:** Custom `namegnome` model loads and responds.

#### 🔗 T0-06 — LangChain ↔ Ollama Sanity Check
- **Goal:** Verify LangChain calls local model.
- **Steps:**
  1. Add `scripts/lc_sanity.py` using `ChatOllama` to send a short prompt.
  2. Run `poetry run python scripts/lc_sanity.py`.
- **Done When:** Script prints a coherent response from local LLM.

---

## 🧱 Sprint 1 — Core Project Structure & Utilities

### 🎯 Goal
Lay down the production skeleton, config, and utilities referenced by plan.

### 🪜 Tickets

#### 📁 T1-01 — Directory Layout & Absolute Imports
- **Goal:** Match PLAN architecture and enable clean imports.
- **Steps:**
  1. Ensure `src/namegnome_serve/` subtree exists per PLAN.
  2. Add `src/namegnome_serve/__init__.py` with `__all__` for key modules.
  3. Configure source path if needed; rely on Poetry defaults.
- **Done When:** `from namegnome_serve.core import ...` works in tests.

#### 🧰 T1-02 — Debug Utility (Universal Debug Logging Rule)
- **Goal:** Single debug entrypoint.
- **Steps:**
  1. Create `src/namegnome_serve/utils/debug.py` with `debug(msg: str)` toggled by `NAMEGNOME_DEBUG`.
  2. Replace any `print()` with `debug()` throughout stubs.
- **Done When:** `NAMEGNOME_DEBUG=1` prints; otherwise silent.

#### 🧪 T1-03 — Test Harness & CI Thresholds
- **Goal:** Pytest runnable, 80% coverage threshold placeholder.
- **Steps:**
  1. Add `tests/conftest.py` and smoke tests per package.
  2. Configure `pytest.ini` with `--cov=namegnome_serve --cov-fail-under=80`.
- **Done When:** `poetry run pytest` passes; coverage tracked.

#### 🧾 T1-04 — Schemas & Types (Pydantic v2)
- **Goal:** Shared dataclasses for pipeline.
- **Steps:**
  1. Create `routes/schemas.py` defining `ScanResult`, `PlanItem`, `ApplyResult`, etc.
  2. Include `sources: list[SourceRef]` with `provider` and `id`.
  3. Add `ConfidenceLevel` enum and anthology flags.
- **Done When:** Schemas import cleanly; mypy passes.

#### 🧱 T1-05 — Config & Constants
- **Goal:** Centralize constants (extensions, providers, etc.).
- **Steps:**
  1. Create `core/constants.py` (extensions for tv/movie/music; supported providers).
  2. Create `core/errors.py` for typed exceptions (DisambiguationRequired, ProviderUnavailable).
- **Done When:** Modules compile and are referenced by later tickets.

---

## 🔎 Sprint 2 — SCAN Engine

### 🎯 Goal
Recursive scanner that collects candidate files and parses preliminary metadata using **MEDIA_CONVENTIONS.md**.

### 🪜 Tickets

#### 🔍 T2-01 — Recursive Walker
- **Goal:** Collect file paths + basic fs metadata.
- **Steps:**
  1. Implement `core/scanner.py: scan(paths: list[Path], media_type: Literal['tv','movie','music'], with_hash: bool=False)`.
  2. Filter by allowed extensions from constants.
  3. Capture size, mtime, optional hash when `with_hash`.
- **Done When:** Returns `ScanResult(files=[...])` with entries for sample tree.

#### 🧮 T2-02 — Filename/Directory Parser (Deterministic)
- **Goal:** Extract candidate title/year/season/episode/etc. from names.
- **Steps:**
  1. Implement regexes aligned to MEDIA_CONVENTIONS (TV SxxEyy, Movie (Year), Music Track##).
  2. For TV, collect multi-episode ranges (E01-E02) and mark anthology-possible if title contains anthology terms.
  3. Normalize whitespace/delimiters.
- **Done When:** Parser returns structured fields for fixtures including Paw Patrol examples.

#### 🏷️ T2-03 — Uncertainty Flags & Notes
- **Goal:** Flag ambiguous items for later disambiguation.
- **Steps:**
  1. If multiple candidate years or titles detected, set `needs_disambiguation=True`.
  2. If anthology-suspect, add `anthology_candidate=True`.
- **Done When:** Flags appear in scan output and are asserted in tests.

#### 🧪 T2-04 — Tests for Scanner & Parser
- **Goal:** Coverage for scan paths and tricky filenames.
- **Steps:**
  1. Add fixtures covering single-episode, multi-episode, anthology, movie remakes, and music tracks.
  2. Write tests for each parser branch including failure cases.
- **Done When:** `pytest` passes; coverage ≥ 80% for scanner module.

---

## 🧠 Sprint 3 — PLAN Engine

### 🎯 Goal
Provider-first deterministic mapping with LLM assist for anthology/fuzzy cases.

### 🪜 Tickets

#### 🌐 T3-01 — Provider Client Abstractions (HTTPX + Cache)
- **Goal:** TMDB/TVDB/MusicBrainz lookups with fallback providers for resilience.
- **Steps:**
  1. Create `metadata/providers/base.py` interface; concrete `tmdb.py`, `tvdb.py`, `musicbrainz.py`.
  2. Add fallback providers: `omdb.py` (movies), `fanarttv.py` (artwork), `anidb.py` (anime).
  3. Implement title+year search; fetch series/season/episodes; albums/tracks.
  4. Add local cache (SQLite) keyed by `(provider, type, id | title+year)` with TTL.
  5. Respect rate limits; exponential backoff on 429/5xx.
  6. Fallback chain: TVDB→TVmaze for TV, TMDB→OMDb for movies, FanartTV for missing artwork.
- **Done When:** Known titles resolve to normalized entities from cache when repeated; fallbacks activate on primary failures.

#### 🧮 T3-02 — Deterministic Mapper
- **Goal:** Map scan fields to provider entities without LLM when possible.
- **Steps:**
  1. Resolve entity (movie/show/artist) by exact title + year; prompt user if ambiguous duplicates.
  2. For TV: map S/E numbers to canonical episode titles; for Music: map Track##.
  3. Produce `PlanItem` with `dstPath` built strictly per MEDIA_CONVENTIONS.
- **Done When:** Straightforward inputs yield correct plans with confidence=1.0 and no warnings.

#### 🧠 T3-03 — LLM Fuzzy & Anthology Mapping
- **Goal:** Handle truncated/misspelled titles and anthology multi-episode files.
- **Steps:**
  1. Build a LangChain `Runnable` that takes: parsed file info + provider episode list.
  2. Prompt the LLM to perform fuzzy matching over titles; use **adjacency** rules to group contiguous episodes.
  3. Emit corrected groups (e.g., first pass 01-02,03-04,04-05 → second pass 01-02,03,04-05).
  4. Attach warnings and confidence per group.
- **Done When:** Anthology fixtures map correctly; confidence < 1.0 where ambiguity remains.

#### 📦 T3-04 — Plan Validation & Review JSON
- **Goal:** Human-reviewable plan output.
- **Steps:**
  1. Combine deterministic and LLM results into a single `Plan[]`.
  2. Include `sources[{provider,id}]`, confidence, and warnings.
  3. Serialize to stable JSON for TUI/CLI consumption.
- **Acceptance Criteria (contract)**
  1. Introduce **`PlanReview`** wrapper that normalizes the output for review.
  2. Merge policy: prefer **deterministic** when non-ambiguous; use **LLM** for ambiguous cases; if both exist for the same source segment, keep **higher confidence** (Δ ≥ 0.1) else prefer deterministic and store the other in `alternatives[]` with warning `tie_breaker_deterministic_preferred`.
  3. Provide **stable ordering** and **grouping**:
    i. `items[]` ordered by `src.path` (case-insensitive, natural sort). Within a group: TV `(season, episode)`; Movies `(year, title)`; Music `(disc, track)`.
    ii. `groups[]` cluster items by source file path with `rollup` metrics.
  4. Include **summary** buckets (`by_origin`, `by_confidence`, counts, warnings, anthology/disambiguation counters).
  5. **Confidence buckets**: `high ≥ 0.90`, `medium ≥ 0.70`, else `low`.
  6. **Schema stability**: include `schema_version: "1.0"`; timestamps in **UTC ISO-8601** ending with `Z`; no string "null"; optional fields omitted or `null`.
  7. Tests must assert **ordering**, **bucket counts**, **merge behavior**, and **byte-stable JSON** (excluding `generated_at`).

---

- 🧩 **Minimal Pydantic Model Sketch (optional)**
  ```python
  from pydantic import BaseModel
  from typing import List, Literal, Optional, Dict, Any
  from datetime import datetime

  Origin = Literal["deterministic","llm"]
  Bucket = Literal["high","medium","low"]
  MediaType = Literal["tv","movie","music"]

  class SourceRef(BaseModel):
      provider: str
      id: str
      type: str

  class EpisodeInfo(BaseModel):
      season: int
      episodes: List[int]
      titles: List[str] = []
      sort_index: List[int]

  class DstInfo(BaseModel):
      path: str
      episode: Optional[EpisodeInfo] = None
      movie: Optional[Dict[str, Any]] = None
      track: Optional[Dict[str, Any]] = None

  class AltItem(BaseModel):
      origin: Origin
      confidence: float
      dst: DstInfo
      reason: Optional[str] = None

  class PlanItem(BaseModel):
      id: str
      origin: Origin
      confidence: float
      confidence_bucket: Bucket
      src: Dict[str, Any]   # { path, segment{...} }
      dst: DstInfo
      sources: List[SourceRef] = []
      warnings: List[str] = []
      anthology: bool = False
      disambiguation: Optional[Dict[str, Any]] = None
      alternatives: List[AltItem] = []
      explain: Optional[Dict[str, str]] = None

  class GroupRollup(BaseModel):
      count: int
      confidence_min: float
      confidence_max: float
      warnings: List[str] = []

  class PlanGroup(BaseModel):
      group_key: str
      src_file: Dict[str, Any]  # path,size,mtime,hash
      items: List[PlanItem]
      rollup: GroupRollup

  class Summary(BaseModel):
      total_items: int
      by_origin: Dict[str, int]
      by_confidence: Dict[str, int]
      warnings: int
      anthology_candidates: int
      disambiguations_required: int

  class PlanReview(BaseModel):
      plan_id: str
      schema_version: str
      generated_at: datetime
      scan_id: Optional[str] = None
      source_fingerprint: Optional[str] = None
      media_type: MediaType
      summary: Summary
      groups: List[PlanGroup]
      items: List[PlanItem]
      notes: List[str] = []
  ````

---

- **Done When:** Plans render cleanly and round-trip through JSON schema tests.

#### 🧰 T3-05 — SQLite Cache Schema & Migrations (Decision)
- **Goal:** Establish SQLite as the default cache backend with schema and migration scaffolding.
- **Steps:**
  1. Create `cache/schema.sql` defining tables for `entities`, `episodes`, `tracks`, and `decisions`.
  2. Include indices on `(provider, type, id)` and `(title_norm, year)`.
  3. Implement migration runner (simple versioned migrations, e.g., manual SQL or lightweight tool).
  4. Wire schema init into CLI bootstrap.
- **Done When:** `namegnome.db` initializes and migrations apply without errors.

#### 🧩 T3-06 — Deterministic Anthology Interval Simplification (Pre-LLM)
- **Goal:** Deterministic second-pass refinement for anthology grouping before invoking LLM.
- **Steps:**
  1. Convert episode groups to closed intervals and detect overlaps/gaps.
  2. Resolve overlaps deterministically (e.g., `03–04` + `04–05` → `03`, `04–05`).
  3. Collapse singleton title matches to single episodes where applicable.
  4. Flag ambiguous cases (gaps/unresolved overlaps) for LLM handoff.
  5. Unit tests with Paw Patrol edge cases.
- **Done When:** Deterministic corrections handle the majority of cases; LLM only for leftovers.

---

## 🚀 Sprint 4 — APPLY Engine

### 🎯 Goal
Atomic filesystem operations with rollback and robust logging.

### 🪜 Tickets

#### 🗂️ T4-01 — Atomic Rename & Rollback Manifest
- **Goal:** Safe rename/move with undo capability.
- **Steps:**
  1. Implement `fs/fs_ops.py` with atomic `rename_with_rollback(src,dst,manifest)`.
  2. Write rollback serializer capturing original paths.
  3. Handle collisions (existing targets) via strategy: skip/overwrite/backup.
- **Done When:** Renames apply and a rollback file is emitted for each run.

#### 📜 T4-02 — Apply Chain + Logs
- **Goal:** Orchestrate apply with structured logs.
- **Steps:**
  1. Create `chains/apply_chain.py` to iterate `PlanItem`s and call fs ops.
  2. Log success/skip/error with Rich/structlog; expose summary JSON.
  3. Unit tests simulate failures and assert rollback integrity.
- **Done When:** Apply succeeds on happy path and fails gracefully with actionable logs.

#### 🧪 T4-03 — Integration Test: scan→plan→apply
- **Goal:** Ensure end-to-end pipeline correctness.
- **Steps:**
  1. Build sample media tree with edge cases (anthology, remakes, music tracks).
  2. Execute full pipeline via CLI entrypoint.
  3. Assert final paths match MEDIA_CONVENTIONS and rollback works.
- **Done When:** E2E tests pass and produce expected filenames.

#### 🔒 T4-04 — Exclusive Locking & Optimistic Checks for Concurrent Apply
- **Goal:** Prevent concurrent mutations and race conditions during apply.
- **Steps:**
  1. Implement a per-root **file lock** (e.g., `.namegnome.lock`) and a **SQLite advisory lock** row.
  2. If lock exists, return 423 Locked with active job metadata.
  3. Before rename, verify source inode/path/mtime match the plan snapshot; mark stale if changed.
- **Done When:** Competing applies are blocked; stale plans are detected and skipped safely.

#### 🧯 T4-05 — Apply Modes: Transactional vs Continue-on-Error
- **Goal:** Robust partial failure handling with clear guarantees.
- **Steps:**
  1. Implement **transactional** mode: stop on first hard failure and rollback prior renames.
  2. Implement **continue-on-error** mode: attempt all, emit rollback token for successes only.
  3. Extend summary payloads (207 Multi-Status) and add tests for both modes.
- **Done When:** Both modes behave as specified with comprehensive tests.
