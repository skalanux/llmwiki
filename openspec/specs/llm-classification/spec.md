# llm-classification Specification

## Purpose

Send extracted text to DeepSeek V4 Flash via the OpenCode Zen router and return structured classification: title, tags, summary, section breaks, and related pages.

## Requirements

| # | Requirement | Strength | Scenarios |
|---|-------------|----------|-----------|
| 1 | The system MUST send extracted text to an OpenAI-compatible API via the configured OpenCode Zen endpoint | MUST | Happy |
| 2 | The system MUST request structured JSON output with schema: `title`, `tags`, `summary`, `sections`, `related_pages` | MUST | Happy, PartialResponse |
| 3 | The system MUST handle token limits (truncate input to fit context budget) | MUST | OversizedInput |
| 4 | The system MUST retry on transient failures (timeout, 5xx) up to 3 times with exponential backoff | MUST | Timeout |
| 5 | The system MUST fail fast on auth errors (401, 403) without retrying | MUST | AuthError |

### Requirement 1: API call

The system MUST call `{OPENCODE_ZEN_ENDPOINT}/chat/completions` with the extracted text as user message.

#### Scenario: Happy path

- GIVEN extracted text under 4000 tokens and valid API credentials
- WHEN the system sends the classification request
- THEN the API returns a 200 with a structured JSON response

### Requirement 2: Structured output

The system MUST request and parse a JSON response matching the defined schema.

#### Scenario: Full valid response

- GIVEN a valid API response with all schema fields
- WHEN the system parses the response
- THEN it returns `Classification(title, tags, summary, sections, related_pages)`

#### Scenario: Partial or malformed JSON

- GIVEN an API response with missing fields or invalid JSON
- WHEN the system attempts to parse
- THEN it raises a `ClassificationError` and logs the raw response

### Requirement 3: Token limits

The system MUST use tiktoken to count tokens and truncate input if it exceeds the model's context window.

#### Scenario: Oversized input

- GIVEN extracted text exceeding 32k tokens
- WHEN the system prepares the request
- THEN the input is truncated from the middle to fit within budget
- AND a warning is logged

### Requirement 4: Retry logic

The system MUST retry on network errors and 5xx responses.

#### Scenario: Transient timeout

- GIVEN the API times out on the first attempt
- WHEN the system retries with exponential backoff
- THEN the third attempt succeeds
- AND no error is propagated

### Requirement 5: Auth errors

The system MUST NOT retry on 401 or 403 responses.

#### Scenario: Invalid API key

- GIVEN a 401 response from the API
- WHEN the system receives the response
- THEN it raises immediately without retrying
- AND the error message indicates an auth failure
