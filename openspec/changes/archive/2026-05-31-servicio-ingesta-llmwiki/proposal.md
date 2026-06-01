# Proposal: Servicio de Ingesta y Clasificación Automática para llmwiki

## Executive Summary

Autonomous LLM-powered ingestion service for llmwiki. User drops raw sources (`.md`, `.txt`, PDF, images) into an inbox — service extracts text, classifies content via DeepSeek V4 Flash (routed through OpenCode Zen), and generates/maintains interconnected markdown wiki pages. Fully automatic, zero human intervention.

## Intent

Implement Karpathy's "self-writing wiki" pattern: raw sources → LLM classifies → wiki pages with cross-references and auto-updated index. No manual structuring required from the user.

## Scope

### In Scope
- LangGraph pipeline: validate → extract → classify → identify affected pages → generate updates → write → update index
- File format support: `.md`, `.txt`, `.pdf` (pypdf), images (tesseract OCR)
- OpenCode Zen integration (OpenAI-compatible client, configurable endpoint + API key)
- File watching via watchdog (Phase 2)
- SQLite hash tracking — skip already-processed files
- CLI mode (Phase 1) + auto-watch mode (Phase 2+)
- Wiki output: markdown + YAML frontmatter

### Out of Scope
- Web UI / dashboard
- Cloud deployment adapters (S3, webhooks)
- Scheduled lint/health-check daemon
- Webhook-based ingest API
- Multi-user or auth layer

## User Workflow

1. Set `OPENCODE_API_KEY` in `.env`
2. Drop files into `~/inbox/` (configurable)
3. **Phase 1**: `llmwiki-ingest ~/inbox/doc.md` (manual CLI)
4. **Phase 2+**: files auto-process on drop (watchdog daemon)
5. Service extracts → classifies → writes/updates pages in `~/wiki/`
6. User reads wiki via any markdown viewer

## Architecture

```
┌── inbox/ ──┐
│ doc.md     │  ← user drops files
│ paper.pdf  │
│ img.png    │
└─────┬──────┘
      │ file_path
      ▼
┌──────────────────────┐
│  CLI (P1) / watchdog │  file event or manual
│  (P2+)               │
└──────┬───────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│         LangGraph Pipeline (Core)           │
│                                             │
│  validate → extract → classify → identify  │
│  affected_pages → generate → write → index  │
│                                             │
│  Shared State: file_path, hash, raw_text,   │
│  classification, affected_pages[], errors[] │
└──────┬──────────────────────────────────────┘
       │ LLM calls (OpenAI-compatible)
       ▼
┌───────────────────┐
│  OpenCode Zen      │  gateway/router
│  /zen/v1/...       │  → deepseek-v4-flash
│  (configurable)    │
└───────────────────┘
       │ writes .md files
       ▼
┌── wiki/ ──┐
│ index.md   │  auto-updated
│ entities/  │  per-classification pages
│ concepts/  │
│ sources/   │
└───────────┘
```

## Phasing Plan

| Phase | What | Key Deps | Deliverable |
|-------|------|----------|-------------|
| **P0** | Setup: pip, venv, `.env`, project skeleton | — | Working Python env |
| **P1** | LangGraph CLI pipeline (validate→extract→classify→write→index) | `langgraph`, `httpx`, `pydantic`, `pyyaml`, `tiktoken` | Core classification + wiki generation |
| **P2** | File watcher + SQLite hash tracking | `watchdog`, stdlib `sqlite3` | Auto-pickup from inbox |
| **P3** | PDF extraction + OCR | `pypdf`, `pytesseract`, `pillow` | Rich format support |
| **P4** | LangGraph hardening: retry, structured output, conditional branches | — | Production-grade pipeline |

## Capabilities

### New Capabilities
- `ingestion-cli`: CLI pipeline that ingests a file path and generates wiki pages
- `text-extraction`: Extract text from .md, .txt, PDF, and image files
- `llm-classification`: Classify content via OpenCode Zen + DeepSeek V4 Flash
- `wiki-generation`: Write/update markdown wiki pages with YAML frontmatter
- `file-watching`: Watch inbox directory for new files (auto-process)
- `hash-tracking`: SQLite-based dedup to avoid reprocessing

### Modified Capabilities

None. This is a greenfield project — no existing specs.

## Tech Stack

| Package | Purpose | Phase |
|---------|---------|-------|
| `langgraph ≥0.3` | Pipeline orchestration (state graph) | P1 |
| `httpx ≥0.28` | Async HTTP calls to OpenCode Zen | P1 |
| `pydantic ≥2.0` | Schemas, state, config validation | P1 |
| `python-dotenv ≥1.0` | `.env` file loading | P0 |
| `pyyaml ≥6.0` | Frontmatter parsing/writing | P1 |
| `tiktoken ≥0.9` | Token counting for context budget | P1 |
| `rich` | CLI formatting / progress display | P1 |
| `watchdog ≥5.0` | File system events (cross-platform) | P2 |
| `pypdf ≥5.0` | PDF text extraction | P3 |
| `pytesseract` | OCR for images | P3 |
| `pillow ≥10.0` | Image preprocessing for OCR | P3 |

## API & Configuration

- **`.env`** at project root or `~/llmwiki/.env`
- `OPENCODE_API_KEY` — required, paid API key
- `OPENCODE_BASE_URL` — default `https://opencode.ai/zen/v1`
- `OPENCODE_MODEL` — default `deepseek-v4-flash`
- `WIKI_DIR` — default `~/wiki`
- `INBOX_DIR` — default `~/inbox`
- All optional except `API_KEY`. Use `pydantic.BaseSettings` or `python-dotenv` + `os.getenv`.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LangGraph from P1 | ✅ Yes | User's explicit request. Used as lightweight state graph inside CLI, not just API wrapper |
| LLM client | OpenAI-compatible | OpenCode Zen exposes `/zen/v1/chat/completions`; allows swapping providers |
| OCR | pytesseract | Mature, well-tested; Tesseract C lib is a one-time OS dependency |
| File watching | watchdog | Cross-platform (inotify/FSEvents/polling). PollingObserver = cloud-ready fallback |
| Pipeline mode | Fully auto | User decision — no review/staging step |
| Hash tracking | stdlib sqlite3 | Zero added deps, persistent across runs |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Tesseract not installed | Med | Document in setup; fail with clear error + install instructions |
| LLM classification quality | Med | CLI mode enables prompt iteration before auto-watch goes live |
| Token overflow as wiki grows | Low | `tiktoken` budget check before each LLM call; truncate context if needed |
| Partial file on CREATE event | Low | Debounce + verify size stability; use `IN_CLOSE_WRITE` when available |

## Rollback Plan

1. **Single file**: delete generated wiki page → next ingest regenerates
2. **Full revert**: restore `wiki/` from git, clear `processed_files.sqlite`
3. **Code revert**: `git revert` commit, re-run `pip install -e .`

## Success Criteria

- [ ] CLI ingests a `.md` file → generates ≥1 wiki page with correct classification
- [ ] Same file re-uploaded is skipped (hash match)
- [ ] PDF text extraction produces usable classification
- [ ] Watchdog auto-pickup works for new files in inbox
- [ ] All LLM calls go through configurable OpenCode Zen endpoint
- [ ] `.env` without `OPENCODE_API_KEY` fails with clear error
