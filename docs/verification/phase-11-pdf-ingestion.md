# Phase 11 PDF ingestion verification

## Implemented slice

- `.txt` remains limited to 1 MiB; text-based `.pdf` is limited to 10 MiB.
- `pypdf` extracts each page and normalization joins non-empty pages without
  inventing OCR content.
- Every PDF chunk stores nullable one-based `page_start` and `page_end`; legacy
  text chunks keep both values null.
- Search context, answer citations, API responses, and React source labels carry
  the page range.
- Malformed, encrypted, and scanned-only/no-text PDFs have distinct stable
  validation codes.

## Evidence

- A generated two-page PDF extracted both sentences and exact spans: page 1
  `[0, 57)`, page 2 `[59, 109)`.
- PostgreSQL migration `e62d7a4c9031` completed upgrade, downgrade, and re-upgrade.
- Backend: Ruff and strict mypy pass; 182 tests pass, five environment-gated
  tests skip, and two unrelated Redis lifespan tests were excluded in the
  restricted runner.
- Frontend: lint, typecheck, 13 tests, and production build pass.

## Honest boundary

This slice supports PDFs with an extractable text layer. OCR for scanned images,
tables-as-structured-data, figures, and layout-aware retrieval remain future
multimodal work and are not claimed here.
