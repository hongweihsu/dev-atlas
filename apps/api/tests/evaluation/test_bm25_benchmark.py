import pytest

from devatlas.evaluation.bm25_benchmark import benchmark_size, make_corpus


def test_make_corpus_is_deterministic_and_bounded() -> None:
    first = make_corpus(3)

    assert first == make_corpus(3)
    assert len(first) == 3
    assert all(len(chunk) < 1_000 for chunk in first)


def test_benchmark_returns_separate_non_negative_timings() -> None:
    result = benchmark_size(5, repeats=1)

    assert result.chunk_count == 5
    assert result.repeat_count == 1
    assert result.tokenize_median_ms >= 0
    assert result.index_median_ms >= 0
    assert result.query_median_ms >= 0
    assert result.rebuild_median_ms == pytest.approx(
        result.tokenize_median_ms + result.index_median_ms
    )


@pytest.mark.parametrize(("chunks", "repeats"), [(0, 1), (1, 0)])
def test_benchmark_rejects_non_positive_inputs(chunks: int, repeats: int) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        benchmark_size(chunks, repeats=repeats)
