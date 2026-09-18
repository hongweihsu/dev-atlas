from retrieval_works.evaluation.nanobeir_tokens import (
    TaskTokenInspection,
    build_token_report,
    inspect_task_tokens,
)


def character_encoder(text: str) -> list[int]:
    return list(range(len(text)))


def test_inspect_task_tokens_counts_title_text_and_queries() -> None:
    inspection = inspect_task_tokens(
        task_name="NanoExampleRetrieval",
        split="train",
        corpus={
            "doc-2": {"_id": "doc-2", "title": "Title", "text": "Body"},
            "doc-1": {"_id": "doc-1", "text": "Short"},
        },
        queries={"query-1": "Find it"},
        encode=character_encoder,
    )

    assert inspection.document_count == 2
    assert inspection.query_count == 1
    assert inspection.document_tokens == 15
    assert inspection.query_tokens == 7
    assert inspection.maximum_document_tokens == 10
    assert len(inspection.corpus_sha256) == 64
    assert len(inspection.queries_sha256) == 64


def test_fingerprint_is_stable_across_mapping_order() -> None:
    first = inspect_task_tokens(
        task_name="task",
        split="train",
        corpus={"b": {"text": "two"}, "a": {"text": "one"}},
        queries={},
        encode=character_encoder,
    )
    second = inspect_task_tokens(
        task_name="task",
        split="train",
        corpus={"a": {"text": "one"}, "b": {"text": "two"}},
        queries={},
        encode=character_encoder,
    )

    assert first.corpus_sha256 == second.corpus_sha256


def test_build_token_report_aggregates_document_and_query_tokens() -> None:
    inspections = [
        TaskTokenInspection("one", "train", 10, 2, 100, 5, 20, "a", "b"),
        TaskTokenInspection("two", "train", 20, 4, 250, 10, 30, "c", "d"),
    ]

    report = build_token_report(
        inspections,
        embedding_model="text-embedding-3-small",
    )

    assert report["totals"] == {
        "document_count": 30,
        "query_count": 6,
        "document_tokens": 350,
        "query_tokens": 15,
        "all_tokens": 365,
    }
