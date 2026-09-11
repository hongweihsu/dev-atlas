# NanoBEIR three-task retrieval baseline — 2026-09-11

## Scope

This standard document-level run uses the official NanoBEIR corpus IDs, fifty
queries per task, and official relevance judgments. Documents are not processed
through DevAtlas ingestion or chunking, so these results evaluate retrieval
methods rather than the complete product pipeline.

- Dense model: `text-embedding-3-small`, 1,536 dimensions
- Lexical retriever: BM25S defaults
- Hybrid: reciprocal-rank fusion over the top 100 dense and lexical candidates,
  with rank constant 60
- Metrics: `ir-measures` nDCG@10 and Recall@10
- Dense input: 2,280,805 document tokens and 2,233 query tokens

## Results

| Task | Strategy | nDCG@10 | Recall@10 |
| --- | --- | ---: | ---: |
| NanoSciFact | BM25 | 0.7033 | 0.8300 |
|  | Dense | **0.7647** | **0.9000** |
|  | Hybrid RRF | 0.7635 | 0.8500 |
| NanoNFCorpus | BM25 | 0.3180 | 0.1135 |
|  | Dense | **0.3869** | **0.1699** |
|  | Hybrid RRF | 0.3774 | 0.1520 |
| NanoHotpotQA | BM25 | 0.8098 | 0.8800 |
|  | Dense | 0.7898 | 0.8200 |
|  | Hybrid RRF | **0.8444** | **0.9000** |

## Decision

The result supports keeping hybrid retrieval as a product capability, but not
claiming it is universally superior. Fixed RRF is strongest on NanoHotpotQA;
dense retrieval is strongest on SciFact and NFCorpus. The next useful
experiment is therefore query- or collection-aware strategy selection, or a
small fusion-weight comparison, rather than adding a reranker without evidence.

The run also exposed the account's one-million-token-per-minute limit. The
initial attempt completed and cached SciFact, then stopped during NFCorpus. The
runner now smooths requests below 800,000 tokens per minute. A resumed run reused
SciFact and completed the remaining caches; a final all-strategy run reported
cache hits for all six corpus/query entries and reproduced every score without
new embedding requests.

## Limits

- Three NanoBEIR tasks and 150 queries do not represent every search workload.
- No significance test is reported; metric differences should not be described
  as statistically significant.
- BM25S defaults and one fixed RRF configuration were measured; this is not a
  broad hyperparameter search.
- The estimated clean-pass embedding cost was USD $0.0457. Actual billing may be
  slightly higher because part of NFCorpus was sent before the rate-limit stop;
  provider billing, not this report, is authoritative.
