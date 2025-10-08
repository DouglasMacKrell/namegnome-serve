# Design Clarifications (Cursor Q&A) — NameGnome Serve

This document answers concerns and questions raised during assessment.

---

## 1) Disambiguation UX in a REST Context

**Decision:** Non-blocking flow using a **409 Conflict** with a **disambiguation token**, followed by a separate **/disambiguate** call.

- `/plan` never blocks waiting for user input.
- On ambiguity (e.g., `Danger Mouse` 1981 vs 2015), return:

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
````

* Client resolves by calling `POST /disambiguate { token, choice_id }`.
* Server persists decision in cache and resumes planning.
* For programmatic clients, allow query params (e.g., `?tmdb_id=67890`).
* **Optional job model:** `POST /plan` → `202 { job_id }`; stream progress via SSE `/jobs/{job_id}/events`.

**Tickets:** T6-04 added to Sprint 6.

---

## 2) Cache Implementation Choice

**Decision:** Use **SQLite** as the default cache (ACID, tooling, portability).

* Tables: `entities`, `episodes`, `tracks`, `decisions`.
* Indexes: `(provider, type, id)` and `(title_norm, year)`.
* Future analytics: export or mirror into DuckDB if needed.

**Tickets:** T3-05 (SQLite schema & migrations) added to Sprint 3.

---

## 3) Anthology Multi-Pass Algorithm

**Decision:** Deterministic first, then LLM only if needed.

* **First pass:** parse declared ranges and titles.
* **Trigger second pass:** if overlaps, gaps, or low confidence.
* **Deterministic second pass:**

  * Convert groups to integer intervals, sort, check adjacency.
  * Resolve overlap boundaries (e.g., `03-04` & `04-05` → `03`, `04-05`).
  * Collapse to singletons when titles indicate a single canonical episode.
  * Implemented via `core/anthology.py::interval_simplify`, which consumes
    scanner-produced `segments` and TVDB episode lists before falling back to the
    LangChain runnable.
* **LLM assist:** only when ambiguity remains; supply provider episode list and first-pass groups; require JSON schema output.

**Tickets:** T3-06 added to Sprint 3.

---

## 4) Concurrent Request Handling

**Decision:** Allow concurrent **scan/plan**; serialize **apply** with locking and optimistic checks.

* **Scan/Plan:** read-only; bind plan to an immutable scan snapshot (hash of list+mtimes).
* **Apply:**

  * Per-root exclusive **file lock** + **SQLite advisory lock**.
  * If locked, return **423 Locked** with active job metadata.
  * Before each rename, verify inode/path/mtime matches plan snapshot; mark stale otherwise.

**Tickets:** T4-04 appended to Sprint 4.

---

## 5) Partial Failure Handling

**Decision:** Two modes (+ dry-run):

* **Transactional (default):** stop on first hard failure, rollback prior renames, return **207 Multi-Status** summary.
* **Continue-on-error:** attempt all, return successes/failures, provide **rollback token** (reverts the successful subset).
* **Dry-run:** never mutates.

**Tickets:** T4-05 appended to Sprint 4.

---

## 6) LLM Streaming + Structured JSON

**Decision:** Two channels.

* **SSE stream** for human feedback (`llm_token`, `progress`, `warning`).
* **Buffered final JSON** for authoritative output (schema-validated).
  Optional NDJSON hints may be streamed but are non-authoritative.

**Tickets:** T6-05 appended to Sprint 6.

---

## 7) MCP Tool Role Clarification

**Decision:** MCP is a **thin client** over REST for developers (Cursor).

* Tools: `scan.preview`, `plan.preview`, `plan.explain`, `apply.undo`, `disambiguate.resolve`, `provider.lookup`.
* Capabilities: preview plans, explain items, rollback via `report_id`, resolve disambiguations, quick provider lookups.
* Permissions: local-only by default; timeouts and error normalization.

**Tickets:** Sprint **6.5** added with T6.5-01 → T6.5-06.

---

### Cross-References

* TASKS_SPRINTS_1-4: Sprint 3 – T3-05, T3-06 appended.
* TASKS_SPRINTS_5-8: Sprint 6 – T6-04, T6-05 appended; Sprint 6.5 added.

---

## 🔧 Implementation Notes (non-normative)

* Keep **final `/plan` response buffered** and schema-validated; stream SSE only for human feedback.
* Compute buckets with constants so they’re easy to tune later.
* For byte-stability tests, compare a copy of JSON with `generated_at` removed.
