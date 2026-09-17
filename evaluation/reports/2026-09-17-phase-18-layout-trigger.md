# Phase 18 PDF layout-trigger comparison — 2026-09-17

## Question

Can inexpensive PDF geometry detect cases where a text layer exists but native
extraction may lose a table or reading order, while retaining a native path for
ordinary prose?

## Change

Before accepting native extraction, each page is inspected for four conservative
signals: no visible text, at least four table-like rectangles, a rendered image
covering at least 8% of the page, or a text-content sequence that jumps upward by
more than `max(12 points, 1.5% of page height)`. The last signal catches the
common column-major pattern: the content stream reaches the bottom of one column
and then returns to the top of the next.

Any signal currently sends the bounded whole PDF through multimodal extraction.
This favors evidence retention; selective page-only re-extraction remains a
future cost optimization.

## Reviewed comparison

| Case | Layout reason | Route after change | Structural result |
| --- | --- | --- | --- |
| `native-text` | none | native | no table judgment |
| `native-table` | `table_graphics` | multimodal | retained |
| `scanned-table` | `no_text`, `large_image` | multimodal | retained |
| `mixed-pages` | page 2: `no_text`, `large_image` | multimodal | retained |
| `column-order-table` | `table_graphics`, `suspicious_reading_order` | multimodal | retained |

| Metric | Text-presence baseline | Layout trigger |
| --- | ---: | ---: |
| PathAccuracy | 1.00 | 1.00 |
| PageCoverage | 1.00 | 1.00 |
| EvidenceRetention | 1.00 | 1.00 |
| StructureRetention | 0.75 | 1.00 |

The provider-backed run recovered `Index builder → IDX-440 → Degraded → Search`
as one row, removing the single reviewed structural failure. The five-case suite
is diagnostic evidence for this design choice, not a general PDF-accuracy claim.

## Trade-offs

- Ordinary prose remains deterministic, local, and free of model calls.
- Four of five current fixtures use multimodal extraction, versus two of four in
  the initial baseline, so structure retention improved by spending more provider
  calls on documents with visual structure.
- Rectangle and upward-jump thresholds are heuristics. Bordered forms, decorative
  boxes, or intentionally non-linear layouts can produce false positives.
- Reason codes make routing decisions inspectable and support later threshold
  tuning against a larger, representative corpus.
