# Phase 5 NanoBEIR evaluation plan

**Status:** three-strategy baseline completed and reproduced from cache; BM25,
dense, and fixed-RRF hybrid results are recorded for all selected tasks.

## Selected tasks

| Task | Retrieval pattern | Documents | Queries | Reported characters |
| --- | --- | ---: | ---: | ---: |
| NanoSciFactRetrieval | Scientific claim-to-evidence retrieval | 2,919 | 50 | 4,182,563 |
| NanoNFCorpusRetrieval | Short medical/nutrition queries with many relevant documents | 2,953 | 50 | 4,468,144 |
| NanoHotpotQARetrieval | Multi-hop questions with two relevant documents per query | 5,090 | 50 | 1,784,059 |
| **Total** |  | **10,962** | **150** | **10,434,766** |

The tasks are intentionally different. SciFact tests long technical evidence,
NFCorpus tests short domain-specific queries and broad relevance sets, and
HotpotQA tests retrieval of multiple supporting documents. Each official task
contains only fifty queries, keeping repeated evaluation bounded.

Sources: [NanoSciFactRetrieval](https://huggingface.co/datasets/mteb/NanoSciFactRetrieval),
[NanoNFCorpusRetrieval](https://huggingface.co/datasets/mteb/NanoNFCorpusRetrieval),
and [NanoHotpotQARetrieval](https://huggingface.co/datasets/mteb/NanoHotpotQARetrieval).

## Two result classes

### Standard model/search evaluation

- Load official corpus, queries, and qrels through MTEB.
- Preserve official IDs and splits.
- Batch embeddings without sending documents through `POST /documents`.
- Report standard per-task nDCG@10, Recall@10, and diagnostic Recall@100.
- Compare BM25, dense retrieval, and RRF hybrid using the same cached document
  and query embeddings.
- Treat this as the closest result to the public benchmark protocol.

### DevAtlas end-to-end evaluation

- Optional follow-up after a safe bulk evaluation loader exists.
- Run documents through DevAtlas normalization, chunking, pgvector, BM25S, and
  chunk-to-document aggregation.
- Use a disposable evaluation database and preserve each official document ID
  in a manifest.
- Report results as DevAtlas pipeline metrics, not as leaderboard-equivalent
  NanoBEIR scores.

The current one-document ingestion endpoint must not be used for all 10,962
documents. It would create excessive per-document transactions and provider
requests and would measure HTTP ingestion overhead rather than retrieval
quality.

## Provider cost estimate

The selected corpora contain about 10.43 million characters. Using the rough
planning conversion of four characters per token gives about 2.61 million input
tokens before exact tokenizer measurement. At the current
`text-embedding-3-small` price of USD $0.02 per million input tokens, the rough
document-embedding estimate is USD $0.052. Reserve a USD $0.07 ceiling for
tokenization variance; query embeddings are negligible at this scale.

Official pricing source:
[text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small).

The local `text-embedding-3-small` tokenizer count is 2,280,805 document tokens
plus 2,233 query tokens. At the same list price, one uncached embedding pass is
approximately USD $0.0457. This remains an estimate rather than execution
approval because provider billing is authoritative and retries could add input.
The paid run remains gated on verifying batching and the reusable cache path.

## Implementation gate

1. Add MTEB to a benchmark-only optional group or environment. Version 2.20.11
   is Apache-2.0, but its core dependencies include datasets,
   sentence-transformers, transformers, torch, scikit-learn, scipy, and polars;
   it must not become a production API dependency.
2. Implement a deterministic dataset-inspection command that downloads the
   selected tasks and records exact counts without calling OpenAI. **Complete.**
3. Add cached, batched embedding adapters so vector and hybrid runs reuse the
   same vectors. **Cache and batching foundation complete.**
4. Run BM25 first, then request approval for the exact paid embedding run.
   **Complete.**
5. Reopen reranker selection only if hybrid has a repeatable per-task failure or
   meaningful nDCG/Recall headroom.

Official package metadata:
[MTEB pyproject](https://github.com/embeddings-benchmark/mteb/blob/main/pyproject.toml).

## Metadata inspection

Run the benchmark-only command without downloading corpus text or calling a
model provider:

```bash
cd apps/api
uv run --extra benchmark python -m devatlas.evaluation.nanobeir_inspection \
  --report ../../evaluation/runs/nanobeir-inspection.json
```

The ignored JSON output records the installed MTEB version and per-task plus
aggregate documents, queries, relevance judgments, characters, average document
length, and average relevant documents per query. MTEB currently emits a torch
`FutureWarning` during import on this environment; it does not change the
inspection result and is not suppressed by DevAtlas.

## Exact token inspection

Download/cache the selected public corpus text and count it with the embedding
model tokenizer, without calling OpenAI:

```bash
cd apps/api
uv run --extra benchmark python -m devatlas.evaluation.nanobeir_tokens \
  --report ../../evaluation/runs/nanobeir-tokens.json
```

| Task | Document tokens | Query tokens | Largest document |
| --- | ---: | ---: | ---: |
| NanoSciFactRetrieval | 895,976 | 985 | 1,881 |
| NanoNFCorpusRetrieval | 965,977 | 267 | 2,252 |
| NanoHotpotQARetrieval | 418,852 | 981 | 429 |
| **Total** | **2,280,805** | **2,233** | **2,252** |

The ignored JSON report also records deterministic SHA-256 fingerprints over
sorted official IDs and normalized title/text payloads. These fingerprints will
be part of the embedding-cache identity so changed corpus content cannot
silently reuse stale vectors.

## Embedding cache contract

`nanobeir_cache.py` orders records by official ID, embeds only on a cache miss,
validates every returned batch, converts vectors to compact float32 NumPy
arrays, and writes the manifest last. A cache identity includes task, split,
record kind, model, dimension, and content fingerprint. Cache hits therefore
cannot cross models, dimensions, datasets, corpus revisions, or corpus/query
boundaries.

Incomplete, incorrectly ordered, wrongly shaped, or non-finite cache entries
fail closed instead of silently triggering a paid replacement. This makes
cache damage visible and prevents an unnoticed provider call. Offline tests
verify deterministic batching, repeat-run reuse, fingerprint invalidation, and
incomplete-entry rejection.

## Baseline result

The dated [three-task report](reports/2026-09-11-nanobeir-three-task-baseline.md)
records the standard nDCG@10 and Recall@10 comparison. Dense retrieval wins on
SciFact and NFCorpus, while fixed-RRF hybrid wins on HotpotQA. This supports a
portfolio claim that the system measures strategy trade-offs; it does not
support claiming hybrid is always more accurate.
