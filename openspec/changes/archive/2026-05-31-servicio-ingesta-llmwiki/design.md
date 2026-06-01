# Design: Servicio de Ingesta y Clasificación Automática para llmwiki

## Technical Approach

LangGraph pipeline orquestado como state graph dentro de un CLI Typer. Cuatro nodos secuenciales: Extract → Classify → Generate → Write. Cada nodo recibe/escribe en un `State` compartido (TypedDict). Extractors usan **strategy pattern** por tipo de archivo. LLM calls vía cliente OpenAI-compatible apuntando a OpenCode Zen. Watchdog como hilo separado en Phase 2. Sin staging — pipeline fully automatic.

## Architecture Decisions

| Decisión | Opciones | Tradeoff | Elegido |
|----------|----------|----------|---------|
| **Graph topology** | Linear vs sub-graphs | Linear: simple, fácil de debuggear. Sub-graphs: reutilizables, más overhead | **Linear** — 4 nodos, error branching por nodo |
| **State persistence** | SQLite checkpoints vs in-memory | Checkpoints: resume tras crash. In-memory: zero deps, más rápido | **In-memory** (P1) — checkpoint opcional P4 |
| **Extractor dispatch** | Registry pattern vs if/elif | Registry: extensible, más boilerplate. if/elif: simple para 4 tipos | **if/elif** en `IngestionService` — 4 formatos no justifican registry |
| **LLM client** | httpx directo vs openai SDK | httpx: sin dep extra, control total. openai SDK: retry built-in, streaming | **httpx directo** — solo usamos `/chat/completions`, evitar dep pesada |
| **Hash algorithm** | SHA-256 vs BLAKE2b | BLAKE2b: 2x más rápido en Python. SHA-256: estándar | **BLAKE2b** (hashlib) — SQLite key, archivos grandes |
| **Error handling** | Nodo condicional vs excepción | Condicional: visible en graph. Excepción: simple pero opaco | **Excepción con logging** — early exit rápido y claro |
| **File watching** | watchdog vs inotify puro | watchdog: cross-platform. inotify: linux-only | **watchdog** (P2) — ya decidido en proposal, PollingObserver fallback |

## Data Flow

```
inbox/foo.md
    │ (CLI arg o watchdog event)
    ▼
┌──────────────────────────────────────────┐
│           IngestionService               │
│  1. hash_tracker.is_duplicate(blake2b)   │◄── data/hash.db
│  2. skip si ya procesado                 │
└──────┬───────────────────────────────────┘
       │ file_path (no duplicado)
       ▼
┌──────────────────────────────────────────┐
│ 1. extract_text(file_path)               │
│    └─ strategy: PlainTextExtractor       │
│       PdfExtractor ─► pypdf              │
│       OcrExtractor ─► pytesseract        │
│    Salida: raw_text + metadata            │
└──────┬───────────────────────────────────┘
       │ raw_text
       ▼
┌──────────────────────────────────────────┐
│ 2. classify(raw_text)                    │
│    └─ POST /zen/v1/chat/completions      │
│       → deepseek-v4-flash                │
│       → Structured output (JSON mode)    │
│    Salida: Classification (Pydantic)      │
└──────┬───────────────────────────────────┘
       │ classification
       ▼
┌──────────────────────────────────────────┐
│ 3. generate_wiki(classification)         │
│    └─ LLM escribe markdown + frontmatter │
│    └─ tiktoken budget check pre-call     │
│    Salida: wiki_markdown (str)            │
└──────┬───────────────────────────────────┘
       │ wiki_markdown
       ▼
┌──────────────────────────────────────────┐
│ 4. write_page(wiki_markdown)             │
│    └─ Construye ruta: wiki/{slug}.md     │
│    └─ Escribe archivo                    │
│    └─ hash_tracker.record(hash, path)    │
└──────┬───────────────────────────────────┘
       │ hash registrado
       ▼
     ✅ Done — stdout summary via Rich
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/__init__.py` | Create | Package marker |
| `src/__main__.py` | Create | `python -m llmwiki` entry point |
| `src/cli.py` | Create | Typer app con comandos `ingest`, `watch` |
| `src/config.py` | Create | `LLMWikiConfig` Pydantic model, load from env+.env |
| `src/state.py` | Create | LangGraph `State` TypedDict: file_path, raw_text, metadata, classification, wiki_content, hash, errors |
| `src/pipeline.py` | Create | `create_graph()` → LangGraph `StateGraph` definition |
| `src/models.py` | Create | `Classification`, `Metadata`, `LLMResponse` Pydantic models |
| `src/extractors/__init__.py` | Create | Extractor registry/dispatch |
| `src/extractors/base.py` | Create | `BaseExtractor` abstract class |
| `src/extractors/text.py` | Create | `PlainTextExtractor` — .md/.txt |
| `src/extractors/pdf.py` | Create | `PdfExtractor` — pypdf |
| `src/extractors/ocr.py` | Create | `OcrExtractor` — pytesseract |
| `src/classifier.py` | Create | `ClassifierService` — httpx client, retry, JSON mode |
| `src/wiki_writer.py` | Create | `WikiWriter` — genera frontmatter, escribe archivos |
| `src/hash_tracker.py` | Create | `HashTracker` — SQLite, init_table, is_duplicate, record |
| `src/file_watcher.py` | Create | `FileWatcherService` — watchdog observer + event handler |
| `pyproject.toml` | Create | Project metadata, deps, `[tool.llmwiki]` section, Typer entry point |
| `.env.example` | Create | Template con OPENCODE_API_KEY, defaults comentados |
| `inbox/` | Create | Directorio monitoreado (gitkeep + .gitignore) |
| `wiki/` | Create | Directorio de salida (gitkeep + .gitignore) |
| `data/hash.db` | Create | SQLite DB (creado en runtime, gitignored) |
| `.gitignore` | Create | `/data/`, `wiki/`, `.env`, `__pycache__` |

## Interfaces / Contracts

```python
# state.py
class State(TypedDict):
    file_path: str
    file_hash: str               # blake2b hex digest
    raw_text: str | None
    metadata: dict[str, Any]     # size, mtime, format, pages (pdf)
    classification: Classification | None
    wiki_content: str | None     # markdown final
    output_path: str | None      # wiki/{slug}.md
    errors: list[str]

# models.py
class Classification(BaseModel):
    title: str
    slug: str                    # sanitized, url-friendly
    page_type: Literal["entity", "concept", "source", "reference"]
    tags: list[str]
    summary: str
    related_slugs: list[str]
    confidence: float            # 0.0 - 1.0

# extractors/base.py
class BaseExtractor(ABC):
    supported_extensions: ClassVar[frozenset[str]]
    @abstractmethod
    async def extract(self, path: Path) -> tuple[str, dict]: ...

# classifier.py | __call__
class ClassifierService:
    async def classify(self, text: str) -> Classification: ...

# wiki_writer.py
class WikiWriter:
    async def write(self, content: str, slug: str) -> Path: ...
    def _build_frontmatter(self, classification: Classification) -> str: ...
    def _slug_to_path(self, slug: str) -> Path: ...

# hash_tracker.py
class HashTracker:
    def is_duplicate(self, digest: str) -> bool: ...
    def record(self, digest: str, path: str) -> None: ...
```

**LLM API Contract** (OpenCode Zen /chat/completions):

```json
// Request
POST {base_url}/chat/completions
{
  "model": "deepseek-v4-flash",
  "messages": [{"role": "user", "content": "classify: ..."}],
  "response_format": { "type": "json_object" }
}

// Response
{
  "id": "...",
  "choices": [{
    "message": {
      "content": "{\"title\": \"...\", \"slug\": \"...\", ...}"
    }
  }]
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Extractors (text, pdf mock, ocr mock) | Parametrize por formato, assert text + metadata shape |
| Unit | ClassifierService (httpx mock) | Mock responses, assert retry on 429/503 |
| Unit | HashTracker | In-memory SQLite, assert dedup |
| Unit | WikiWriter | Assert frontmatter YAML, slug→path mapping |
| Integration | Pipeline end-to-end (archivo real) | Temp dirs, .md input → wiki page output |
| Integration | LangGraph graph | State transitions, error branch coverage |

## Migration / Rollout

No migration required. Greenfield project. Phased delivery por capacidades:

1. **P0** — `pyproject.toml`, `src/__main__.py`, `config.py` (env + cli scaffold)
2. **P1** — Pipeline completo (extract→classify→generate→write), CLI ingest command
3. **P2** — `HashTracker` + `FileWatcherService`, `watch` command
4. **P3** — PDF/OCR extractors
5. **P4** — Hardening: retry, checkpointing, structured output validation

## Open Questions

- [ ] ¿Debe el LLM prompt de generación incluir el wiki existente como contexto? Si sí, necesitamos leer el archivo antes de regenerar — puede crecer el token budget.
- [ ] Formato de respuesta del LLM: ¿usar `response_format: json_object` (disponible en OpenCode Zen?) o `function calling` para structured output?
- [ ] Watchdog: ¿polling observer + debounce por tiempo o inotify con `IN_CLOSE_WRITE`? Depende de si corre en WSL/macOS.
