# ADR-012: Evidence-triggered single corrective retrieval

## Status

Accepted — 2026-09-16

## Context

Retrieval can fail because a user's wording does not match indexed terminology.
Running query rewriting and a second retrieval for every answer would add model
cost and latency even when the first attempt already has sufficient evidence.
Allowing an open correction loop would also make cost and termination uncertain.

## Decision

Keep the existing grounded-answer path as the first attempt. Only when its
validated structured result reports `has_sufficient_evidence=false`, ask a
dedicated provider for one alternative standalone retrieval query and run the
same authorized answer path once more.

Skip the second retrieval when the rewrite is empty or unchanged. Preserve the
original KnowledgeBase scope, expose whether correction occurred and the exact
corrective query, and never attempt more than one correction.

## Consequences

- Successful first-pass questions pay no correction cost.
- A failed retrieval gets one terminology-focused recovery opportunity.
- Both attempts retain the existing workspace authorization and citation
  validation boundaries.
- Correction may still end with insufficient evidence; it must not invent an
  answer merely because a retry occurred.
- A live unknown-project case exercised the correction branch and correctly
  returned insufficient evidence without citations.
- One transient invalid-provider response returned a fail-closed `502` before
  the same request succeeded on retry; provider-contract observability belongs
  in Phase 16.
