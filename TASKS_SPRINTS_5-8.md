<!-- TASKS_SPRINTS_5-8_CLEAN.md | NameGnome Serve | Full, step-by-step tickets for Sprints 5–8 (+ Sprint 6.5) | CLEAN COPY -->

# 📝 TASKS — Sprints 5–8 (+6.5) (Clean Copy)

Follows directly after Sprints 0–4 (see `TASKS_SPRINTS_0-4_CLEAN`).

---

## 🧪 Sprint 5 — Testing & Edge Cases

### 🎯 Goal
Comprehensive tests for anthology mapping, fuzzy matching, and integration stability.

### 🪜 Tickets

#### 🧪 T5-01 — Anthology Regression Suite
- **Goal:** Lock in behavior for tricky anthology cases.
- **Steps:**
  1. Create `tests/data/anthology/` with Paw Patrol–style filenames.
  2. Add expected provider episode lists (JSON fixtures).
  3. Write tests to assert LLM grouping corrections (first→second pass).
- **Done When:** All anthology tests pass deterministically across runs.

#### 🧠 T5-02 — Fuzzy Title Matching Evaluations
- **Goal:** Validate fuzzy matches with controlled misspellings/partial titles.
- **Steps:**
  1. Build misspelling corpus for several shows/movies.
  2. Assert LLM-selected episodes/tracks align with provider adjacency.
  3. Threshold confidence; require manual review below cutoff.
- **Done When:** Fuzzy suite passes and low-confidence paths are flagged.

#### 🔗 T5-03 — Provider Cache Behavior Tests
- **Goal:** Ensure caching reduces API calls and supports offline mode.
- **Steps:**
  1. Seed the cache; run same plan twice; assert reduced network ops.
  2. Simulate offline; assert cached entities still resolve.
- **Done When:** Cache hit rate measurable; offline lookups succeed.

#### 🧩 T5-04 — End-to-End Integration Tests
- **Goal:** Validate scan→plan→apply across mixed media directories.
- **Steps:**
  1. Build mixed library fixtures (TV/Movie/Music).
  2. Run full CLI; verify output names meet MEDIA_CONVENTIONS.
  3. Validate rollback tokens restore original state.
- **Done When:** E2E passes on CI; artifacts/logs stored.

---

## 🧭 Sprint 6 — API Surface & LangServe Routes

### 🎯 Goal
Expose stable REST endpoints with LangServe for Scan/Plan/Apply.

### 🪜 Tickets

#### 🌐 T6-01 — FastAPI App & Health Route
- **Goal:** Bootstrapped app with healthcheck.
- **Steps:**
  1. Create `app.py` with FastAPI instance and `/healthz`.
  2. Wire LangServe for chains: `/scan`, `/plan`, `/apply`.
  3. Add CORS config for local tools.
- **Done When:** `uvicorn` serves and healthcheck returns 200.

#### 🔌 T6-02 — Route Schemas & Validation
- **Goal:** Input/output contracts via Pydantic models.
- **Steps:**
  1. Define request/response models reused from `routes/schemas.py`.
  2. Enforce explicit `media_type` and disambiguation fields.
  3. JSON streaming where applicable.
- **Done When:** Requests with invalid shapes return 422 with helpful messages.

#### 🧵 T6-03 — Streaming Responses & Backpressure
- **Goal:** Stream long-running operations (LLM, scan) to clients.
- **Steps:**
  1. Implement Server-Sent Events (SSE) or chunked transfer for progress.
  2. Integrate with TUI streaming consumers.
- **Done When:** Clients receive progressive updates without timeouts.

**Mockup — SSE event stream (developer view):**
~~~http
event: progress\ndata: {"phase":"scan","files_total":124,"files_scanned":37}\n\n
event: llm_token\ndata: {"phase":"plan","file":"S07E04.mp4","token":"Matching 'Mighty'..."}\n\n
event: warning\ndata: {"phase":"plan","file":"S07E04.mp4","msg":"Low confidence: title truncated"}\n\n
event: done\ndata: {"phase":"plan","items":42}
~~~

#### 🧭 T6-04 — Disambiguation 409 Response & `/disambiguate` Endpoint
- **Goal:** Non-blocking REST disambiguation flow using tokens.
- **Steps:**
  1. On ambiguity, return **409** with `{status:'disambiguation_required', disambiguation_token, candidates[]}`.
  2. Implement `POST /disambiguate { token, choice_id }` to persist and resume planning.
  3. Cache decision under normalized `(title_norm, year, provider)`.
- **Done When:** Client can resolve ambiguity via second call; planning resumes successfully.

#### 🧪 T6-05 — Two-Channel Output: SSE Stream vs Final JSON
- **Goal:** Separate human feedback (SSE) from authoritative plan JSON.
- **Steps:**
  1. Emit SSE `llm_token/progress/warning` events for UI.
  2. Buffer final plan JSON, validate schema, and return as the `/plan` response body.
  3. Add NDJSON “hints” option for advanced clients (optional).
- **Done When:** UIs stream progress while receiving a single, valid JSON document at completion.

---

## 🧭 Sprint 6.5 — MCP Tooling Integration (Cursor)

### 🎯 Goal
Provide a thin MCP client over REST for developer workflows inside Cursor.

### 🪜 Tickets

#### 🧾 T6.5-01 — MCP Spec & Scopes
- **Goal:** Define MCP tool methods and permissions.
- **Steps:**
  1. Document methods: `scan.preview`, `plan.preview`, `plan.explain`, `apply.undo`, `disambiguate.resolve`, `provider.lookup`.
  2. Define payloads and map to REST endpoints.
- **Done When:** MCP spec doc approved and checked into `docs/mcp.md`.

#### 🔌 T6.5-02 — REST Bridge Implementation
- **Goal:** Implement MCP handlers that call our REST API.
- **Steps:**
  1. Implement handlers with error normalization and timeouts.
  2. Add auth/localhost allowances as needed.
- **Done When:** MCP calls succeed end-to-end against local server.

#### 👀 T6.5-03 — Preview & Explain
- **Goal:** Editor-friendly previews and explanations.
- **Steps:**
  1. `scan.preview` returns summarized tree.
  2. `plan.preview` returns grouped rename items.
  3. `plan.explain { item_id }` returns short rationale + deterministic/LLM attribution.
- **Done When:** Cursor panels render previews and explanations clearly.

#### ↩️ T6.5-04 — Undo & Rollback
- **Goal:** Allow quick rollback from the editor.
- **Steps:**
  1. `apply.undo { report_id }` invokes REST rollback.
  2. Show summary in editor and refresh preview.
- **Done When:** Single-click rollback works in Cursor.

#### 🧩 T6.5-05 — Disambiguation via MCP
- **Goal:** Resolve ambiguity from within the editor.
- **Steps:**
  1. `disambiguate.resolve { token, choice_id }` calls REST.
  2. Refresh plan preview on success.
- **Done When:** Disambiguations persist and planning resumes.

#### 🔎 T6.5-06 — Metadata Lookup Tool
- **Goal:** Quick provider queries for debugging.
- **Steps:**
  1. `provider.lookup { type, title, year }` returns candidates.
  2. Present as a list with IDs for copy/paste.
- **Done When:** Developers can fetch provider IDs without leaving the editor.

---

## 🧭 Sprint 7 — CLI → TUI Implementation

### 🎯 Goal
Turn the CLI into a rich TUI with progress, streaming LLM output, and interactive review.

### 🪜 Tickets

#### 🧭 T7-01 — TUI Framework Setup (Rich/Textual)
- **Goal:** Centralized console/TUI renderer.
- **Steps:**
  1. Adopt Rich for tables/spinners/progress; evaluate Textual later for full-screen flows.
  2. Create `cli/ui.py` with helpers: `spinner()`, `progress_bar()`, `status_panel()`.
  3. Ensure non-interactive fallback logs plain text.
- **Done When:** CLI outputs are routed through UI helpers without regressions.

**Mockup — Base layout skeleton:**
~~~text
┌───────────────────────────────────────────────────────────────────────┐
│ NameGnome Serve                                                       │
├───────────────────────────────────────────────────────────────────────┤
│ [SCAN] /Volumes/Media/TV  ▷ files: 0/0  elapsed: 00:00:05             │
│ ──────────────────────────────────────────────── 35% ███████          │
│ Current: Paw Patrol S07E04.mp4                                        │
├───────────────────────────────────────────────────────────────────────┤
│ Status: Waiting for provider lookups… (tmdb)                           │
│ Cache: hits 17 • misses 4 • offline: no                                │
├───────────────────────────────────────────────────────────────────────┤
│ Logs                                                                   │
│ • Connecting to SSE…                                                   │
│ • Received 124 scan items                                              │
│ • Planning: fuzzy match for "Mighty Pups"                              │
└───────────────────────────────────────────────────────────────────────┘
~~~

#### 📊 T7-02 — Progress Bars & Status Panels
- **Goal:** Visible feedback during scan/apply.
- **Steps:**
  1. Progress per directory/file; aggregated totals.
  2. Status panels for provider lookups and cache hits/misses.
  3. Color-coded icons for success/warn/error.
- **Done When:** Long operations show continuous progress; no blank waits.

**Mockup — Scan progress & counters:**
~~~text
[SCAN] /TV/Paw Patrol     files 37/124   dirs 4/12   speed 142 f/s   ETA 00:01:12
██████████░░░░░░░░░░ 31%
Current: S07E04.mp4
~~~

#### 🧠 T7-03 — Stream LLM Reasoning
- **Goal:** Show partial LLM outputs for anthology/fuzzy mapping.
- **Steps:**
  1. Subscribe to LangChain callbacks; stream tokens.
  2. Live panel updates; collapse to final summary on completion.
  3. Truncate very long traces with “expand more”.
- **Done When:** Users can watch progress and never wonder if it’s hung.

**Mockup — Live LLM panel (token stream):**
~~~text
┌ LLM Reasoning ────────────────────────────────────────────────────────┐
| Matching input "Mighty Pups Charged Up…" against provider episodes…   |
| tokens: Mighty ░ Pups ░ Charged ░ Up ░ Pups ░ Vs ░ Three ░ Super…     |
| Suggest groups: [01–02], [03–04], [04–05] (low conf on overlap)       |
| Second pass fix: [01–02], [03], [04–05]                               |
| confidence: 0.72                                                       |
└───────────────────────────────────────────────────────────────────────┘
~~~

#### 🧾 T7-04 — Interactive Plan Review
- **Goal:** Approve/decline per item.
- **Steps:**
  1. Render table: src → dst, confidence, warnings, sources.
  2. Keyboard navigation; select all; filter by warnings < threshold.
  3. Confirm step prints summary and writes approval snapshot.
- **Done When:** Users can approve plans interactively and proceed to APPLY.

**Mockup — Plan review table:**
~~~text
┌───────────────────────────────────────────────────────────────────────────────┐
│ Plan Review (↑↓ navigate • Space select • a=select all • f=filter • Enter)   │
├────┬───────────────────────────────┬────────────────────────────────┬───────┬──┤
│ Sel│ Source                        │ Destination                   │ Conf  │⚠ │
├────┼───────────────────────────────┼────────────────────────────────┼───────┼──┤
│[x] │ Paw Patrol - S07E01-E02.mp4   │ S07E01-E02 - Mighty Pups Save │ 1.00  │  │
│[ ] │ Paw Patrol - S07E03-04.mp4    │ S07E03 - The New Pup          │ 0.68  │!!│
│[x] │ Paw Patrol - S07E04-05.mp4    │ S07E04-05 - Pups Vs Baddies   │ 0.84  │ !│
├────┴───────────────────────────────┴────────────────────────────────┴───────┴──┤
│ Filter: warnings>=medium   (a) Select All   (Enter) Confirm   (q) Cancel      │
└───────────────────────────────────────────────────────────────────────────────┘
~~~

#### 🧪 T7-05 — Error Handling & Resilience
- **Goal:** Friendly failures.
- **Steps:**
  1. Gracefully handle Ctrl-C; cleanup temp files.
  2. Show actionable errors with remediation tips.
  3. Fallback to plain logs in dumb terminals/CI.
- **Done When:** TUI behaves well across terminals and failure modes.

**Mockup — Error panel & recovery action:**
~~~text
┌ ERROR ────────────────────────────────────────────────────────────────┐
| Provider rate-limited (HTTP 429). Retrying in 4s… (attempt 2/5)       |
| Tip: Increase cache TTL or run with --offline if data is already cached|
| Actions: (r)etry now  (o)ffline mode  (q)uit                          |
└───────────────────────────────────────────────────────────────────────┘
~~~

---

## 🧭 Sprint 8 — Polishing & Enhancements

### 🎯 Goal
Tighten caching, offline behavior, and UX; finalize release.

### 🪜 Tickets

#### 🧰 T8-01 — Cache TTL & SWR
- **Goal:** Smart cache lifecycle.
- **Steps:**
  1. TTL per entity type (series vs episode vs movie vs album/track).
  2. Stale-while-revalidate on background thread.
  3. Cache warmers for known libraries.
- **Done When:** Reduced provider calls; fresh data on re-run.

#### 🧑‍💻 T8-02 — Disambiguation UX
- **Goal:** First-class prompts when multiple candidates exist.
- **Steps:**
  1. For `Danger Mouse`, show grid with (year, provider id, artwork if available).
  2. Persist decision to cache to avoid re-asking.
- **Done When:** User disambiguations are remembered and applied.

**Mockup — Disambiguation picker:**
~~~text
Which "Danger Mouse" did you mean?
[1] Danger Mouse (1981)  tmdb:12345
[2] Danger Mouse (2015)  tmdb:67890
Select: _
~~~

#### 🧪 T8-03 — Release Hardening
- **Goal:** Final QA.
- **Steps:**
  1. Run full test matrix; verify coverage ≥ 80%.
  2. Smoke test offline mode.
  3. Produce `CHANGELOG.md` and tag `v0.1.0`.
- **Done When:** CI green; artifacts ready; docs updated.
