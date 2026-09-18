# ADR-014: Conservative PDF layout trigger

## Status

Accepted — 2026-09-17

## Context

ADR-013 used missing native text as the only multimodal trigger. The reviewed
baseline showed a text-layer table whose PDF operators were ordered by column:
all tokens survived, but the row relationship did not. A pure text-presence
check therefore cannot establish that native extraction preserved visual
meaning.

## Decision

Analyze every PDF page with local `pypdf` geometry before choosing the extraction
path. Request multimodal extraction when any page has no visible text, at least
four table-like rectangles, a displayed image covering at least 8% of the page,
or a suspicious reading-order jump back toward the top of the page.

An upward jump is suspicious when consecutive content-stream text fragments
increase in vertical position by more than `max(12 points, 1.5% of page height)`.
This is deliberately a geometric warning, not proof that the text is wrong.
Record explicit reason codes for evaluation and diagnosis.

Keep ordinary prose on the native path. Copy only suspicious pages into a
temporary PDF for the structured multimodal adapter, pass an explicit original
page-number mapping, and merge validated results with the retained native pages.

## Consequences

- The known column-major table relationship is recovered by multimodal
  extraction, raising reviewed StructureRetention from 0.75 to 1.00.
- Pure text PDFs continue to avoid model cost and nondeterminism.
- False positives are possible for bordered forms, decorative rectangles, and
  intentionally non-linear pages; this is accepted in favor of not silently
  dropping important structure.
- Selective page extraction is now implemented: only flagged pages are copied
  into a temporary PDF, the provider must return their original page numbers,
  and those pages replace corresponding native text during a fail-closed merge.
  The five reviewed fixtures reduce provider-routed pages from five to four
  (20%); this is a page-count proxy, not a measured token, latency, or cost gain.
- The detector does not claim to understand semantics or prove visual quality;
  thresholds must be evaluated and tuned as the corpus grows.
