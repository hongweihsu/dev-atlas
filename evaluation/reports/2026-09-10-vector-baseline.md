# Vector retrieval baseline — 2026-09-10

## Scope

- Corpus: three controlled English documents in `evaluation/corpus/`
- Judgments: ten owner-reviewed document and exact-passage cases
- Retrieval: active-version pgvector cosine search
- Embedding: OpenAI `text-embedding-3-small`, 1,536 dimensions
- Candidate collection: top 20 chunks
- Evaluated answer-context cutoff: top 5 chunks
- Code: local commit `7a48142`

## Results

| Metric | Result |
| --- | ---: |
| DocumentRecall@1 | 0.80 |
| DocumentRecall@3 | 0.90 |
| DocumentMRR@5 | 0.87 |
| EvidenceHit@1 | 0.80 |
| EvidenceHit@3 | 0.90 |
| EvidenceHit@5 | 1.00 |

## Interpretation

For eight of ten questions, both the expected source document and an exact
answer-bearing passage ranked first. Nine of ten found them within the first
three results, and all ten found an answer-bearing passage within the five-chunk
answer-context cutoff.

These values describe only this small controlled corpus. They are a regression
baseline for comparing later retrieval changes, not a claim of general search
accuracy. This first report did not retain per-case rankings, so it cannot yet
identify the two below-top-one cases or the one below-top-three case. The runner
should persist per-case results before the next paid run.

## Reproduction

With the local API running and provider credentials configured:

```bash
cd apps/api
uv run --extra evaluation python -m devatlas.evaluation.retrieval \
  ../../evaluation/retrieval-cases.jsonl \
  --corpus ../../evaluation/corpus \
  --manifest ../../evaluation/runs/manifest.json
```

The manifest is intentionally ignored because its UUIDs belong to one local
database instance.
