# Mixed-index retrieval observation — 2026-09-10

## Scope

- Judged corpus: three controlled English documents in `evaluation/corpus/`
- Other indexed content: five pre-existing, unjudged development documents
- Judgments: ten owner-reviewed document and exact-passage cases for the
  controlled corpus only
- Retrieval: unscoped active-version pgvector cosine search
- Embedding: OpenAI `text-embedding-3-small`, 1,536 dimensions
- Candidate collection: top 20 chunks
- Evaluated answer-context cutoff: top 5 chunks

## Observed values

| Metric | Result |
| --- | ---: |
| DocumentRecall@1 | 0.80 |
| DocumentRecall@3 | 0.90 |
| DocumentMRR@5 | 0.87 |
| EvidenceHit@1 | 0.80 |
| EvidenceHit@3 | 0.90 |
| EvidenceHit@5 | 1.00 |

These are retained as observed values, not accepted as the controlled baseline.
The relevance judgments do not cover the five pre-existing documents, so an
unjudged result may contain valid evidence and cannot safely be treated as
irrelevant.

## Per-case diagnosis

- `tx-rollback`: the judged `transactions` document and passage ranked second,
  behind the pre-existing `Retrieval Works Live Verification` document.
- `vector-provenance`: the judged `vector-search` document and passage ranked
  fifth, behind four historical documents all titled `phase-1-browser-check`.
  Those four results had the same similarity and may be duplicate or equally
  relevant content.
- The other eight cases placed the judged document and exact passage first.

The first aggregate-only execution exposed the issue, and a second approved
ten-query execution retained the individual ranks in the ignored local report.

## Decision

Do not delete or relabel existing development data to improve the score. Run the
accepted baseline against an isolated evaluation database containing only the
controlled corpus, or introduce an explicit authorized search scope in a later
product phase. Post-filtering the current top 20 would not faithfully measure
the API's actual retrieval behavior.
