# MCP Tool Guide — NameGnome Serve

This guide tells the Cursor Agent **what each MCP server is for**, **when to use it**, and **what to avoid**. Keep this close to the project root so Cursor can reference it reliably.

> ⚠️ **Secrets**: Never commit personal access tokens or env values to Git. Use a local `.env` or your shell profile. Redact tokens in logs and issues.

---

## Decision Matrix (TL;DR)

| Server        | Use for                                                  | Avoid / Caution                                            |
|---------------|-----------------------------------------------------------|------------------------------------------------------------|
| `memory`      | Small, transient key–value notes for the agent            | Not for large blobs or long-term storage                   |
| `github`      | Reading issues/PRs, searching code, filing issues         | Never push secrets; avoid mass-changes without review      |
| `github-actions` | Trigger/check workflows, view CI status              | Don’t spam runs; require idempotent workflows              |
| `timeserver`  | Reliable timestamps, timezone math                        | Don’t assume system clock; always read from this tool      |
| `filesystem`  | Reading/writing project files, scaffolding                | Destructive edits without backup/confirmation              |
| `backup`      | Snapshot/restore project dirs before risky changes        | Skipping backups on rename/apply flows                     |

---

## Standard Usage Rules

1. **Plan → Act**: For any multi-file edit or rename, call `backup.snapshot` first, then act, then `backup.list` to confirm snapshot exists.
2. **Idempotency**: If a tool can be called twice, make the second call a no-op (e.g., re-run `backup.snapshot` should not create duplicate copies with identical content hashes).
3. **Atomicity**: Prefer writing to a temporary path and renaming over in-place writes (aligns with T4-01/T4-05).
4. **Privacy**: Mask absolute paths and redact secrets in logs and issues.
5. **Rate limits**: For `github/*`, back off on 429/secondary rate limiting; retry with jitter.

---

## Tool Details

### 1) `memory` (Model Context Protocol – memory server)
- **Purpose**: Short-lived, local **key–value memory** for the agent during a session (think: “sticky notes”).
- **Typical ops**:
  - `memory.set {key, value}` — persist tiny bits of context (e.g., last `plan_id`, `report_id`).
  - `memory.get {key}` — retrieve previously stored values.
  - `memory.delete {key}` — clean up when obsolete.
- **Use when**:
  - You need to remember **small strings** across multi-step tasks (e.g., disambiguation token).
- **Avoid**:
  - Large payloads, binary blobs, provider payload caches. Use SQLite cache instead.
- **Safety**:
  - Never store secrets or personal tokens. Store **IDs**, not data dumps.

**Example prompts**
- “Store `plan_id=pln_123` and `report_id=rpt_abc` for later rollback.”
- “Retrieve the last `plan_id` we generated in this session.”

---

### 2) `github` (GitHub MCP server)
- **Purpose**: Read/Write access to GitHub resources (issues, PRs, repos) within your configured token scope.
- **Typical ops**:
  - `github.searchCode {query, repo}` — find code references.
  - `github.createIssue {repo, title, body, labels}` — file actionable issues.
  - `github.getPulls / createPull` — PR management (if permitted).
- **Use when**:
  - You need to **open an issue** for Cursor-discipline tasks (e.g., T3-04 schema drift), or search past discussions.
- **Avoid**:
  - Pushing secrets, committing generated files without review, mass changes via PRs without human approval.
- **Safety**:
  - Add repro steps and **redacted** logs. Don’t paste absolute paths with user name in public repos.

**Example prompts**
- “Open an issue in `DouglasMacKrell/namegnome-serve` titled ‘T3-05: unify cache DB’ with the acceptance criteria and migration plan.”
- “Search the repo for `interval_simplify` usages and list file paths.”

---

### 3) `github-actions` (custom MCP actions server)
- **Purpose**: Kick off or inspect **CI workflows** (e.g., tests, lint, release) and fetch run logs.
- **Typical ops**:
  - `actions.trigger {repo, workflow, ref, inputs}`
  - `actions.status {repo, run_id}` / `actions.logs {repo, run_id}`
- **Use when**:
  - You need to **run tests** or **release** via workflow after a PR merges.
- **Avoid**:
  - Spamming workflows. Always check prior run status; re-run only if failed or inputs changed.
- **Safety**:
  - Reference exact `ref` (SHA) to avoid ambiguity. Prefer **dry-run** workflows for release candidates.

**Example prompts**
- “Trigger `ci.yaml` on branch `feature/t3-06` and report the run URL.”
- “Fetch logs for the latest failed run and summarize the failing tests.”

---

### 4) `timeserver` (Python MCP time server)
- **Purpose**: Source of truth for **timestamps** and **timezone** calculations (America/New_York).
- **Typical ops**:
  - `time.now {}` — returns ISO-8601 UTC and local time.
  - `time.convert {timestamp, to_tz}` — convert to specific TZ when needed.
- **Use when**:
  - Writing manifests, naming rollback files, TTL math for caches.
- **Avoid**:
  - Using system time for anything serialized; always request timeserver.
- **Safety**:
  - None special; prefer this over `datetime.now()` in agent flows.

**Example prompts**
- “Give me an ISO-8601 UTC timestamp for the rollback header.”
- “Convert `2025-10-08T13:22:19Z` to America/New_York.”

---

### 5) `filesystem` (MCP filesystem server)
- **Purpose**: **Reading/writing files** under the project directory; scaffolding; applying small patches.
- **Typical ops**:
  - `fs.read {path}` / `fs.write {path, content}`
  - `fs.list {path, glob}` — discover files safely
  - `fs.mkdirp {path}` — ensure directories exist
- **Use when**:
  - Updating docs (`TASKS_*`, `MEDIA_CONVENTIONS.md`), adding schemas, or writing tests/fixtures.
- **Avoid**:
  - Mass destructive edits without **backup**; never modify outside allowed root.
- **Safety**:
  - **NFC normalize** filenames (macOS), write to `.tmp` and then rename, keep changes ≤500 lines per file (per your project rules).

**Example prompts**
- “Write `schemas/plan_review.schema.json` with this exact JSON contents, then re-open to verify.”
- “Create `tests/core/test_interval_simplify.py` with the following test cases.”

---

### 6) `backup` (custom MCP backup server)
- **Purpose**: **Snapshot/restore** directories before risky edits (e.g., plan apply, refactors).
- **Typical ops**:
  - `backup.snapshot {path, label?}` → returns `snapshot_id`
  - `backup.list {}` — list snapshots and metadata
  - `backup.restore {snapshot_id, to_path?}` — restore
- **Use when**:
  - Before large file renames (APPLY), or bulk code rewrites.
  - Before schema migrations that modify generated files.
- **Avoid**:
  - Skipping snapshots on multi-file operations.
- **Safety**:
  - Verify snapshot size/hash; set retention via `MAX_VERSIONS`. Confirm restore path before overwriting.

**Example prompts**
- “Create a snapshot of `src/` and `schemas/` labeled `pre-T4-01` and return the `snapshot_id`.”
- “Restore snapshot `snap_2025-10-08_1322` into a temp dir for diff.”

---

## Default Tooling Playbooks

### A) Safe multi-file edit (docs or code)
1. `backup.snapshot` target dirs
2. `filesystem.write` files via temp → rename
3. `github.createIssue` (optional) with summary/links
4. Verify via tests or `github-actions.trigger` (CI)

### B) Preparing an APPLY change
1. `timeserver.now` → `generated_at` stamp
2. `backup.snapshot` library root and `.namegnome`
3. `filesystem.write` manifests/schemas if needed
4. Proceed with apply via REST (outside MCP) but keep snapshot handy

### C) Opening a reproducible issue
1. `timeserver.now` for timestamps
2. `filesystem.read` relevant files
3. `github.createIssue` with redacted logs, steps to reproduce, and links

---
