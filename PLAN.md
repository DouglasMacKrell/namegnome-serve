<!-- PLAN.md | NameGnome Serve | Last updated: 2025-10-05 -->

# PLAN.md

## 📌 Project Overview

**NameGnome Serve** is a local-first media file renaming service powered by LangChain, LangServe, and Ollama. It exposes structured scan/plan/apply functionality over REST, with optional MCP tool integration for IDEs like Cursor. The goal is to provide reliable, deterministic media renaming and anthology splitting that aligns with provider metadata (TMDB/TVDB/MusicBrainz), ensuring Plex/Jellyfin/Emby match correctly.

---

## 🧭 Core Functions

1. **Scan**  
   - Walk directories recursively.  
   - Detect media files by extension and collect metadata (size, hash, media type, existing name).  
   - Output structured JSON describing each file found.

2. **Plan**  
   - **Determine canonical record** via provider API (TMDB/TVDB/MusicBrainz) using explicit context and parsed directory names.
   - **Disambiguate** titles (e.g., `Danger Mouse (1981)` vs `Danger Mouse (2015)`) by prompting the user if multiple candidates exist.
   - **Map input → provider**:  
     - If **titles exist** in the input, LLM performs **fuzzy matching** against provider episodes/tracks/films and uses **adjacency** to resolve incomplete or misspelled pieces.  
     - If **only numbers** exist, trust numbering (S/E/track or year) and pull titles from the provider response.
   - **Anthology mode (`--anthology`)**: allow ≥1 title per file; LLM maps segments to **contiguous provider episodes** using adjacency; never trust input numbering in anthology mode.
   - Produce proposed rename operations with confidence and warnings for manual review.

3. **Apply**  
   - Execute renames atomically.  
   - Produce a rollback token for undo operations.  
   - Ensure filesystem integrity.

---

## 🧰 Inputs & Outputs

### Inputs
- File or directory path(s)  
- Explicit media type (`tv`, `movie`, `music`)  
- Optional disambiguation hints (title, year, season, provider, provider ID)  
- Optional flags:  
  - `--dry-run`: don't apply changes (preview only)
  - `--with-hash`: compute file hashes during scan  
  - `--skip-anthology`: bypass anthology logic  
  - `--transactional`: stop on first failure and rollback (default)
  - `--continue-on-error`: attempt all renames despite failures
  - `--provider`: `tmdb` | `tvdb` | `musicbrainz` (specify preferred provider)
  - `--offline`: use cached data only; no network calls

### Outputs
- **Scan** → `ScanResult` JSON: list of discovered media files with metadata.  
- **Plan** → `PlanItem[]` with `srcPath`, `dstPath`, `reason`, `confidence`, `warnings[]`, and `sources:[{provider,id}]` pulled from API or cache.  
  - May return **409 Disambiguation Required** with `disambiguation_token` and `candidates[]`
- **Disambiguate** → Resolved choice persisted; planning resumes automatically
- **Apply** → `ApplyResult` with `moved[]`, `skipped[]`, `failed[]`, and a `rollbackToken`.

---

## 🧍 User Responsibilities

- **Declare media type.** The system will not guess media type.  
- **Provide clarifications when prompted.** For ambiguous titles (e.g., duplicate show names across years), the user must choose.  
- **Network access for fresh lookups.** API calls are required for uncached entities; otherwise we fall back to cache + manual review.  
- **Valid paths/permissions.** Ensure provided paths are accessible.

---

## 🌐 API & LLM Constraints

- **External metadata is the source of truth.** We **must** query platforms relied on by Plex (TMDB/TVDB/MusicBrainz) to determine canonical titles, seasons/episodes, years, and numbering. Local heuristics alone are insufficient.  
- **Caching required:** Responses must be cached locally (SQLite or DuckDB) with keyed lookups (provider, entity type, ID or title+year) to avoid repeated requests.  
- **Rate limits & resilience:** Respect provider rate limits; implement backoff/retry and graceful degradation (manual review) on failures.  
- **LLM role is assistive, not authoritative:** The LLM may **fuzz‑match** user/file titles against the API response, propose anthology segment mapping, and explain ambiguity, but it does **not** invent metadata.  
- **Offline mode (best‑effort):** If offline, operate only on previously cached data and require **manual confirmation** for anything not in cache.

---

## 🧠 Design Principles

- **Provider‑first correctness:** Treat TMDB/TVDB/MusicBrainz as the canonical source matched by Plex; file names must align with provider records.  
- **Deterministic first, LLM second:** Rules and provider data drive decisions; the LLM proposes fuzzy matches or anthology splits only where deterministic mapping isn’t possible.  
- **Explicit over implicit:** Require users to state media type (`tv`, `movie`, `music`) and provide clarifying inputs when prompted.  
- **Streaming‑safe JSON:** All chain outputs must be valid JSON that can stream through LangChain/LangServe.  
- **Reversible operations:** Every apply emits a rollback plan.  
- **Domain isolation:** Keep TV/Movie/Music logic separate, even if this duplicates code.

---

## 🌐 API Architecture

### REST Endpoints
- `POST /scan` → `ScanResult` (file discovery with metadata)
- `POST /plan` → `PlanItem[]` or `409 Disambiguation Required`
- `POST /disambiguate` → resume planning after user choice
- `POST /apply` → `ApplyResult` with rollback token
- `GET /healthz` → health check

### Disambiguation Flow (Non-Blocking)
When ambiguity occurs (e.g., multiple shows with same title):
1. `POST /plan` returns **HTTP 409** with:
   ```json
   {
     "status": "disambiguation_required",
     "disambiguation_token": "dsk_8f1c...",
     "field": "show",
     "candidates": [
       {"provider":"tmdb","id":"12345","title":"Danger Mouse","year":1981},
       {"provider":"tmdb","id":"67890","title":"Danger Mouse","year":2015}
     ],
     "suggested": "67890"
   }
   ```
2. Client resolves with `POST /disambiguate { token, choice_id }`
3. Server persists decision to cache; planning resumes
4. Programmatic clients may pre-set choice via query param (e.g., `?tmdb_id=67890`)

### Async Job Model (Optional)
- `POST /plan` → `202 Accepted { job_id }`
- Stream progress via SSE: `GET /jobs/{job_id}/events`
- Poll status: `GET /jobs/{job_id}/status`

### Two-Channel Output
- **SSE Stream:** Human feedback (`llm_token`, `progress`, `warning` events) for UIs
- **Buffered JSON:** Authoritative, schema-validated response (non-streaming)
- Optional NDJSON hints for advanced clients (non-authoritative)

### HTTP Status Codes
- `200 OK` → Successful operation
- `202 Accepted` → Job queued (async mode)
- `207 Multi-Status` → Partial success (apply with failures)
- `409 Conflict` → Disambiguation required
- `422 Unprocessable Entity` → Validation error
- `423 Locked` → Concurrent apply blocked by lock
- `429 Too Many Requests` → Provider rate limit hit

---

## 🔒 Concurrency & Locking

### Concurrent Operations
- **Scan/Plan:** Multiple concurrent requests allowed (read-only)
- **Apply:** Serialized per root directory with locking

### Plan Snapshots
- Each plan binds to an **immutable snapshot** of scan results
- Snapshot includes: hash of file list + mtimes
- Before rename, verify source `inode/path/mtime` match snapshot
- Mark plan as **stale** if filesystem changed since scan

### Apply Locking
- Per-root **file lock**: `.namegnome.lock` in target directory
- **SQLite advisory lock** row in cache database
- If lock exists, return **HTTP 423 Locked** with active job metadata
- Lock released on completion or timeout

### Apply Modes
- **Transactional (default):** Stop on first hard failure; rollback prior renames; return 207 Multi-Status summary
- **Continue-on-error:** Attempt all renames; include successes/failures; provide rollback token for applied subset only
- **Dry-run:** Never mutate filesystem; preview operations only

---

## 💾 Caching Strategy

### SQLite Cache (Default)
- **Choice rationale:** ACID guarantees, portability, standard tooling, simple operations
- **Location:** `~/.namegnome/cache/namegnome.db` or project-local
- **Schema:**
  - `entities` → movies, shows, albums (provider ID, title, year, metadata JSON)
  - `episodes` → TV episode details (series ID, season, episode, title)
  - `tracks` → Music track details (album ID, track number, title, duration)
  - `decisions` → User disambiguation choices (title_norm, year, provider, chosen_id)
- **Indexes:**
  - `(provider, type, id)` → primary lookups
  - `(title_norm, year)` → fuzzy search and duplicate detection

### Cache Lifecycle
- **TTL per entity type:**
  - Series metadata: 30 days
  - Episode lists: 7 days
  - Movies: 30 days
  - Albums/tracks: 30 days
  - Decisions: 90 days (user choices)
- **Stale-while-revalidate:** Background refresh of stale entries on access
- **Offline mode:** Operate on cached data only; require manual confirmation for uncached entities
- **Cache warmers:** Preload seasons/episodes for known libraries (optional)

---

## 📐 Media File Naming Conventions

See [MEDIA_CONVENTIONS.md](./MEDIA_CONVENTIONS.md) for the full naming rules and examples.

---

## 🏗 Planned Architecture

    namegnome-serve/
    ├── src/
    │   └── namegnome_serve/
    │       ├── core/
    │       │   ├── scanner.py
    │       │   ├── fs_ops.py
    │       │   ├── media.py
    │       │   ├── constants.py
    │       │   └── errors.py
    │       ├── rules/
    │       │   ├── tv.py
    │       │   ├── movie.py
    │       │   └── music.py
    │       ├── metadata/
    │       │   └── providers/
    │       │       ├── base.py
    │       │       ├── tmdb.py
    │       │       ├── tvdb.py
    │       │       └── musicbrainz.py
    │       ├── cache/
    │       │   ├── schema.sql
    │       │   └── cache.py
    │       ├── chains/
    │       │   ├── scan_chain.py
    │       │   ├── plan_chain.py
    │       │   └── apply_chain.py
    │       ├── prompts/
    │       │   ├── anthology.schema.json
    │       │   └── anthology_prompt.txt
    │       ├── routes/
    │       │   └── schemas.py
    │       ├── mcp/
    │       │   ├── server.py
    │       │   └── tools.py
    │       ├── cli/
    │       │   └── ui.py
    │       ├── utils/
    │       │   └── debug.py
    │       └── app.py
    └── tests/

### MCP Tools (Cursor Integration)
Thin REST client for IDE workflows. Provides developer-focused tools:
- `scan.preview` → Summarized file tree discovery
- `plan.preview` → Grouped rename items with confidence levels
- `plan.explain` → Rationale for specific rename (deterministic vs LLM attribution)
- `apply.undo` → Quick rollback via rollback token
- `disambiguate.resolve` → Resolve ambiguity from within editor
- `provider.lookup` → Quick metadata queries for debugging (title/year → provider IDs)

**Implementation:** MCP server wraps REST API with normalized errors, timeouts, and localhost-only defaults.


---

## 🚧 Limitations

- LLM performance depends on local hardware. For best results, use `llama3:8b` with q4_K_M quantization on Apple Silicon.  
- The system will not guess media type or disambiguate titles without explicit user input.  
- Anthology splitting is **best‑effort** — complex edge cases may require manual review.  
- Rollback works only within the same filesystem context; moving files between disks may limit undo capabilities.

---

## 🧪 Testing Strategy

- **Unit Tests** for each core module (scanner, media filters, deterministic rules, fs_ops).  
- **Chain Tests** for LangChain Runnables (scan_chain, plan_chain, apply_chain).  
- **Integration Tests** for scan→plan→apply pipeline.  
- **Anthology Eval Suite** with offline JSONL dataset to regression test LLM outputs.  
- **Route Tests** to validate FastAPI + LangServe endpoints and JSON contracts.

---

## 🧭 Future Enhancements

- Advanced anthology resolution workflows and UI for manual split authoring beyond LLM assist.
- Configurable naming conventions per platform (Plex, Jellyfin, Emby) with profiles/templates.
- Web UI for remote library management (currently TUI + MCP only).
- Batch processing queue with priority scheduling for large libraries.
- Integration with media server webhooks (Plex/Jellyfin) for automatic post-import renaming.
- Export audit reports (CSV/JSON) showing all rename operations with timestamps and rationale.
- Plugin system for custom metadata providers and naming rules.