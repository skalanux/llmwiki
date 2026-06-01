# wiki-generation Specification

## Purpose

Take classification output and write/update interconnected markdown pages in the `wiki/` directory with YAML frontmatter, cross-links, and content sections.

## Requirements

| # | Requirement | Strength | Scenarios |
|---|-------------|----------|-----------|
| 1 | The system MUST write `.md` files with YAML frontmatter: `title`, `date`, `tags`, `source`, `hash` | MUST | Happy |
| 2 | The system MUST derive filenames by sanitizing the title (lowercase, replace spaces with hyphens) | MUST | Happy |
| 3 | The system MUST skip writing if a page exists with the same content hash | MUST | NoChange |
| 4 | The system MUST generate cross-links between related pages using `[[wikilink]]` syntax | MUST | Happy |
| 5 | The system SHOULD split content exceeding 2000 words into multiple pages with a parent index | SHOULD | LongContent |

### Requirement 1: YAML frontmatter

Every generated page MUST include standard YAML frontmatter.

#### Scenario: New page

- GIVEN a classification with `title: "RAG Architecture"`, `tags: ["rag", "search"]`, and a source file hash
- WHEN the system writes the page
- THEN `wiki/rag-architecture.md` contains frontmatter with `title`, `date`, `tags`, `source`, `hash`

### Requirement 2: Filename sanitization

Filenames MUST be derived from the classification title.

#### Scenario: Title with special chars

- GIVEN a title "What is RAG? (Retrieval-Augmented Gen)"
- WHEN the system generates the filename
- THEN the result is `what-is-rag-retrieval-augmented-gen.md`

### Requirement 3: Hash check

The system MUST compare the incoming classification's source hash against the existing page's frontmatter hash.

#### Scenario: No changes

- GIVEN an existing page with the same `hash` value as the current source file
- WHEN the system checks for changes
- THEN the page is NOT rewritten

### Requirement 4: Cross-links

The system MUST insert `[[wikilink]]` references to `related_pages` from the classification.

#### Scenario: Related pages exist

- GIVEN classification includes `related_pages: ["vector-databases", "embedding-models"]`
- WHEN the system generates content
- THEN the page contains `[[vector-databases]]` and `[[embedding-models]]` in the relevant sections

### Requirement 5: Content splitting

The system SHOULD split very long content into sub-pages.

#### Scenario: Long content split

- GIVEN a classification with content exceeding 2000 words
- WHEN the system generates pages
- THEN a parent index page is created with links to sub-pages
