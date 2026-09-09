# Retrieval evaluation

Phase 2 begins with a deliberately small, reviewed regression set. It measures
whether vector search places a relevant document near the top; it does not yet
judge generated answer quality.

## Dataset contract

`retrieval-cases.jsonl` contains one JSON object per query:

- `case_id`: unique stable identifier for the case
- `query`: text sent to `POST /search`
- `relevant_documents`: one or more relevant document titles

The three files in `corpus/` form the controlled corpus. Upload them as new
documents without overriding their default titles, so the resulting titles are
`transactions`, `vite-proxy`, and `vector-search`. Keep these titles unique in
the database used for evaluation.

The initial ten questions cover three concrete Phase 1 topics. They are small
enough to review manually. Add a case only when a real requirement, bug, or
retrieval failure justifies it.

## Run the baseline

Start the API with OpenAI embeddings configured, upload the three corpus files,
then run:

```bash
cd apps/api
uv run --extra evaluation python -m devatlas.evaluation.retrieval \
  ../../evaluation/retrieval-cases.jsonl
```

Use `--base-url` if the API is not at `http://localhost:8000`.

The runner requests five chunks per query, collapses repeated chunks from the
same document, and reports document-level `Recall@1`, `Recall@3`, and `MRR@5`.
This distinction matters: otherwise several chunks from one document could
occupy several ranks and distort a document-retrieval measurement.

## Package decision

DevAtlas uses `ir-measures` for standard deterministic information-retrieval
metrics. It is installed only through the API project's `evaluation` optional
dependency, not in the production runtime. LLM-based answer judges are deferred
until generation evaluation has a concrete need and a reviewed rubric.

No baseline score should be recorded until the controlled corpus has been
uploaded and the command has completed against live retrieval.
