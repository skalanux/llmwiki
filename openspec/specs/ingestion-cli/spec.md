# ingestion-cli Specification

## Purpose

CLI entry point that accepts a file path and runs the full ingestion pipeline (extract → classify → generate wiki pages).

## Requirements

| # | Requirement | Strength | Scenarios |
|---|-------------|----------|-----------|
| 1 | The CLI MUST expose a `llmwiki-ingest` command via Typer with subcommands: `ingest FILE`, `watch DIRECTORY`, `config`, `status` | MUST | Happy, MissingFile, MissingAPIKey |
| 2 | Configuration MUST load from `.env` file and env vars: `DEEPSEEK_API_KEY`, `OPENCODE_ZEN_ENDPOINT` | MUST | Happy, MissingAPIKey |
| 3 | The default model MUST be `deepseek-v4-flash` unless overridden | MUST | Happy |
| 4 | The CLI SHOULD print progress via `rich` console | SHOULD | Happy |

### Requirement 1: CLI Entry Point

The system MUST expose `llmwiki-ingest` via Typer with commands: `ingest`, `watch`, `config`, `status`.

#### Scenario: Happy path — ingest a single file

- GIVEN a file at `~/inbox/note.md` and `DEEPSEEK_API_KEY` is set
- WHEN the user runs `llmwiki-ingest ingest ~/inbox/note.md`
- THEN the pipeline runs and exits with code 0
- AND a wiki page is written to `~/wiki/`

#### Scenario: Missing file

- GIVEN a path that does not exist
- WHEN the user runs `llmwiki-ingest ingest /nonexistent/file.md`
- THEN the CLI exits with code 1 and prints an error message

#### Scenario: Missing API key

- GIVEN no `DEEPSEEK_API_KEY` in env or `.env`
- WHEN the user runs `llmwiki-ingest ingest file.md`
- THEN the CLI exits with code 1 and prints "DEEPSEEK_API_KEY not configured"

### Requirement 2: Configuration

Configuration MUST load from `.env` then env vars, with env vars taking precedence.

#### Scenario: .env loading

- GIVEN a `.env` file with `DEEPSEEK_API_KEY=sk-test`
- WHEN the command starts
- THEN the key is available without being set in the shell environment

#### Scenario: Env var override

- GIVEN `.env` has `DEEPSEEK_API_KEY=sk-old` and env has `DEEPSEEK_API_KEY=sk-override`
- WHEN the command starts
- THEN `sk-override` is used
