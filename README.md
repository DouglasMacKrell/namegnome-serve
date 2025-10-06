# NameGnome Serve

**Local-first media file renaming service powered by LangChain, LangServe, and Ollama.**

NameGnome Serve provides reliable, deterministic media renaming that aligns with provider metadata (TMDB/TVDB/MusicBrainz), ensuring your Plex, Jellyfin, and Emby libraries match correctly.

---

## 🎯 Features

- **Provider-First Correctness** — Uses TMDB, TVDB, and MusicBrainz as canonical sources
- **Scan → Plan → Apply** — Three-phase workflow with preview and rollback
- **Smart Anthology Handling** — Multi-episode files mapped using title adjacency
- **Fuzzy Matching** — LLM-assisted matching for truncated or misspelled titles
- **Local LLM** — Powered by Ollama (no cloud dependencies)
- **REST API** — LangServe endpoints for programmatic access
- **MCP Integration** — Tools for Cursor IDE workflows
- **Rich TUI** — Interactive terminal UI with progress streaming

---

## 📋 Status

**Work in Progress** — Currently in development (Sprint 0–8 roadmap defined).

See [PLAN.md](./PLAN.md) for architecture and [TASKS_SPRINTS_1-4.md](./TASKS_SPRINTS_1-4.md) / [TASKS_SPRINTS_5-8.md](./TASKS_SPRINTS_5-8.md) for implementation tasks.

---

## 🚀 Quick Start

### Prerequisites

- Python ≥ 3.12
- [Poetry](https://python-poetry.org/docs/#installation)
- [Ollama](https://ollama.ai/) with `llama3:8b` model
- API keys for TMDB and TVDB (see [env.example](./env.example))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/namegnome-serve.git
cd namegnome-serve

# Install dependencies
poetry install

# Copy and configure environment
cp env.example .env
# Edit .env with your API keys

# Create Ollama model
ollama create namegnome -f models/namegnome/Modelfile

# Run the server
poetry run uvicorn namegnome_serve.app:app --reload
```

---

## 📖 Documentation

- **[PLAN.md](./PLAN.md)** — Architecture, API design, caching strategy
- **[MEDIA_CONVENTIONS.md](./MEDIA_CONVENTIONS.md)** — Plex-compatible naming rules
- **[TASKS_SPRINTS_1-4.md](./TASKS_SPRINTS_1-4.md)** — Sprints 0–4 task breakdown
- **[TASKS_SPRINTS_5-8.md](./TASKS_SPRINTS_5-8.md)** — Sprints 5–8 task breakdown

---

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# With coverage
poetry run pytest --cov=namegnome_serve --cov-report=html

# Lint and type check
poetry run ruff check .
poetry run black --check .
poetry run mypy .
```

---

## 🛠️ Development

### Project Structure

```
namegnome-serve/
├── src/namegnome_serve/    # Main package
│   ├── core/                # Scanner, fs ops, constants
│   ├── rules/               # TV/Movie/Music naming logic
│   ├── metadata/providers/  # TMDB/TVDB/MusicBrainz clients
│   ├── cache/               # SQLite caching layer
│   ├── chains/              # LangChain LCEL chains
│   ├── routes/              # FastAPI/LangServe routes
│   ├── mcp/                 # MCP tools for Cursor
│   └── cli/                 # TUI implementation
└── tests/                   # Test suite
```

### Code Standards

- **Python ≥ 3.12** with type hints
- **black** formatting, **ruff** linting, **mypy --strict**
- **80% test coverage** threshold
- **Absolute imports** only (rooted at `namegnome_serve`)
- **500-line max** per file (split by feature/domain)
- **Domain isolation**: TV/Movie/Music logic stays separate

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Follow the project's code standards (see above)
2. Write tests for new features (80% coverage required)
3. Use commit format: `NGS-XYZ: concise action description`
4. Reference task tickets from TASKS files where applicable

---

## 📜 License

[MIT License](./LICENSE) (TBD)

---

## 🙏 Acknowledgments

- **[LangChain](https://github.com/langchain-ai/langchain)** for LLM orchestration
- **[Ollama](https://ollama.ai/)** for local LLM inference
- **[TMDB](https://www.themoviedb.org/)**, **[TVDB](https://thetvdb.com/)**, **[MusicBrainz](https://musicbrainz.org/)** for metadata

---

**Built with ❤️ for reliable media library management.**

