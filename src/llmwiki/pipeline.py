"""LangGraph pipeline definition.

Holds the :class:`IngestionPipeline` that wires together the four sequential
nodes: Extract → Classify → Generate → Write, using LangGraph's ``StateGraph``.
"""
from __future__ import annotations

import logging
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from llmwiki.classifier import ClassifierService
from llmwiki.config import LLMWikiConfig
from llmwiki.extractors import get_extractor
from llmwiki.hash_tracker import HashTracker
from llmwiki.models import ClassificationResult
from llmwiki.state import State
from llmwiki.wiki_writer import WikiWriter
from llmwiki.youtube import enrich_with_transcripts

logger = logging.getLogger(__name__)


def _route_after_hash(state: State) -> str:
    """Return the next node after the hash check.

    If the file is a known duplicate (``skipped=True``) the graph goes
    directly to ``END``; otherwise it proceeds to ``extract``.
    """
    return "skip" if state.get("skipped") else "process"


class IngestionPipeline:
    """Orchestrates the end-to-end ingestion pipeline via LangGraph.

    Builds a four-node sequential graph:

    #. **Extract** — reads the source file and extracts raw text + metadata.
    #. **Classify** — sends the extracted text to an LLM for structured
       classification.
    #. **Generate** — produces a wiki markdown page from the classification.
    #. **Write** — records the file hash in the deduplication database.

    Usage::

        pipeline = IngestionPipeline(config)
        graph = pipeline.build_graph()
        result = await graph.ainvoke({...initial state...})
    """

    def __init__(self, config: LLMWikiConfig) -> None:
        self.config = config
        self.classifier = ClassifierService(config)
        self.writer = WikiWriter(config.resolved_wiki_dir)
        self.hash_tracker = HashTracker(self._resolve_hash_db())

    # ── Graph nodes ───────────────────────────────────────────────────

    async def hash_check_node(self, state: State) -> dict:
        """Check whether the file hash already exists in the tracking DB.

        If the hash is already recorded the pipeline is bypassed entirely
        (``skipped=True``) — no LLM calls or file writes occur.

        The computed hash is stored in ``state["hash"]`` so downstream
        nodes (specifically ``write_node``) can reuse it without re-reading
        the file.
        """
        file_path = Path(state["file_path"])

        if not file_path.exists():
            msg = f"File not found: {file_path}"
            logger.error(msg)
            return {"errors": state["errors"] + [msg], "skipped": True}

        try:
            file_hash = self._compute_hash(file_path)
            if self.hash_tracker.is_duplicate(file_hash):
                logger.info(
                    "Skipping %s — already processed (hash=%s…)",
                    file_path.name, file_hash[:12],
                )
                return {
                    "hash": file_hash,
                    "skipped": True,
                    "errors": state["errors"]
                    + [f"Skipped — already processed (hash: {file_hash[:12]})"],
                }
            return {"hash": file_hash, "skipped": False}
        except Exception as exc:
            logger.exception("Hash check failed for %s", file_path)
            return {"errors": state["errors"] + [f"Hash check failed: {exc}"], "skipped": True}

    async def extract_node(self, state: State) -> dict:
        """Extract raw text and metadata from the source file.

        Uses :func:`~llmwiki.extractors.get_extractor` to select the
        appropriate extractor based on file extension. Stores the extracted
        text, metadata (including the BLAKE2b hash), and hash in the state.

        On failure the error is appended to ``state["errors"]`` and the
        pipeline continues (subsequent nodes will find no text to process).
        """
        file_path = Path(state["file_path"])

        if not file_path.exists():
            msg = f"File not found: {file_path}"
            logger.error(msg)
            return {"errors": state["errors"] + [msg]}

        try:
            extractor = get_extractor(file_path)
            raw_text, metadata = await extractor.extract(file_path)

            # Enrich with YouTube transcripts if links are found
            enriched = enrich_with_transcripts(raw_text)
            if enriched != raw_text:
                logger.info(
                    "Enriched text with YouTube transcript(s) "
                    "(%d → %d chars)",
                    len(raw_text), len(enriched),
                )

            logger.info(
                "Extracted %d bytes from %s (hash=%s…)",
                len(raw_text), file_path.name, metadata.hash[:12],
            )
            return {
                "raw_text": enriched,
                "metadata": metadata,
                "hash": metadata.hash,
            }
        except ValueError as exc:
            logger.warning("No suitable extractor for %s: %s", file_path, exc)
            return {"errors": state["errors"] + [str(exc)]}
        except Exception as exc:
            logger.exception("Extraction failed for %s", file_path)
            return {"errors": state["errors"] + [f"Extraction failed: {exc}"]}

    async def classify_node(self, state: State) -> dict:
        """Send extracted text to the LLM for structured classification.

        Wraps the :class:`~llmwiki.models.LLMResponse` returned by the
        classifier together with the source metadata into a
        :class:`~llmwiki.models.ClassificationResult`.

        Requires ``state["raw_text"]`` to be populated by the extract node.
        """
        raw_text = state.get("raw_text")
        if not raw_text:
            return {"errors": state["errors"] + ["No text to classify"]}

        metadata = state.get("metadata")
        if metadata is None:
            return {"errors": state["errors"] + ["No metadata available"]}

        try:
            llm_response = await self.classifier.classify(
                raw_text, state["file_path"],
            )
            classification = ClassificationResult(
                metadata=metadata,
                classification=llm_response,
                wiki_path="",
            )
            logger.info(
                "Classified %s as '%s'",
                Path(state["file_path"]).name,
                llm_response.title or "(untitled)",
            )
            return {"classification": classification}
        except ValueError as exc:
            # Auth errors or missing API key
            logger.error("Classification config error: %s", exc)
            return {"errors": state["errors"] + [f"Classification config error: {exc}"]}
        except Exception as exc:
            logger.exception("Classification failed for %s", state["file_path"])
            return {"errors": state["errors"] + [f"Classification failed: {exc}"]}

    async def generate_node(self, state: State) -> dict:
        """Generate a wiki markdown page from the classification result.

        Delegates to :meth:`WikiWriter.write` which produces the YAML
        frontmatter, renders the markdown body, and writes the file to the
        configured wiki directory.

        Requires ``state["classification"]`` to be populated by the
        classify node.
        """
        classification = state.get("classification")
        if classification is None:
            return {"errors": state["errors"] + ["No classification to generate from"]}

        try:
            output_path = await self.writer.write(classification)
            logger.info("Wiki page written to %s", output_path)

            # Update the classification result with the final wiki path
            classification.wiki_path = output_path

            return {
                "classification": classification,
                "output_path": output_path,
            }
        except Exception as exc:
            logger.exception("Wiki generation failed for %s", state["file_path"])
            return {"errors": state["errors"] + [f"Wiki generation failed: {exc}"]}

    async def write_node(self, state: State) -> dict:
        """Record the processed file hash in the deduplication database.

        The duplicate check already happened in ``hash_check_node`` — this
        node only needs to persist the hash (together with the file size
        from the metadata) so future runs can skip this file.

        Uses ``INSERT OR IGNORE`` so concurrent runs do not cause errors.
        """
        file_hash = state.get("hash", "")
        output_path = state.get("output_path", "")

        if not file_hash:
            logger.warning("No hash to record — skipping write_node")
            return {}

        try:
            metadata = state.get("metadata")
            file_size = metadata.file_size if metadata else 0
            self.hash_tracker.record(
                file_hash,
                output_path or state["file_path"],
                file_size,
            )
            logger.info("Recorded hash %s for %s", file_hash[:12], output_path)
        except Exception as exc:
            logger.exception("Failed to record hash for %s", output_path)
            return {"errors": state["errors"] + [f"Hash recording failed: {exc}"]}

        return {}

    # ── Graph construction ────────────────────────────────────────────

    def build_graph(self) -> StateGraph:
        """Build and compile the LangGraph ``StateGraph``.

        The graph has a **hash check** guard node before extraction::

            START → hash_check → (conditional)
              ├── skipped=True  → END
              └── skipped=False → extract → classify → generate → write → END

        If the file hash already exists in the tracking database the
        pipeline bypasses extraction, classification, generation, and
        writing — saving LLM calls and disk I/O.
        """
        builder = StateGraph(State)
        builder.add_node("hash_check", self.hash_check_node)
        builder.add_node("extract", self.extract_node)
        builder.add_node("classify", self.classify_node)
        builder.add_node("generate", self.generate_node)
        builder.add_node("write", self.write_node)
        builder.add_edge(START, "hash_check")

        # Conditional routing: skip all processing for known hashes
        builder.add_conditional_edges(
            "hash_check",
            _route_after_hash,
            {
                "process": "extract",
                "skip": END,
            },
        )

        builder.add_edge("extract", "classify")
        builder.add_edge("classify", "generate")
        builder.add_edge("generate", "write")
        builder.add_edge("write", END)

        graph = builder.compile()
        logger.debug("Ingestion pipeline graph compiled")
        return graph

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def aclose(self) -> None:
        """Release all held resources (HTTP client, DB connection)."""
        await self.classifier.close()
        self.hash_tracker.close()

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _compute_hash(file_path: Path) -> str:
        """Compute the BLAKE2b hex digest of a file's raw bytes.

        Uses the same algorithm as :class:`~llmwiki.extractors.text.PlainTextExtractor`
        so the hash computed here will match the hash stored in the
        extraction metadata.
        """
        import hashlib

        raw_bytes = file_path.read_bytes()
        return hashlib.blake2b(raw_bytes).hexdigest()

    def _resolve_hash_db(self) -> Path:
        """Return the path to the hash-tracking SQLite database.

        The database lives at ``<base_dir>/data/hash.db``, where
        *base_dir* is the configured ``llmwiki_base_dir`` (or the current
        working directory if unset).
        """
        base = (
            Path(self.config.llmwiki_base_dir)
            if self.config.llmwiki_base_dir
            else Path.cwd()
        )
        return base / "data" / "hash.db"


async def run_pipeline(config: LLMWikiConfig, file_path: Path) -> dict:
    """Convenience wrapper — build, run, and clean up a pipeline instance.

    Creates an :class:`IngestionPipeline`, compiles the graph, invokes it
    with the proper initial state, and tears down all resources.

    Returns:
        The final ``State`` dictionary produced by ``graph.ainvoke()``.
        The caller should inspect ``result["skipped"]`` to determine
        whether the file was actually processed.
    """
    pipeline = IngestionPipeline(config)
    try:
        graph = pipeline.build_graph()
        initial_state: State = {
            "file_path": str(file_path),
            "hash": "",
            "raw_text": "",
            "metadata": None,
            "classification": None,
            "wiki_content": "",
            "output_path": "",
            "errors": [],
            "skipped": False,
        }
        return await graph.ainvoke(initial_state)
    finally:
        await pipeline.aclose()
