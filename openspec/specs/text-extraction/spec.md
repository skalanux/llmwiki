# text-extraction Specification

## Purpose

Read source files from disk, extract plain text, and return content with metadata for downstream classification.

## Requirements

| # | Requirement | Strength | Scenarios |
|---|-------------|----------|-----------|
| 1 | The system MUST extract plain text from `.md` and `.txt` files by reading raw content | MUST | HappyUtf8, Latin1 |
| 2 | The system MUST extract text from PDFs using docling | MUST | HappyPdf, CorruptedPdf |
| 3 | The system MUST extract text from images via OCR using docling/tesseract | MUST | HappyOcr, NoTesseract |
| 4 | The system MUST return metadata: source path, file type, size in bytes, and SHA-256 hash | MUST | HappyUtf8 |
| 5 | The system MUST handle UTF-8 and Latin-1 encodings for text files | MUST | HappyUtf8, Latin1 |

### Requirement 1: Text file extraction

The system MUST read `.md` and `.txt` files and return the raw text content.

#### Scenario: Happy path — UTF-8 markdown

- GIVEN a valid `.md` file encoded as UTF-8
- WHEN the system extracts text
- THEN the content matches the file's text exactly

#### Scenario: Latin-1 encoded text file

- GIVEN a `.txt` file encoded as Latin-1
- WHEN the system extracts text
- THEN the content is decoded correctly with no Unicode errors

### Requirement 2: PDF extraction

The system MUST extract text from PDFs via docling, returning a string.

#### Scenario: Happy path — PDF with selectable text

- GIVEN a PDF containing selectable text
- WHEN the system extracts text
- THEN the returned string contains readable paragraphs from the PDF

#### Scenario: Corrupted PDF

- GIVEN a PDF file that is truncated or corrupted
- WHEN the system extracts text
- THEN it raises an error and does not proceed to classification

### Requirement 3: Image OCR

The system MUST extract text from images via docling/tesseract OCR.

#### Scenario: Happy path — image with clear text

- GIVEN a PNG with clearly printed English text
- WHEN the system runs OCR
- THEN the returned string contains the visible text

#### Scenario: Tesseract not installed

- GIVEN an image file but Tesseract is not installed
- WHEN the system runs OCR
- THEN it raises a clear error instructing the user to install Tesseract

### Requirement 4: Metadata

The system MUST return metadata alongside extracted text.

#### Scenario: Complete metadata

- GIVEN a 1024-byte markdown file
- WHEN extraction completes
- THEN the result includes `source_path`, `file_type: ".md"`, `size: 1024`, and a valid SHA-256 hash
