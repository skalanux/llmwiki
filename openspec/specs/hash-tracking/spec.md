# hash-tracking Specification

## Purpose

Maintain a persistent database of file hashes (SHA-256) to avoid re-processing already-ingested files.

## Requirements

| # | Requirement | Strength | Scenarios |
|---|-------------|----------|-----------|
| 1 | The system MUST compute SHA-256 hash of file content before extraction | MUST | Happy, CorruptedDb |
| 2 | The system MUST persist hashes in a SQLite database at `~/.llmwiki/processed.sqlite` | MUST | FreshStart |
| 3 | The system MUST skip files whose hash already exists in the database | MUST | Duplicate |
| 4 | The system MUST handle a corrupted database gracefully (re-create with warning) | MUST | CorruptedDb |

### Requirement 1: Hash computation

The system MUST compute SHA-256 of raw file bytes before any processing.

#### Scenario: Hash computation

- GIVEN a file with known content
- WHEN the system reads the file
- THEN the SHA-256 hash matches the expected value

### Requirement 2: Persistence

The system MUST store hashes in a SQLite database for cross-session dedup.

#### Scenario: Fresh start

- GIVEN no database exists yet
- WHEN the system initializes
- THEN the database is created with the `processed_files` table

### Requirement 3: Dedup

The system MUST skip files whose hash is already recorded.

#### Scenario: File re-ingested

- GIVEN a file that was already processed (hash exists in DB)
- WHEN the system checks the hash
- THEN the file is skipped with a log message "Already processed, skipping"

### Requirement 4: Corruption handling

The system MUST recover from a corrupted hash database.

#### Scenario: Corrupted database

- GIVEN a corrupted SQLite file at the expected path
- WHEN the system attempts to open it
- THEN the system backs up the corrupted file and creates a fresh database
- AND a warning is logged

### Requirement 5: Hash record fields

Each record MUST store: file path, hash, file size, and timestamp.

#### Scenario: Record structure

- GIVEN a file is processed successfully
- WHEN the system persists the hash
- THEN the database contains a row with `path`, `hash`, `size`, and `processed_at`
