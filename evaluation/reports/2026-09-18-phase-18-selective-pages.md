# Phase 18 selective-page PDF routing — 2026-09-18

## Decision

Keep deterministic native extraction for trusted pages and send only pages
flagged by reviewed layout signals to multimodal extraction. Construct a
temporary PDF containing those pages, preserve an explicit mapping to original
page numbers, and fail closed if the provider omits, duplicates, reorders, or
adds a page. Merge validated multimodal pages with untouched native text before
chunking and embedding.

## Offline routing evidence

The same five generated, human-reviewed fixtures used by the Phase 18 layout
evaluation produced these routes:

| Fixture | Total pages | Selected pages | Signal |
| --- | ---: | --- | --- |
| `native-text.pdf` | 1 | none | none |
| `native-table.pdf` | 1 | 1 | table graphics |
| `scanned-table.pdf` | 1 | 1 | no text, large image |
| `mixed-pages.pdf` | 2 | 2 | no text, large image |
| `column-order-table.pdf` | 1 | 1 | table graphics, suspicious reading order |

Among documents requiring multimodal extraction, whole-document fallback would
send five pages and selective routing sends four: a 20% reduction in routed
pages. The mixed fixture improves from two routed pages to one. This measures
page routing only; it is not evidence of a 20% token, latency, or dollar-cost
reduction.

## Provider-backed regression

Offline tests verify physical PDF page selection, original-page mapping,
native/multimodal merge, continuous provenance spans, and fail-closed duplicate
handling. After explicit approval to transmit only these generated fixtures, a
provider-backed rerun produced:

| Metric | Result |
| --- | ---: |
| PathAccuracy | 1.00 |
| PageCoverage | 1.00 |
| EvidenceRetention | 1.00 |
| StructureRetention | 1.00 |

Selective routing therefore retained every reviewed metric from the preceding
whole-document layout-trigger run while routing four rather than five pages to
the provider. Five controlled synthetic cases do not establish general PDF
accuracy or a measured token, latency, or cost reduction.
