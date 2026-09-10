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

## Corrected three-way ablation

An owner review found that the original `vector-model` passage stated which
metadata was stored but did not answer why. The corpus now explicitly states
that the metadata prevents comparison between incompatible vector
configurations. The document was embedded as a new active version, and all
three strategies were rerun against the corrected judgment.

| Overall metric | Vector only | BM25 only | Hybrid RRF |
| --- | ---: | ---: | ---: |
| DocumentRecall@1 | 0.875 | 1.000 | 0.938 |
| DocumentMRR@5 | 0.927 | 1.000 | 0.938 |
| EvidenceHit@1 | 0.875 | 1.000 | 0.938 |
| DocumentRecall@3 | 1.000 | 1.000 | 1.000 |
| EvidenceHit@3 | 1.000 | 1.000 | 1.000 |
| EvidenceHit@5 | 1.000 | 1.000 | 1.000 |

| Semantic metric | Vector only | BM25 only | Hybrid RRF |
| --- | ---: | ---: | ---: |
| DocumentRecall@1 | 0.800 | 1.000 | 0.900 |
| DocumentMRR@5 | 0.883 | 1.000 | 0.900 |
| EvidenceHit@1 | 0.800 | 1.000 | 0.900 |

All three strategies scored 1.000 on identifier rank-one metrics.

## Per-case changes

- Vector-only placed `vector-model` third and `vector-provenance` second.
- Hybrid placed `vector-model` second and `vector-provenance` first.
- BM25-only placed all sixteen judged documents and evidence passages first.
- No strategy missed judged evidence within the top three.

Hybrid improved both document and evidence rank-one retrieval over vector-only
and preserved identifier performance, but it did not outperform BM25-only on
this corpus. The current English dataset has substantial query/document
vocabulary overlap and is therefore not strong evidence of semantic and lexical
complementarity. Hybrid remains implemented as a product capability, but the
measured claim must include this limitation.

## Implementation observations

BM25S may return zero-score rows to fill the requested `k`; DevAtlas removes
those rows before fusion so a lexical non-match cannot receive RRF credit. Raw
BM25 and cosine scores are not directly comparable, so RRF combines only their
rank positions using stable chunk UUIDs.

The initial adapter rebuilds the in-memory BM25 index from active chunks for
each request. This guarantees fresh results after document changes but leaves
latency and memory scaling unmeasured. Index lifecycle optimization should be
driven by a benchmark rather than assumed necessary from this small corpus.
