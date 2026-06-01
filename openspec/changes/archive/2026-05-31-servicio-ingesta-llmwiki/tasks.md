# Tasks: Servicio de Ingesta y Clasificación Automática

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~580–700 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (P0) → PR 2 (P1a) → PR 3 (P1b) → PR 4 (P1c) |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes (resolved → feature-branch-chain)
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High (managed — PR 1 is ~100 lines)

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | P0 Scaffold — pyproject, package, dirs, env, linters | PR 1 | ~100 lines, base = main |
| 2 | P1a Foundation — config, state, models | PR 2 | ~120 lines, base = main |
| 3 | P1b Extractors + Classifier + Wiki writer + Hash tracker | PR 3 | ~255 lines, base = PR 2 branch |
| 4 | P1c Pipeline + CLI + Wiring | PR 4 | ~175 lines, base = PR 3 branch |

## Phase 1: Foundation / Infrastructure

- [x] 1.1 Create `pyproject.toml` with project metadata, build system, deps (typer, langgraph, httpx, pydantic, pydantic-settings, pyyaml, watchdog)
- [x] 1.2 Create `src/llmwiki/__init__.py` and `src/llmwiki/__main__.py` package markers
- [x] 1.3 Create `.env.example` with DEEPSEEK_API_KEY, OPENCODE_ZEN_ENDPOINT, MODEL, WIKI_DIR, INBOX_DIR, WATCH, OCR_ENABLED
- [x] 1.4 Create `data/`, `inbox/`, `wiki/` directories with `.gitkeep`
- [x] 1.5 Create `.gitignore` ignoring `/data/`, `wiki/`, `.env`, `__pycache__`, `*.pyc`
- [x] 1.6 Add `ruff` + `mypy` config sections to `pyproject.toml`
- [x] 1.7 Create `src/llmwiki/config.py` with `LLMWikiConfig(BaseSettings)` — loads `.env` + env vars (placeholder)
- [x] 1.8 Create `src/llmwiki/state.py` with LangGraph `State(TypedDict)` — file_path, hash, raw_text, metadata, classification, wiki_content, output_path, errors (placeholder)
- [x] 1.9 Create `src/llmwiki/models.py` with `ClassificationResult`, `Metadata`, `LLMResponse` Pydantic models

## Phase 2: Core Implementation

- [x] 2.1 Create `src/llmwiki/extractors/__init__.py` — package marker (placeholder)
- [x] 2.2 Create `src/llmwiki/extractors/base.py` with `BaseExtractor(ABC)` — abstract base (placeholder)
- [x] 2.3 Create `src/llmwiki/extractors/text.py` with `PlainTextExtractor` for `.md`/`.txt` (placeholder)
- [x] 2.4 Create `src/llmwiki/classifier.py` with `ClassifierService` (placeholder)
- [x] 2.5 Create `src/llmwiki/wiki_writer.py` with `WikiWriter` (placeholder)
- [x] 2.6 Create `src/llmwiki/hash_tracker.py` with `HashTracker` (placeholder)

## Phase 3: Integration / Wiring

- [x] 3.1 Create `src/llmwiki/pipeline.py` with `create_graph()` (placeholder)
- [x] 3.2 Create `src/llmwiki/cli.py` with Typer app (placeholder — "Hello from llmwiki")
- [x] 3.3 Wire `src/llmwiki/__main__.py` as `python -m llmwiki` entry point calling CLI
- [x] 3.4 Add `[project.scripts]` entry point `llmwiki-ingest` in `pyproject.toml`

## Phase 4: Documentation

- [x] 4.1 Create `README.md` with overview, setup steps, quickstart, config reference

## Phase 5: File Watching + Hash Dedup (P2)

- [x] 5.1 Add `hash_check_node` before `extract_node` in LangGraph pipeline with conditional skip
- [x] 5.2 Add `skipped: bool` field to `State` TypedDict
- [x] 5.3 Implement `src/llmwiki/file_watcher.py` with watchdog, `IN_CLOSE_WRITE`, debounce, temp file filtering, polling fallback
- [x] 5.4 Add `watch` Typer subcommand to `src/llmwiki/cli.py`
- [x] 5.5 Add `size INTEGER` column to `hash_tracker` SQLite schema with migration
- [x] 5.6 Add `run_pipeline()` shared async helper to `pipeline.py`
