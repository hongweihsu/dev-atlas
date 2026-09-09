# Phase 1 Acceptance Record

- **Date:** 2026-09-09
- **Scope:** single-user UTF-8 text ingestion, document replacement, active-version
  retrieval, grounded answer citations, and stable validation failures
- **Data:** purpose-built synthetic text with no private source material

## Automated evidence

- Backend Ruff formatting/lint and strict mypy passed.
- 119 routine backend tests passed with paid/external providers mocked.
- Three PostgreSQL integration tests passed, including the atomic
  Version 1 inactive / Version 2 active transition and duplicate rejection.
- Frontend ESLint and TypeScript passed.
- Seven React component tests passed, covering health feedback, initial upload,
  replacement upload, duplicate feedback, grounded citations, and answer errors.
- The Vite production build passed, and the initial live layout was inspected in
  the browser at desktop width.

## Controlled live evidence

The local Docker stack received a synthetic Version 1 text file and returned
`201 ready`, one chunk, and `version_number: 1`. Uploading changed synthetic
content to `/documents/{document_id}/versions` returned `201 ready` with the
same document identity and `version_number: 2`.

A subsequent grounded question cited the active Version 2, Chunk 0, offsets
0–481, and returned `has_sufficient_evidence: true`. This confirms endpoint
wiring and provenance; it is not a retrieval-quality benchmark.

Two live failure paths were exercised:

- Re-uploading the same normalized Version 2 content returned
  `409 duplicate_document_content`.
- Uploading a `.pdf` with `application/pdf` returned `415 unsupported_type`.

## Remaining human interaction checkpoint

The native operating-system file picker cannot be automated through the
available browser safety boundary. The React file-input behavior is covered by
component tests with browser `File` and `FormData` objects, but the owner should
perform one final click-through upload before recording a portfolio demo.
