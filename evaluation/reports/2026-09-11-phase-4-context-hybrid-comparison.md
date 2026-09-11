# Phase 4 adversarial context hybrid comparison

**Date:** 2026-09-11  
**Compared strategies:** BM25S lexical vs pgvector + BM25S RRF hybrid  
**Cases:** 5 reviewed adversarial questions  
**Corpus:** 3 isolated documents, 7 chunks  
**Provider calls for hybrid run:** 5 query embedding requests

## Results

| Metric | Lexical | Hybrid |
| --- | ---: | ---: |
| DocumentRecall@1 | 1.00 | 1.00 |
| DocumentMRR@5 | 1.00 | 1.00 |
| EvidenceHit@1 | 0.80 | 1.00 |
| EvidenceHit@3 | 1.00 | 1.00 |
| EvidenceHit@5 | 1.00 | 1.00 |
| Mean context budget utilization | 48.87% | 48.85% |
| Mean represented documents | 2.60 | 2.60 |
| Mean maximum same-document share | 52.00% | 52.00% |
| Mean overlapping characters | 240 | 240 |
| Cases with budget exclusions | 0.00% | 0.00% |

Hybrid moved the answer-bearing `context-rollback-authority` chunk from rank two
to rank one. The other four judged passages remained at rank one. The observed
lexical failure is therefore already resolved by the Phase 3 hybrid strategy.

## Decision

This controlled suite supports hybrid retrieval over lexical-only retrieval for
answer-bearing rank-one coverage. It does not show remaining relevance headroom
for a reranker: all five hybrid cases already place judged evidence first.

Context redundancy did not improve because RRF changes candidate order rather
than removing overlapping neighbors. The measured 240 overlapping characters
did not displace evidence, and the character budget was never binding. Do not
claim that a reranker or diversity policy improves this workload without a new
measured failure. A future NanoBEIR subset can supply broader public retrieval
coverage before a reranker package decision.

The small application-specific result is not a broad generalization claim and
must not be combined with Phase 2–3 or future public benchmark aggregates.
