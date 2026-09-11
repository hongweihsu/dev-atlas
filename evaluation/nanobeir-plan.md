# Phase 5 NanoBEIR evaluation plan

**Status:** task selection and cost gate; no dataset downloaded and no provider
calls made.

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
- Report standard per-task nDCG@10 and Recall@10.
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

This estimate is not execution approval. Before the paid run, load only dataset
metadata/text locally, count exact tokens with the model tokenizer, verify
batching and cache paths, and present the final estimate.

## Implementation gate

1. Add MTEB to a benchmark-only optional group or environment. Version 2.20.11
   is Apache-2.0, but its core dependencies include datasets,
   sentence-transformers, transformers, torch, scikit-learn, scipy, and polars;
   it must not become a production API dependency.
2. Implement a deterministic dataset-inspection command that downloads the
   selected tasks and records exact counts without calling OpenAI.
3. Add cached, batched embedding adapters so vector and hybrid runs reuse the
   same vectors.
4. Run BM25 first, then request approval for the exact paid embedding run.
5. Reopen reranker selection only if hybrid has a repeatable per-task failure or
   meaningful nDCG/Recall headroom.

Official package metadata:
[MTEB pyproject](https://github.com/embeddings-benchmark/mteb/blob/main/pyproject.toml).
