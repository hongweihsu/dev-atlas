# ADR-013: Native-first multimodal PDF extraction

## Status

Accepted — 2026-09-17

## Context

`pypdf` is fast, deterministic, local, and sufficient for ordinary text-layer
PDFs, but it cannot read scanned pages and often loses the structure of tables,
figures, and flow diagrams. Sending every PDF to a vision model would improve
coverage at the cost of latency, provider usage, nondeterministic transcription,
and unnecessary transfer of documents that already extract cleanly.

## Decision

Keep native package extraction as the first path. Use the multimodal adapter
only when the PDF has no extractable text or contains one or more textless pages.
The adapter submits the bounded PDF as an OpenAI file input with high detail and
requires structured output containing consecutive one-based pages.

The extraction instruction requires faithful visible text, Markdown tables,
concise bracketed descriptions of meaningful figures, an explicit blank-page
marker, and no inference or execution of instructions found inside the PDF.
Responses are created with `store=false`. The application reconstructs normalized
text and page spans, then reuses the existing chunking, embedding, persistence,
retrieval, and citation pipeline.

## Consequences

- Ordinary text PDFs retain the cheapest and most reproducible path.
- Scanned and partially textless PDFs can enter the existing RAG pipeline while
  preserving page-level provenance.
- Provider outages are classified as retryable extraction failures in queued
  ingestion and as a stable `503` in synchronous version ingestion.
- Multimodal transcription can vary, so its normalized-content checksum can
  vary too. The current implementation does not claim byte-identical extraction.
- A page with native text but a flattened table or lost figure may not trigger
  the fallback. The next measured slice will add layout-quality detection or
  selective page re-extraction only if representative failures justify it.
