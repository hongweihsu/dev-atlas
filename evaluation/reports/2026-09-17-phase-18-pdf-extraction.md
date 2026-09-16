# Phase 18 PDF extraction baseline — 2026-09-17

## Question

Does the native-first extraction policy preserve page provenance, exact tokens,
and table relationships across a small set of materially different PDFs, and
does it expose a concrete reason to broaden the multimodal trigger?

## Reviewed cases

| Case | PDF property | Expected path | Purpose |
| --- | --- | --- | --- |
| `native-table` | One-page text-layer table | native | Preserve cheap deterministic extraction |
| `scanned-table` | One-page image-only table and flow | multimodal | Recover OCR tokens and row relationships |
| `mixed-pages` | Native policy page plus scanned table page | multimodal | Preserve both pages when any page lacks text |
| `column-order-table` | Visual table whose PDF operators are column-major | native | Expose the current text-present/layout-broken boundary |

All fixtures were visually rendered and reviewed before the run. The two
multimodal cases contain generated, non-sensitive content.

## Metrics

| Metric | Result | Interpretation |
| --- | ---: | --- |
| PathAccuracy | 1.00 | All four cases took the intended current route |
| PageCoverage | 1.00 | Every expected one-based page span was retained |
| EvidenceRetention | 1.00 | All nine reviewed identifiers/values survived extraction |
| StructureRetention | 0.75 | Three of four reviewed row relationships remained contiguous |

The first run incorrectly reported `StructureRetention=0.25` because the judge
treated Markdown table pipes as meaningful characters. Human review showed the
rows were correct. The judge was fixed to normalize only `|` separators, then
the provider-backed run was repeated. This correction is part of the evaluation
evidence: a metric is not trustworthy until its failure examples are inspected.

## Concrete failure and decision

`column-order-table` retained `IDX-440`, `Degraded`, and `Search`, so token-level
evidence passed. Native extraction emitted headings and values by column,
however, so `Index builder IDX-440 Degraded Search` was no longer a contiguous
relationship. The current fallback did not run because the page was not empty.

This supports the next implementation experiment: detect suspicious native
table layout and selectively re-extract only those pages with multimodal vision.
It does not support sending every PDF to a model, nor does four generated cases
support a general PDF accuracy claim.

## Reproducibility and cost boundary

- Fixtures are reproducibly generated from versioned code and remain ignored
  local artifacts.
- The JSON report is ignored; this dated report records the reviewed aggregate
  and concrete failure.
- A fresh run makes two multimodal extraction calls. Native cases make none.
- Model output can vary, so future comparisons must retain case diagnostics and
  inspect changed failures rather than relying only on the aggregate.
