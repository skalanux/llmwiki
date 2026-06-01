## Exploration: Servicio de Ingesta y Clasificación Automática para llmwiki

### Fecha
2026-05-31

### Fuentes consultadas
- [Karpathy's LLM Wiki — Gist original](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Build a Second Brain — AskGlitch blog post](https://www.askglitch.com/blog/build-a-second-brain)
- [OpenCode Zen — Documentación oficial](https://open-code.ai/en/docs/zen)
- [Synthadoc v0.5.0](https://github.com/axoviq-ai/synthadoc) — implementación de referencia con revisión adversarial
- [LLM-WIKI-MCP](https://github.com/Electro-resonance/LLM-WIKI-MCP) — MCP server con ingest, hash tracking, Ollama support
- [Synto v0.3.0](https://github.com/kytmanov/synto) — wiki local-first con MCP server y drafts
- [Link v1.3.0](https://github.com/gowtham0992/link) — source-backed memory con MCP tools

---

### 1. Concept Understanding

#### La idea de Karpathy (LLM Wiki)

El gist de Karpathy (abril 2026, 5000+ estrellas) propone un **patrón arquitectónico** de 3 capas para construir wikis persistentes mantenidas por LLMs:

| Capa | Descripción | Quién la posee |
|------|-------------|----------------|
| **Raw Sources** | Documentos fuente inmutables (artículos, PDFs, imágenes). El LLM lee pero nunca escribe. | Humano (sourcing) |
| **The Wiki** | Archivos markdown generados por LLM: resúmenes, entidades, conceptos, comparaciones, cross-references. | LLM (escribe todo) |
| **The Schema** | Archivo de configuración (CLAUDE.md, AGENTS.md) que define estructura, convenciones y workflows. | Humano + LLM co-evolucionan |

**El insight clave**: la diferencia con RAG tradicional no es técnica — es **acumulativa**. RAG rediscover knowledge en cada query. La LLM Wiki *compila* conocimiento una vez y lo mantiene actualizado. El wiki se vuelve más rico con cada fuente ingerida.

**Operaciones del ciclo de vida**:
1. **Ingest** — Nueva fuente → el LLM lee, discute takeaways, escribe summary page, actualiza índice, actualiza páginas de entidades/conceptos relacionadas (10-15 páginas por fuente)
2. **Query** — Preguntas contra el wiki. Respuestas se filed back como nuevas páginas
3. **Lint** — Health check periódico: contradicciones, orphan pages, stale claims

#### Cómo lo aborda la implementación de referencia (AskGlitch)

El blog post concreta el patrón en 4 slash commands para Claude Code:
- `/capture <url>` — clipping + ingest → actualiza wiki
- `/sync` — batch reconcile de sources/ nuevos
- `/lint` — health check
- `/digest` — síntesis semanal

Usan skills de Claude Code (archivos SKILL.md en `.claude/skills/`). El setup requiere Obsidian + CLAUDE.md como schema. Es un workflow *manual-asistido*: el humano gatilla cada operación.

**Proyectos existentes que ya implementan esto** (surgidos de los comentarios del gist):

| Proyecto | Stack | Diferenciador |
|----------|-------|---------------|
| LLM-WIKI-MCP | Python, MCP, Ollama | CLI + MCP server, hash-based tracking, local-first |
| Synthadoc | Rust, Obsidian plugin | Revisión adversarial, claim-level provenance |
| Link | Go, MCP, SQLite | Source-backed memory, graph UI |
| Synto | Python, MCP, Ollama | Three-state drafts (draft → verified → published) |

Ninguno usa LangGraph. Todos son más simples: CLI o MCP server con llamadas secuenciales al LLM.

---

### 2. Architecture Sketches

#### Enfoque A: Servicio Autónomo con LangGraph (Full Automation)

```
┌─────────────────────────────────────────────────────────┐
│                    langgraph Service                      │
│                                                           │
│  ┌──────────┐   ┌──────────┐   ┌─────────┐   ┌────────┐ │
│  │ FileWatch │──→│ Extract  │──→│ Classify│──→│ Wiki   │ │
│  │ (inotify) │   │ (text)   │   │ (LLM)   │   │ Writer │ │
│  └──────────┘   └──────────┘   └─────────┘   └────────┘ │
│       │              │              │              │      │
│       ▼              ▼              ▼              ▼      │
│  ┌──────────────────────────────────────────────────┐    │
│  │              Graph State (shared)                │    │
│  │  file_path, content_type, raw_text,              │    │
│  │  classification, wiki_pages_affected             │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │  OpenCode Zen Client (httpx → api.open.ai/zen)   │    │
│  └──────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
         ▲                              │
         │  inotify events              │  writes markdown
         │  (CREATE, MODIFY)            │  files
         │                              ▼
  ┌────────────┐                ┌──────────────┐
  │  ~/inbox/   │                │  ~/wiki/      │
  │  (sources)  │                │  (markdown)   │
  └────────────┘                └──────────────┘
```

- **Pros**: Automatización completa, el usuario solo deja caer archivos
- **Cons**: Complejidad alta (LangGraph + inotify + async processing), inotify no funciona en serverless
- **Effort**: Alto

#### Enfoque B: Servicio Híbrido (Daemon Watch + API para LLM Processing)

```
┌─────────────────┐     ┌────────────────────────────────────┐
│  watchdog daemon │────→│      FastAPI / Quart Service       │
│  (pyinotify)     │     │                                    │
│                  │     │  POST /ingest (file_path)          │
│  ~/inbox/        │     │  POST /classify (text)             │
│  (monitored)     │     │  POST /wiki/update (page, content) │
│                  │     │  GET  /wiki/health                 │
│  Event → HTTP    │     │                                    │
│  POST to service │     │  ┌──────────────────────────────┐  │
└─────────────────┘     │  │  LangGraph Workflow          │  │
                        │  │  (extract → classify → write)│  │
                        │  └──────────────────────────────┘  │
                        │                                    │
                        │  OpenAI-compatible API call        │
                        │  → OpenCode Zen (DeepSeek V4)     │
                        └────────────────────────────────────┘
```

- **Pros**: Separa concerns, el daemon watch es reemplazable (local vs cloud), la API permite integraciones (webhooks, S3 events)
- **Cons**: Dos procesos que mantener, latencia de HTTP local
- **Effort**: Medio

#### Enfoque C: Workflow Simplificado (Sin LangGraph)

```
┌──────────────┐     ┌───────────────┐     ┌───────────────┐
│  FileWatcher  │────→│  process_file │────→│  classify.py  │
│  (watchdog)   │     │  (extract.py)  │     │  (httpx + LLM)│
└──────────────┘     └───────────────┘     └───────┬───────┘
                                                    │
                                                    ▼
                                            ┌───────────────┐
                                            │  write_wiki.py │
                                            │  (markdown)    │
                                            └───────────────┘
```

- **Pros**: Simple, fácil de debuggear, menos dependencias, fácil deploy
- **Cons**: Sin state management, sin loops de decisión, menos extensible
- **Effort**: Bajo

**Recomendación**: Enfoque B (Híbrido). LangGraph tiene sentido si el flujo necesita loops, branching, o human-in-the-loop. Para un pipeline lineal (watch → extract → classify → write), LangGraph añade complejidad sin beneficio claro. Pero como el usuario lo pidió explícitamente, se puede usar LangGraph para el *orquestador interno* dentro de la API, con el watchdog como proceso separado.

---

### 3. Tech Stack Analysis

#### Dependencias Core

| Dependencia | Versión (est.) | Propósito | Alternativas |
|-------------|----------------|-----------|--------------|
| `langgraph` | ≥0.3 | Orquestación del pipeline como grafo de estado | `temporal`, `prefect`, o vanilla async |
| `watchdog` | ≥5.0 | File system events cross-platform (inotify en Linux, FSEvents en macOS, polling en Windows/cloud) | `pyinotify` (solo Linux), `inotify` (puro C) |
| `httpx` | ≥0.28 | Llamadas HTTP async a OpenCode Zen API | `aiohttp`, `requests` (sync) |
| `pydantic` | ≥2.0 | Validación de datos, schemas, settings | `attrs`, `dataclasses` |
| `pyyaml` | ≥6.0 | Parsing de frontmatter YAML en .md | — |
| `markdown` | ≥3.7 | Renderizado/parsing de markdown | `mistune`, `marko` |
| `tiktoken` | ≥0.9 | Conteo de tokens para presupuestos de LLM | — |
| `python-multipart` | — | Para subida de archivos vía API | — |

#### Opcionales (según necesidad)

| Dependencia | Propósito | Nota |
|-------------|-----------|------|
| `pypdf` / `pdfplumber` | Extraer texto de PDFs | Solo si se ingieren PDFs |
| `pytesseract` + `tesseract` | OCR para imágenes | Solo si se ingieren imágenes con texto |
| `pillow` | Procesamiento de imágenes para OCR | Dependencia de pytesseract |
| `sqlite3` (stdlib) | Tracking de archivos procesados (hash-based) | Evita reprocesar |
| `rich` | Logging bonito en terminal | UX |
| `uvicorn` / `hypercorn` | Servidor ASGI si se usa FastAPI/Quart | Para Enfoque B |

#### Servicios Externos

| Servicio | Rol | Configuración |
|----------|-----|---------------|
| **OpenCode Zen** | API Gateway → DeepSeek V4 Flash Free | `OPENCODE_API_KEY`, endpoint `https://opencode.ai/zen/v1/chat/completions` |
| **OpenCode Zen Free** | Modelo gratuito (`deepseek-v4-flash-free`, 200K context) | Sin costo, requiere API key de OpenCode Zen |

OpenCode Zen es un gateway OpenAI-compatible. Se puede usar con cualquier cliente OpenAI (incluyendo el SDK de LangChain/LangGraph). El modelo `deepseek-v4-flash-free` está disponible sin costo.

#### Estado actual del workspace

- Python 3.14.4 instalado (`/usr/bin/python3`)
- **pip no instalado** — hay que instalarlo primero
- No hay dependencias instaladas
- `openspec/config.yaml` ya configurado con `strict_tdd: false`

#### OpenCode Zen como "Router"

El usuario menciona "OpenCode Zen como router". Analizando la documentación:

**OpenCode Zen** es un **AI Gateway** (no un router en el sentido de tráfico de red). Es un servicio que:
- Provee acceso a modelos curados y benchmarked (DeepSeek V4 Flash Free, Qwen 3.6 Plus, etc.)
- Ofrece un API endpoint OpenAI-compatible (`https://opencode.ai/zen/v1`)
- Maneja facturación, rate limiting, y failover entre modelos
- Es opcional — puedes usar DeepSeek directamente también

El modelo gratuito `deepseek-v4-flash-free` tiene:
- 200K tokens de contexto
- 128K tokens de salida máxima
- Soporte para tools, reasoning, structured output
- Sin costo (free tier promocional)

Como "router", el servicio haría sus llamadas LLM a través de `https://opencode.ai/zen/v1/chat/completions` usando la API key de OpenCode Zen, y OpenCode Zen se encarga de rutear al modelo correcto (DeepSeek V4 Flash Free en este caso).

---

### 4. Key Risks

#### 4.1 inotify en la nube
- **Problema**: inotify requiere un filesystem mountpoint local. En serverless (AWS Lambda, Cloud Run) no existe.
- **Soluciones**:
  - Usar una VM persistente (EC2, DigitalOcean Droplet) con el watchdog
  - Usar eventos de S3/GCS + webhook → al servicio
  - Usar `watchdog` con su `PollingObserver` que funciona sin inotify (pero no escala)
  - Recomendación: abstraer el observer con un adapter pattern (Observer local en dev, SNS+SQS en prod)

#### 4.2 Costos de LLM
- OpenCode Zen Free tiene modelos gratuitos pero son promocionales y pueden cambiar
- Cada ingesta de documento puede consumir 5-15k tokens (dependiendo del tamaño del documento y de cuántas páginas del wiki actualiza)
- Clasificar y escribir 10-15 páginas por fuente puede acumularse en documentos grandes
- Sin control de presupuesto, una ingesta masiva puede ser costosa en modelos pagos

#### 4.3 Calidad de clasificación
- DeepSeek V4 Flash Free puede no ser el mejor modelo para clasificación estructurada si el dominio es muy específico
- El prompt de clasificación (el "schema") va a requerir iteración
- Riesgo de alucinación: el LLM puede "inventar" conexiones en el wiki

#### 4.4 Race conditions en file watching
- Archivos grandes pueden escribirse parcialmente cuando el watcher los detecta (CREATE se dispara antes de que termine la escritura)
- **Solución**: esperar a MODIFY + inotify `IN_CLOSE_WRITE`, o implementar un debounce + verificación de tamaño

#### 4.5 Token overflow
- DeepSeek V4 Flash Free tiene 200K context, pero el wiki puede crecer más que eso
- Si el LLM necesita leer `index.md` completo + varias páginas + el nuevo source, puede exceder el contexto
- **Solución**: usar `tiktoken` para contar tokens antes de enviar, truncar o paginar el contexto

#### 4.6 Dependencia de pip
- pip no está instalado en el ambiente actual
- Bloqueante para empezar: instalar pip o usar `uv`/`pdm` como alternativas

---

### 5. Open Questions

Estas son preguntas que habría que resolver con el usuario antes de pasar a propuesta formal:

1. **¿Modo local, cloud, o ambos?**
   - ¿El servicio corre principalmente en su máquina o quiere deployarlo en la nube?
   - Si es cloud: ¿AWS, GCP, DigitalOcean, o self-hosted?
   - ¿inotify local o S3 events?

2. **¿Formato del wiki?**
   - Estructura exacta de carpetas
   - Formato de frontmatter (tags, fechas, fuentes)
   - Convenciones de naming de archivos

3. **¿Alcance de formatos de archivo?**
   - Solo `.md` y `.txt`?
   - ¿PDFs? (requiere `pypdf`)
   - ¿Imágenes con OCR? (requiere `tesseract`)
   - ¿Links/URLs además de archivos?

4. **¿Pipeline automático o con confirmación?**
   - ¿El servicio procesa automáticamente cada archivo que cae en inbox?
   - ¿O prefiere un modelo "staging" donde revisa antes de escribir al wiki?

5. **¿Qué tan grande espera que crezca?**
   - ¿Decenas, cientos, o miles de páginas?
   - ¿Necesita búsqueda tipo qmd/tantivy? (Karpathy recomienda qmd para escalar)

6. **¿DeepSeek V4 Flash Free es suficiente?**
   - ¿O quiere poder cambiar de modelo fácilmente?
   - ¿OpenCode Zen como gateway único o múltiples proveedores?

7. **Presupuesto de infraestructura**
   - ¿Costo mensual esperado para API calls?
   - ¿Servidor dedicado o Cloud Run/VPS mínimo?

---

### 6. Next Steps & Recommendation

#### Enfoque recomendado para propuesta

**Enfoque B (Híbrido) con esta estructura**:

1. **Servicio base**: FastAPI con LangGraph como orquestador interno
2. **File watcher**: `watchdog` (no `pyinotify`) — soporta cross-platform y tiene modo polling para cloud
3. **LLM gateway**: OpenCode Zen API (OpenAI-compatible), modelo `deepseek-v4-flash-free`
4. **Persistencia**: Sistema de archivos local (markdown + YAML frontmatter), más SQLite para tracking de archivos procesados
5. **Arquitectura**: Adapter pattern para el observer (local inotify / cloud SNS+SQS)

#### Pipeline LangGraph (nodoso)

```
State schema:
  - file_path: str
  - source_hash: str
  - raw_text: Optional[str]
  - extracted_text: Optional[str]
  - classification: Optional[WikiClassification]
  - affected_pages: list[PageUpdate]
  - errors: list[str]

Nodes:
  validate_file   → verifica extensión, tamaño, duplicado (por hash)
  extract_text    → .md/.txt directo, .pdf con pypdf, img con OCR
  classify_content → llama a DeepSeek vía OpenCode Zen
  identify_affected_pages → lee index.md, compara con clasificación
  generate_updates → genera diff de páginas a escribir
  write_pages     → escribe/actualiza archivos .md en wiki/
  update_index    → actualiza index.md
  append_log      → escribe entrada en log.md
```

#### Pipeline mínimo viable (antes de LangGraph)

Para la primera iteración, sugiero **empezar SIN LangGraph** y migrar después si el flujo lo justifica. Un script CLI que:
1. Toma un file path
2. Extrae texto
3. Llama a DeepSeek vía OpenCode Zen
4. Escribe/actualiza páginas markdown en `wiki/`

Esto da valor inmediato y deja espacio para iterar el schema de clasificación antes de agregar la complejidad de LangGraph + inotify.

#### Orden recomendado de construcción

| Fase | Qué | Dependencias |
|------|-----|--------------|
| 0 | Setup: instalar pip, crear virtualenv, configurar OpenCode Zen API key | — |
| 1 | CLI de ingesta: extraer texto + clasificar + escribir wiki (sin watch) | httpx, pydantic, pyyaml |
| 2 | Agregar pipeline LangGraph con el mismo flujo | langgraph |
| 3 | Agregar file watcher (watchdog + polling mode) | watchdog |
| 4 | Agregar soporte para PDFs + OCR (si necesario) | pypdf, pytesseract |
| 5 | Agregar API web (FastAPI) | uvicorn, fastapi |
| 6 | Cloud deploy: adapter S3/webhook | — |
| 7 | lint automático periódico | — |
| 8 | Web UI básica | — |

---

### 7. Dependencies Graph (resumen para proposal)

```
llmwiki-ingesta
├── Python 3.14.4
├── pip (needs install)
├── langgraph          → orquestación del pipeline
├── watchdog            → file system events (inotify + polling)
├── httpx               → API calls to OpenCode Zen
├── pydantic            → schemas y validación
├── pyyaml              → frontmatter parsing
├── markdown            → markdown generation
├── tiktoken            → token counting
│
├── [optional] pypdf                → PDF extraction
├── [optional] pytesseract + tesseract → OCR
├── [optional] fastapi + uvicorn    → REST API
│
└── External:
    └── OpenCode Zen API → opencode.ai/zen/v1
        └── Model: deepseek-v4-flash-free
```

---

### 8. Conclusión

El proyecto es factible y la idea de Karpathy está bien documentada. El principal desafío técnico no es la clasificación por LLM (eso es directo) sino:

1. **El file watcher portable** (local vs cloud)
2. **Definir bien el schema de clasificación** para que el LLM produzca resultados consistentes
3. **Manejar el crecimiento del wiki** sin exceder contextos de 200K tokens

La recomendación es empezar simple (CLI de ingesta sin watch), validar con el usuario que la clasificación funciona para su dominio, y luego agregar automatización progresivamente.

**Estado**: Ready for Proposal.
**Siguiente fase**: sdd-propose → formalizar alcance y enfoque.
