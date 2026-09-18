# BM25S index lifecycle benchmark — 2026-09-11

## Question

Does the first hybrid-search slice need an in-memory BM25 index cache now, or
is rebuilding the index per request still acceptable for its bounded corpus?

## Method

- Runtime: Python 3.13.2 on macOS 15.5 arm64
- Package: BM25S 0.3.11, NumPy backend
- Corpus: deterministic synthetic chunks below the production 1,000-character
  chunk limit; generated only as benchmark load, not relevance judgments
- Sizes: 10, 100, 1,000, and 5,000 chunks
- Repeats: 5 per size; values are medians
- Queries: 4 fixed technical queries per repeat
- Retrieval cutoff: top 20
- Excluded: database fetch, network, concurrency, and process memory

## Results

| Chunks | Tokenize median | Index median | Rebuild median | Query median |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 0.12 ms | 0.18 ms | 0.30 ms | 0.023 ms |
| 100 | 1.20 ms | 1.52 ms | 2.72 ms | 0.025 ms |
| 1,000 | 11.25 ms | 14.92 ms | 26.17 ms | 0.029 ms |
| 5,000 | 59.16 ms | 81.30 ms | 140.46 ms | 0.040 ms |

Index rebuild cost grew roughly with corpus size in this bounded run, while the
measured query operation remained below 0.05 ms. At 5,000 chunks, rebuilding
adds about 140 ms before database and application overhead, making per-request
rebuild unsuitable as a scaling design.

## Decision

Do not add cache invalidation and concurrent refresh logic for the current
eleven-chunk corpus. Keep the simple fresh-snapshot implementation through the
first single-user slice.

Revisit the index lifecycle before the corpus reaches 1,000 active chunks or
when measured BM25 rebuild p95 exceeds 25 ms under a representative workload.
At that point compare a versioned in-process snapshot with a persistent search
index such as ParadeDB. The final choice must also measure database fetch,
memory, concurrent reads during refresh, and document update/delete behavior.

## Reproduction

```bash
cd apps/api
uv run python -m retrieval_works.evaluation.bm25_benchmark \
  --report ../../evaluation/runs/bm25-index-benchmark.json
```

The JSON output is local and ignored; this report contains the portable result
and its limitations.
