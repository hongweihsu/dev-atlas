# Controlled vector retrieval baseline — 2026-09-10

## Scope

- Database: freshly recreated local PostgreSQL volume
- Corpus: only the three controlled English documents in `evaluation/corpus/`
- Judgments: ten owner-reviewed document and exact-passage cases
- Retrieval: active-version pgvector cosine search
- Embedding: OpenAI `text-embedding-3-small`, 1,536 dimensions
- Candidate collection: top 20 chunks; only three chunks existed
- Answer-context cutoff: top 5 chunks

## Results

| Metric | Result |
| --- | ---: |
| DocumentRecall@1 | 1.00 |
| DocumentRecall@3 | 1.00 |
| DocumentMRR@5 | 1.00 |
| EvidenceHit@1 | 1.00 |
| EvidenceHit@3 | 1.00 |
| EvidenceHit@5 | 1.00 |

Every case placed its judged document and exact evidence passage first. The
ignored local JSON report retains every candidate rank and score.

## Limitations and next decision

This is a valid regression baseline for this exact corpus, not evidence of
general retrieval accuracy. Each controlled document produced one chunk, so the
document and evidence metrics cannot yet diverge. The perfect score shows that
changing retrieval algorithms on these ten cases would provide no measurable
gain.

The next retrieval comparison needs a small number of harder, multi-chunk or
lexically ambiguous cases derived from concrete product behavior. It should not
inflate the dataset merely to lower the score. The earlier mixed-index run also
showed that incomplete judgments make unrelated and potentially relevant
documents indistinguishable; future experiments must preserve corpus isolation
or supply judgments for the complete search scope.

## Reproduction note

After recreating the database volume, `alembic upgrade head` had to be run
manually before ingestion. This is recorded as a local startup workflow gap;
the failed pre-migration request did not persist a document.
