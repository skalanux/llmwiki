# file-watching Specification

## Purpose

Monitor a directory for new or modified files and automatically trigger the ingestion pipeline.

## Requirements

| # | Requirement | Strength | Scenarios |
|---|-------------|----------|-----------|
| 1 | The system MUST watch a configurable directory using `watchdog` | MUST | Happy |
| 2 | The system MUST trigger ingestion on `IN_CLOSE_WRITE` events | MUST | Happy |
| 3 | The system MUST debounce rapid writes with a configurable cooldown (default 5s) | MUST | RapidWrites |
| 4 | The system MUST ignore temp/swap files (`.swp`, `~`, `.tmp`) | MUST | TempFile |
| 5 | The system SHOULD use `watchdog`'s native observer (fallback to polling) | SHOULD | NoInotify |

### Requirement 1: Directory watching

The system MUST start a watchdog observer on the configured directory.

#### Scenario: Happy path

- GIVEN `INBOX_DIR` is set to `~/inbox`
- WHEN the user runs `llmwiki-ingest watch`
- THEN the system begins watching `~/inbox`

### Requirement 2: Event filtering

The system MUST react only to `IN_CLOSE_WRITE` events (file finished writing).

#### Scenario: File created and written

- GIVEN a file `note.md` is being copied to the watched directory
- WHEN the write completes (IN_CLOSE_WRITE fires)
- THEN the ingestion pipeline is triggered for that file

### Requirement 3: Debounce

The system MUST debounce repeated events for the same file within the cooldown period.

#### Scenario: Rapid successive writes

- GIVEN an editor that saves the same file 3 times in 2 seconds
- WHEN the cooldown is 5 seconds
- THEN ingestion runs exactly once

### Requirement 4: Temp file filtering

The system MUST ignore files matching temp file patterns.

#### Scenario: Vim swap file

- GIVEN a file `.note.md.swp` appears in the watched directory
- WHEN the event fires
- THEN the system ignores the event

### Requirement 5: Fallback observer

The system SHOULD fall back to `PollingObserver` if `inotify` is unavailable.

#### Scenario: No inotify on filesystem

- GIVEN a directory on NFS or FUSE that does not support inotify
- WHEN the watcher starts
- THEN the system falls back to polling without error
