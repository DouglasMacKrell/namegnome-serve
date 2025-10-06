# Contributing to NameGnome Serve

Thank you for your interest in contributing to NameGnome Serve!

---

## 🌿 Branching Strategy

We use a **main + develop** workflow:

- **`main`** → Stable releases only. Production-ready code.
- **`develop`** → Active development branch (default). All PRs merge here first.
- **Feature branches** → Branch from `develop` for new features or tasks.

### Workflow

1. **Create feature branch from develop:**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/NGS-XXX-short-description
   ```

2. **Make changes and commit:**
   ```bash
   git add .
   git commit -m "NGS-XXX: Description of change"
   ```

3. **Push and create PR to develop:**
   ```bash
   git push -u origin feature/NGS-XXX-short-description
   gh pr create --base develop --title "NGS-XXX: Title" --body "Description"
   ```

4. **After PR approval, merge to develop:**
   - PR merges automatically delete the feature branch

5. **Periodic releases to main:**
   - Once `develop` is stable, create a PR from `develop` → `main`
   - Tag releases on `main`: `v0.1.0`, `v0.2.0`, etc.

---

## 📝 Commit Format

Use the **NGS-XXX** prefix for task-related commits:

```
NGS-XXX: Brief description of change

Longer explanation if needed, referencing specific files or decisions.
```

Examples:
- `NGS-001: Add scanner module with recursive file walker`
- `NGS-023: Implement SQLite cache schema and migrations`
- `NGS-042: Fix anthology overlap detection in edge cases`

For non-task commits:
- `docs: Update README with installation steps`
- `chore: Update dependencies`
- `fix: Correct typo in MEDIA_CONVENTIONS.md`

---

## 🧪 Code Standards

### Before Committing

Run these checks locally:

```bash
# Format code
poetry run black .

# Lint
poetry run ruff check .

# Type check
poetry run mypy .

# Run tests
poetry run pytest --cov=namegnome_serve --cov-fail-under=80
```

### Requirements

- **Python ≥ 3.12** with type hints (use `mypy --strict`)
- **Black** formatting (88 char line length)
- **Ruff** linting (code only, no docs)
- **80% test coverage** minimum
- **Absolute imports** only (rooted at `namegnome_serve`)
- **500-line max** per file (split by feature/domain)
- **Domain isolation**: TV/Movie/Music logic must remain separate

### Testing

Each new function/class requires:
1. **1 expected-flow test** (happy path)
2. **1 edge case test**
3. **1 failure case test**

---

## 📚 Documentation

- Update **README.md** for new commands, flags, or dependencies
- Update **PLAN.md** for architectural changes
- Add **ADRs** (Architecture Decision Records) under `/docs` for major decisions
- Use **Google-style docstrings** for all public functions/classes
- Add inline `# Reason:` or `# TODO: NGS-###` comments where relevant

---

## 🚫 Pre-Commit Hooks

Pre-commit hooks enforce quality gates:
- `black` formatting
- `ruff` linting
- `mypy` type checking
- `pytest` with coverage threshold

**All checks must pass before commit.**

---

## 🧭 Sprint Tasks

Refer to the TASKS files for sprint breakdowns:
- [TASKS_SPRINTS_1-4.md](./TASKS_SPRINTS_1-4.md) — Sprints 0–4
- [TASKS_SPRINTS_5-8.md](./TASKS_SPRINTS_5-8.md) — Sprints 5–8

---

## ❓ Questions?

Open an issue or start a discussion on GitHub!

---

**Thank you for contributing to NameGnome Serve! 🎉**

