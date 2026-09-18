import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from time import perf_counter

import bm25s  # type: ignore[import-untyped]

DEFAULT_SIZES = (10, 100, 1_000, 5_000)
DEFAULT_REPEATS = 5
QUERIES = (
    "transaction rollback boundary",
    "DVX-4827 upload remediation",
    "embedding model compatibility",
    "Vite proxy FastAPI",
)
TOP_K = 20


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    chunk_count: int
    repeat_count: int
    tokenize_median_ms: float
    index_median_ms: float
    query_median_ms: float
    rebuild_median_ms: float


def make_corpus(chunk_count: int) -> list[str]:
    """Create deterministic benchmark load, not retrieval relevance judgments."""
    topics = (
        "transaction commit rollback database boundary",
        "DVX-4827 upload byte limit incident remediation",
        "embedding model dimension compatible vector search",
        "Vite development proxy forwards API requests to FastAPI",
        "document version chunk provenance character offsets",
    )
    padding = " ".join(f"term{number}" for number in range(80))
    return [
        f"chunk {index} {topics[index % len(topics)]} {padding}"
        for index in range(chunk_count)
    ]


def benchmark_size(
    chunk_count: int,
    *,
    repeats: int = DEFAULT_REPEATS,
) -> BenchmarkResult:
    if chunk_count <= 0:
        raise ValueError("chunk_count must be positive")
    if repeats <= 0:
        raise ValueError("repeats must be positive")

    corpus = make_corpus(chunk_count)
    tokenize_samples: list[float] = []
    index_samples: list[float] = []
    query_samples: list[float] = []

    for _ in range(repeats):
        started = perf_counter()
        corpus_tokens = bm25s.tokenize(
            corpus,
            stopwords=None,
            show_progress=False,
        )
        tokenize_samples.append(perf_counter() - started)

        retriever = bm25s.BM25(corpus=list(range(chunk_count)))
        started = perf_counter()
        retriever.index(corpus_tokens, show_progress=False)
        index_samples.append(perf_counter() - started)

        for query in QUERIES:
            query_tokens = bm25s.tokenize(
                query,
                stopwords=None,
                show_progress=False,
            )
            started = perf_counter()
            retriever.retrieve(
                query_tokens,
                k=min(TOP_K, chunk_count),
                show_progress=False,
            )
            query_samples.append(perf_counter() - started)

    tokenize_median = median(tokenize_samples)
    index_median = median(index_samples)
    return BenchmarkResult(
        chunk_count=chunk_count,
        repeat_count=repeats,
        tokenize_median_ms=tokenize_median * 1_000,
        index_median_ms=index_median * 1_000,
        query_median_ms=median(query_samples) * 1_000,
        rebuild_median_ms=(tokenize_median + index_median) * 1_000,
    )


def run_benchmark(
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    *,
    repeats: int = DEFAULT_REPEATS,
) -> list[BenchmarkResult]:
    return [benchmark_size(size, repeats=repeats) for size in sizes]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure bounded BM25S index rebuild and query cost"
    )
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=list(DEFAULT_SIZES),
    )
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    results = run_benchmark(tuple(args.sizes), repeats=args.repeats)
    rendered = (
        json.dumps(
            {
                "method": "bm25s_numpy",
                "top_k": TOP_K,
                "query_count_per_repeat": len(QUERIES),
                "results": [asdict(result) for result in results],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
