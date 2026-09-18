# NanoBEIR three-task retrieval baseline — 2026-09-11

## Scope

This standard document-level run uses the official NanoBEIR corpus IDs, fifty
queries per task, and official relevance judgments. Documents are not processed
through Retrieval Works ingestion or chunking, so these results evaluate retrieval
methods rather than the complete product pipeline.

- Dense model: `text-embedding-3-small`, 1,536 dimensions
- Lexical retriever: BM25S defaults
- Hybrid: reciprocal-rank fusion over the top 100 dense and lexical candidates,
  with rank constant 60
- Metrics: `ir-measures` nDCG@10 and Recall@10
- Dense input: 2,280,805 document tokens and 2,233 query tokens

## Results

| Task | Strategy | nDCG@10 | Recall@10 | Recall@100 |
| --- | --- | ---: | ---: | ---: |
| NanoSciFact | BM25 | 0.7033 | 0.8300 | 0.9000 |
|  | Dense | **0.7647** | **0.9000** | 0.9600 |
|  | Hybrid RRF | 0.7635 | 0.8500 | **0.9800** |
| NanoNFCorpus | BM25 | 0.3180 | 0.1135 | 0.2069 |
|  | Dense | **0.3869** | **0.1699** | **0.3501** |
|  | Hybrid RRF | 0.3774 | 0.1520 | 0.3157 |
| NanoHotpotQA | BM25 | 0.8098 | 0.8800 | **0.9500** |
|  | Dense | 0.7898 | 0.8200 | 0.9400 |
|  | Hybrid RRF | **0.8444** | **0.9000** | **0.9500** |

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

NFCorpus Recall@10 needs additional context: its fifty queries average 50.36
relevant documents, and 34 queries have more than ten. Because a top-ten result
cannot retrieve more than ten documents, even perfect ordering has a mean
Recall@10 ceiling of 0.5342 on this slice. Its dense Recall@10 of 0.1699 still
leaves improvement room, but it must not be compared directly with a task that
has only one or two relevant documents per query.

At depth 100, NFCorpus dense recall rises to 0.3501 (versus a 0.9481 mean
theoretical ceiling). This shows that deeper candidate collection recovers more
relevant material, while also confirming a real domain-retrieval gap. Because
dense remains better than both BM25 and fixed RRF at depths 10 and 100, the
bounded decision is to avoid global RRF tuning solely for NFCorpus and continue
the product roadmap. Future domain-specific work can reopen this result.

## Limits

- Three NanoBEIR tasks and 150 queries do not represent every search workload.
- No significance test is reported; metric differences should not be described
  as statistically significant.
- BM25S defaults and one fixed RRF configuration were measured; this is not a
  broad hyperparameter search.
- The estimated clean-pass embedding cost was USD $0.0457. Actual billing may be
  slightly higher because part of NFCorpus was sent before the rate-limit stop;
  provider billing, not this report, is authoritative.
