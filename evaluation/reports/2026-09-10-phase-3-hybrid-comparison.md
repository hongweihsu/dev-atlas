# Phase 3 hybrid retrieval comparison — 2026-09-10

## Scope

- Corpus: five controlled documents and eleven deterministic chunks
- Judgments: sixteen owner-reviewed cases (ten semantic, six identifier)
- Vector retriever: pgvector cosine similarity
- Lexical retriever: BM25S over current active chunks
- Fusion: reciprocal rank fusion with rank constant 60
- Candidate collection: up to 20 candidates from each retriever
- Answer-context cutoff: top 5 fused chunks
- Embedding: OpenAI `text-embedding-3-small`, 1,536 dimensions

## Vector-only versus hybrid

| Scope and metric | Vector only | Hybrid | Change |
| --- | ---: | ---: | ---: |
| Overall DocumentRecall@1 | 0.875 | 0.938 | +0.063 |
| Overall DocumentMRR@5 | 0.927 | 0.938 | +0.010 |
| Overall EvidenceHit@1 | 0.875 | 0.938 | +0.063 |
| Semantic DocumentRecall@1 | 0.800 | 0.900 | +0.100 |
| Semantic DocumentMRR@5 | 0.883 | 0.900 | +0.017 |
| Semantic EvidenceHit@1 | 0.800 | 0.900 | +0.100 |
| Identifier DocumentRecall@1 | 1.000 | 1.000 | 0.000 |
| Identifier DocumentMRR@5 | 1.000 | 1.000 | 0.000 |
| Identifier EvidenceHit@1 | 1.000 | 1.000 | 0.000 |

DocumentRecall@3 and EvidenceHit@3/@5 remained 1.000 in every scope.

## Per-case changes

- `vector-model`: judged document and evidence improved from rank 3 to rank 2.
- `vector-provenance`: judged document and evidence improved from rank 2 to
  rank 1.
- The other fourteen cases retained rank 1.
- No identifier case regressed.

The result supports keeping hybrid retrieval for this controlled DevAtlas
workload: lexical evidence improved the two previously weak semantic cases while
preserving exact-token performance. It does not prove that the same improvement
generalizes to a larger or multilingual corpus.

## Implementation observations

BM25S may return zero-score rows to fill the requested `k`; DevAtlas removes
those rows before fusion so a lexical non-match cannot receive RRF credit. Raw
BM25 and cosine scores are not directly comparable, so RRF combines only their
rank positions using stable chunk UUIDs.

The initial adapter rebuilds the in-memory BM25 index from active chunks for
each request. This guarantees fresh results after document changes but leaves
latency and memory scaling unmeasured. Index lifecycle optimization should be
driven by a benchmark rather than assumed necessary from this small corpus.
