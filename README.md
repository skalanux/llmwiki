# LLM Wiki — Ingesta y Clasificación Automática

An automatic ingestion and classification pipeline that watches a directory
for new documents (Markdown, text, PDF, images), extracts their content,
classifies them via an LLM (DeepSeek / OpenCode Zen), and writes them as
structured wiki pages with YAML frontmatter, tags, cross-references, and
deduplication. Inspired by [Andrej Karpathy's LLM wiki
gist](https://gist.github.com/karpathy/369fce0d1086d2e78e38bb7dc64963e6).

The pipeline runs as a Typer CLI (`llmwiki-ingest`) and uses LangGraph for
stateful orchestration through four sequential stages: Extract → Classify →
Generate → Write. File watching via `watchdog` enables hands-free operation.

## Quickstart

```bash
# Clone and enter the project
git clone <repo-url>
cd llmwiki

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install the package (with PDF/OCR support)
pip install -e ".[pdf]"

# Configure your API key
cp .env.example .env
# Edit .env and set LLMWIKI_API_KEY

# Run the CLI
llmwiki-ingest
```

> **Note**: PDF/OCR extraction requires the optional `docling` library.
> Install it separately with ``pip install llmwiki-ingest[pdf]``.
> OCR further requires **Tesseract** to be installed on your system
> (``apt install tesseract-ocr``, ``brew install tesseract``, etc.).

## Configuration

All configuration is via environment variables or a `.env` file. See
`.env.example` for the full list.

## Project Structure

```
src/llmwiki/          # Package root
  cli.py              # Typer CLI entry point
  config.py           # Pydantic BaseSettings
  pipeline.py         # LangGraph state graph
  state.py            # Shared TypedDict state
  classifier.py       # LLM classification service
  wiki_writer.py      # Wiki page generator
  hash_tracker.py     # SQLite-based dedup
  file_watcher.py     # watchdog observer
  extractors/         # Text extraction strategies
    base.py           # Abstract base extractor
    text.py           # Plain text (.md, .txt)
    pdf.py            # PDF extraction
    ocr.py            # Image OCR
```

### Runtime Directories (configured via LLMWIKI_BASE_DIR)

All runtime data lives **outside** the project, in a directory you choose:

```
/path/to/llmwiki-data/     ← set LLMWIKI_BASE_DIR in .env
├── inbox/                  ← drop files here for automatic processing
└── wiki/                   ← generated wiki pages
```

The inbox and wiki directories can also be set independently via
``LLMWIKI_INBOX_DIR`` and ``LLMWIKI_WIKI_DIR`` (absolute paths, or relative
to ``LLMWIKI_BASE_DIR``).

## Phased Delivery

| Phase | What                    | Status |
|-------|-------------------------|--------|
| P0    | Project scaffold        | ✅ Done |
| P1    | Core pipeline + CLI     | 🔜 Next |
| P2    | Hash tracker + watcher  | 📋 Planned |
| P3    | PDF / OCR extractors    | ✅ Done |
| P4    | Hardening & polish      | 📋 Planned |
