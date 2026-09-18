from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, cast

import bm25s  # type: ignore[import-untyped]
import ir_measures
import numpy as np
import tiktoken
from ir_measures import Recall, nDCG
from numpy.typing import NDArray
from openai import AsyncOpenAI

from retrieval_works.evaluation.nanobeir_cache import (
    EmbeddingCacheIdentity,
    NumpyEmbeddingCache,
    embed_records_with_cache,
)
from retrieval_works.evaluation.nanobeir_inspection import SELECTED_TASKS
from retrieval_works.evaluation.nanobeir_tokens import (
    document_text,
    fingerprint_records,
)
from retrieval_works.infrastructure.embedding.openai import OpenAIEmbeddingProvider

Strategy = Literal["lexical", "dense", "hybrid"]
METRIC_DEPTH = 10
FUSION_CANDIDATES = 100


class LoadedRetrievalTask(Protocol):
    corpus: Mapping[str, Mapping[str, Mapping[str, str]]]
    queries: Mapping[str, Mapping[str, str]]
    relevant_docs: Mapping[str, Mapping[str, Mapping[str, int]]]


@dataclass(frozen=True, slots=True)
class StrategyMetrics:
    ndcg_at_10: float
    recall_at_10: float
    recall_at_100: float


@dataclass(frozen=True, slots=True)
class TaskBenchmarkResult:
    task_name: str
    split: str
    document_count: int
    query_count: int
    metrics: dict[Strategy, StrategyMetrics]
    corpus_cache_hit: bool | None
    query_cache_hit: bool | None


class TokenPacedEmbeddingProvider:
    """Smooth benchmark traffic below the configured provider TPM limit."""

    def __init__(
        self, provider: OpenAIEmbeddingProvider, *, tokens_per_minute: int
    ) -> None:
        if tokens_per_minute <= 0:
            raise ValueError("tokens_per_minute must be greater than zero")
        self._provider = provider
        self._tokens_per_minute = tokens_per_minute
        self._encoding = tiktoken.encoding_for_model(provider.model)

    @property
    def model(self) -> str:
        return self._provider.model

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = await self._provider.embed(texts)
        token_count = sum(
            len(self._encoding.encode(text, disallowed_special=())) for text in texts
        )
        await asyncio.sleep(60 * token_count / self._tokens_per_minute)
        return vectors


def reciprocal_rank_fusion_ids(
    *rankings: Sequence[str],
    limit: int = METRIC_DEPTH,
    rank_constant: int = 60,
) -> list[str]:
    scores: dict[str, float] = {}
    best_rank: dict[str, int] = {}
    for ranking in rankings:
        for rank, document_id in enumerate(ranking, start=1):
            scores[document_id] = scores.get(document_id, 0.0) + 1.0 / (
                rank_constant + rank
            )
            best_rank[document_id] = min(best_rank.get(document_id, rank), rank)
    return sorted(scores, key=lambda key: (-scores[key], best_rank[key], key))[:limit]


def calculate_metrics(
    qrels: Mapping[str, Mapping[str, int]],
    rankings: Mapping[str, Sequence[str]],
) -> StrategyMetrics:
    run = {
        query_id: {
            document_id: float(len(ranking) - rank)
            for rank, document_id in enumerate(ranking)
        }
        for query_id, ranking in rankings.items()
    }
    results = ir_measures.calc_aggregate(
        [nDCG @ 10, Recall @ 10, Recall @ 100], dict(qrels), run
    )
    return StrategyMetrics(
        ndcg_at_10=float(results[nDCG @ 10]),
        recall_at_10=float(results[Recall @ 10]),
        recall_at_100=float(results[Recall @ 100]),
    )


def lexical_rankings(
    corpus: Mapping[str, str], queries: Mapping[str, str], *, limit: int
) -> dict[str, list[str]]:
    document_ids = sorted(corpus)
    query_ids = sorted(queries)
    retriever = bm25s.BM25()
    retriever.index(
        bm25s.tokenize([corpus[key] for key in document_ids], show_progress=False),
        show_progress=False,
    )
    results, _ = retriever.retrieve(
        bm25s.tokenize([queries[key] for key in query_ids], show_progress=False),
        corpus=document_ids,
        k=min(limit, len(document_ids)),
        show_progress=False,
    )
    return {
        query_id: [str(document_id) for document_id in row]
        for query_id, row in zip(query_ids, results, strict=True)
    }


def dense_rankings(
    *,
    document_ids: Sequence[str],
    query_ids: Sequence[str],
    document_vectors: NDArray[np.float32],
    query_vectors: NDArray[np.float32],
    limit: int,
) -> dict[str, list[str]]:
    document_norms = np.linalg.norm(document_vectors, axis=1, keepdims=True)
    query_norms = np.linalg.norm(query_vectors, axis=1, keepdims=True)
    if np.any(document_norms == 0) or np.any(query_norms == 0):
        raise ValueError("dense ranking cannot normalize a zero vector")
    similarities = (query_vectors / query_norms) @ (document_vectors / document_norms).T
    depth = min(limit, len(document_ids))
    return {
        query_id: [document_ids[index] for index in _stable_top_indices(row, depth)]
        for query_id, row in zip(query_ids, similarities, strict=True)
    }


def _stable_top_indices(scores: NDArray[np.float32], limit: int) -> list[int]:
    return sorted(range(len(scores)), key=lambda index: (-scores[index], index))[:limit]


async def run_task(
    *,
    task_name: str,
    strategies: Sequence[Strategy],
    cache: NumpyEmbeddingCache,
    provider: TokenPacedEmbeddingProvider | None,
    batch_size: int,
) -> TaskBenchmarkResult:
    import mteb

    task = mteb.get_task(task_name)
    task.load_data()
    split = task.metadata.eval_splits[0]
    loaded = cast(LoadedRetrievalTask, task)
    corpus = {key: document_text(value) for key, value in loaded.corpus[split].items()}
    queries = dict(loaded.queries[split])
    qrels = loaded.relevant_docs[split]

    needed_depth = FUSION_CANDIDATES if "hybrid" in strategies else METRIC_DEPTH
    lexical = (
        lexical_rankings(corpus, queries, limit=needed_depth)
        if "lexical" in strategies or "hybrid" in strategies
        else None
    )
    dense: dict[str, list[str]] | None = None
    corpus_hit: bool | None = None
    query_hit: bool | None = None
    if "dense" in strategies or "hybrid" in strategies:
        if provider is None:
            raise ValueError("dense and hybrid strategies require a provider")
        document_vectors, corpus_hit = await embed_records_with_cache(
            records=corpus,
            identity=EmbeddingCacheIdentity(
                task_name,
                split,
                "corpus",
                provider.model,
                provider.dimension,
                fingerprint_records(corpus),
            ),
            provider=provider,
            cache=cache,
            batch_size=batch_size,
        )
        query_vectors, query_hit = await embed_records_with_cache(
            records=queries,
            identity=EmbeddingCacheIdentity(
                task_name,
                split,
                "queries",
                provider.model,
                provider.dimension,
                fingerprint_records(queries),
            ),
            provider=provider,
            cache=cache,
            batch_size=batch_size,
        )
        dense = dense_rankings(
            document_ids=sorted(corpus),
            query_ids=sorted(queries),
            document_vectors=document_vectors,
            query_vectors=query_vectors,
            limit=needed_depth,
        )

    metrics: dict[Strategy, StrategyMetrics] = {}
    if "lexical" in strategies:
        assert lexical is not None
        metrics["lexical"] = calculate_metrics(qrels, lexical)
    if "dense" in strategies:
        assert dense is not None
        metrics["dense"] = calculate_metrics(qrels, dense)
    if "hybrid" in strategies:
        assert lexical is not None and dense is not None
        hybrid = {
            query_id: reciprocal_rank_fusion_ids(
                dense[query_id], lexical[query_id], limit=FUSION_CANDIDATES
            )
            for query_id in queries
        }
        metrics["hybrid"] = calculate_metrics(qrels, hybrid)
    task.unload_data()
    return TaskBenchmarkResult(
        task_name, split, len(corpus), len(queries), metrics, corpus_hit, query_hit
    )


async def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    strategies = cast(list[Strategy], args.strategy)
    provider = None
    if "dense" in strategies or "hybrid" in strategies:
        provider = TokenPacedEmbeddingProvider(
            OpenAIEmbeddingProvider(
                AsyncOpenAI(), model=args.model, dimension=args.dimension
            ),
            tokens_per_minute=args.tokens_per_minute,
        )
    cache = NumpyEmbeddingCache(args.cache_directory)
    results = [
        await run_task(
            task_name=task_name,
            strategies=strategies,
            cache=cache,
            provider=provider,
            batch_size=args.batch_size,
        )
        for task_name in SELECTED_TASKS
    ]
    return {
        "model": args.model,
        "dimension": args.dimension,
        "tasks": [asdict(r) for r in results],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the selected NanoBEIR slice")
    parser.add_argument(
        "--strategy",
        action="append",
        choices=("lexical", "dense", "hybrid"),
        default=None,
    )
    parser.add_argument("--model", default="text-embedding-3-small")
    parser.add_argument("--dimension", type=int, default=1536)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--tokens-per-minute", type=int, default=800_000)
    parser.add_argument(
        "--cache-directory",
        type=Path,
        default=Path("../../evaluation/runs/nanobeir-cache"),
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.strategy is None:
        args.strategy = ["lexical", "dense", "hybrid"]
    report = asyncio.run(run_benchmark(args))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
