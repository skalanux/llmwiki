# Specs: Servicio de Ingesta y Clasificación Automática

## Overview

6 new capabilities, each with a full spec at `openspec/specs/{domain}/spec.md`:

| Domain | Requirements | Scenarios | Key RFC 2119 |
|--------|-------------|-----------|-------------|
| ingestion-cli | 4 | 6 | MUST provide Typer CLI, MUST load .env |
| text-extraction | 5 | 9 | MUST extract .md/.txt/PDF/images |
| llm-classification | 5 | 7 | MUST call OpenAI-compatible API, retry logic |
| wiki-generation | 5 | 5 | MUST write YAML frontmatter, hash-check skip |
| file-watching | 5 | 5 | MUST watch via watchdog, debounce, filter temps |
| hash-tracking | 5 | 6 | MUST SHA-256 dedup via SQLite, corrupt recovery |

**Total**: 30 requirements, 38 scenarios across 6 capability specs.

## Per-Domain Summary

### ingestion-cli
`llmwiki-ingest` Typer CLI with `ingest`, `watch`, `config`, `status`. Config from `.env` + env vars. Missing API key → exit 1 with error message. Rich progress display.

### text-extraction
Read `.md`/`.txt` directly (UTF-8/Latin-1). PDFs via docling. Images via Tesseract OCR. Returns `{text, source_path, file_type, size, hash}`.

### llm-classification
Sends text to OpenCode Zen (`/chat/completions`) requesting JSON schema: `title`, `tags`, `summary`, `sections`, `related_pages`. Token truncation via tiktoken. 3 retries on 5xx/timeout, fail fast on 401/403.

### wiki-generation
Pages in `wiki/` with YAML frontmatter (`title`, `date`, `tags`, `source`, `hash`). Sanitized filenames. Hash-check skip. Wikilink cross-refs. 2000-word split threshold.

### file-watching
Watchdog observer on configurable directory. `IN_CLOSE_WRITE` trigger. 5s debounce. Ignore `.swp`, `~`, `.tmp`. Fallback to polling if no inotify.

### hash-tracking
SQLite at `~/.llmwiki/processed.sqlite`. SHA-256 dedup. Skip on hash match. Back up + recreate on corruption.

## Next Step

Ready for sdd-design.
