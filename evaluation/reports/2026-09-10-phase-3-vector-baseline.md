# Phase 3 stratified vector baseline — 2026-09-10

## Scope

- Database: isolated local PostgreSQL corpus created for retrieval evaluation
- Corpus: five controlled documents and eleven deterministic chunks
- Judgments: sixteen owner-reviewed cases (ten semantic, six identifier)
- Retrieval: active-version pgvector cosine search
- Embedding: OpenAI `text-embedding-3-small`, 1,536 dimensions
- Candidate collection: top 20 chunks
- Answer-context cutoff: top 5 chunks

## Results

| Scope | DocumentRecall@1 | DocumentRecall@3 | DocumentMRR@5 | EvidenceHit@1 | EvidenceHit@3 | EvidenceHit@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall (16) | 0.875 | 1.000 | 0.927 | 0.875 | 1.000 | 1.000 |
| Semantic (10) | 0.800 | 1.000 | 0.883 | 0.800 | 1.000 | 1.000 |
| Identifier (6) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

All six exact-identifier cases placed the judged evidence first. The expanded
dataset therefore did not manufacture a lexical failure: vector retrieval
already handles these particular identifiers well.

Two semantic cases were weaker. `vector-model` placed the judged vector-search
evidence third, behind chunks from the API contract registry and operations
runbook. `vector-provenance` placed it second, behind the API contract registry.
Every judged passage still appeared within the top-three context candidates.

## Phase 3 decision

Hybrid retrieval remains a product requirement because DevAtlas must support
both semantic descriptions and exact technical tokens. This result is the
comparison baseline, not a claim that BM25 will improve every category.

The hybrid experiment must report semantic and identifier results separately.
It succeeds only if it improves or preserves useful retrieval behavior without
hiding a regression in one category behind gains in the other. Per-case ranks
must remain available when aggregate metrics tie.

## Limitations

The corpus and judgments are deliberately small and English-heavy. The result
is a regression signal for the implemented DevAtlas behavior, not a general
retrieval benchmark. It does not measure latency, index-update cost, generated
answer quality, or multilingual tokenization.
