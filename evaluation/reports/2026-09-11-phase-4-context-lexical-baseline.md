# Phase 4 adversarial context lexical baseline

**Date:** 2026-09-11  
**Strategy:** BM25S lexical retrieval  
**Cases:** 5 reviewed adversarial questions  
**Corpus:** 3 isolated documents, 7 chunks  
**Answer context:** top 5 chunks, 12,000-character budget

## Purpose

This run tests whether document-level success hides chunk-order or context
construction problems. It is a small application-specific diagnostic suite,
not a public benchmark or a claim of broad generalization.

## Controlled setup

The first execution revealed unrelated active documents in the normal
development database and was retained only as a mixed-index observation. The
reported run used a separate `devatlas_phase4` database containing only the
three reviewed corpus documents. Existing embeddings for those exact records
were copied into the isolated database, avoiding duplicate provider calls.

## Results

| Metric | Result |
| --- | ---: |
| DocumentRecall@1 | 1.00 |
| DocumentRecall@3 | 1.00 |
| DocumentMRR@5 | 1.00 |
| EvidenceHit@1 | 0.80 |
| EvidenceHit@3 | 1.00 |
| EvidenceHit@5 | 1.00 |
| Mean selected chunks | 5.00 |
| Mean context budget utilization | 48.87% |
| Mean represented documents | 2.60 |
| Mean maximum same-document share | 52.00% |
| Mean overlapping characters | 240 |
| Cases with budget exclusions | 0.00% |

`context-rollback-authority` exposed the only answer-bearing rank-one failure.
BM25 ranked a keyword-heavy overview chunk first and the precise authorization
rule second. The correct evidence still entered the five-chunk answer context.
The other four answer-bearing passages ranked first.

## Decision

The current 12,000-character budget is not binding, so budget expansion or
truncation logic is not justified. Neighboring chunk overlap is measurable but
did not remove judged evidence from context. Before adding a reranker, compare
hybrid retrieval on the same isolated corpus and check whether it already moves
the authorization rule to rank one. If the failure remains, use this case as
the first reranker acceptance test.

Do not combine these metrics with the Phase 2–3 regression set or a future
NanoBEIR result.
