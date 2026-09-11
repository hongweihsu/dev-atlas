from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import pytest

from devatlas.evaluation.nanobeir_inspection import (
    InvalidNanoBeirMetadataError,
    TaskInspection,
    build_report,
    inspect_task,
)


@dataclass(frozen=True)
class FakeMetadata:
    name: str
    eval_splits: Sequence[str]
    descriptive_stats: Mapping[str, Mapping[str, Any]]


def test_inspect_task_supports_nested_mteb_statistics() -> None:
    metadata = FakeMetadata(
        name="NanoExampleRetrieval",
        eval_splits=("train",),
        descriptive_stats={
            "train": {
                "number_of_characters": 4200,
                "documents_text_statistics": {
                    "unique_texts": 20,
                    "average_text_length": 200.0,
                },
                "queries_text_statistics": {"unique_texts": 5},
                "relevant_docs_statistics": {
                    "num_relevant_docs": 8,
                    "average_relevant_docs_per_query": 1.6,
                },
            }
        },
    )

    assert inspect_task(metadata) == TaskInspection(
        task_name="NanoExampleRetrieval",
        split="train",
        document_count=20,
        query_count=5,
        relevant_judgment_count=8,
        character_count=4200,
        average_document_characters=200.0,
        average_relevant_documents_per_query=1.6,
    )


def test_inspect_task_supports_flat_mteb_statistics() -> None:
    metadata = FakeMetadata(
        name="NanoLegacyRetrieval",
        eval_splits=("train",),
        descriptive_stats={
            "train": {
                "num_documents": 10,
                "num_queries": 2,
                "num_relevant_docs": 4,
                "number_of_characters": 1000,
                "average_document_length": 95.0,
                "average_relevant_docs_per_query": 2.0,
            }
        },
    )

    inspection = inspect_task(metadata)

    assert inspection.document_count == 10
    assert inspection.average_relevant_documents_per_query == 2.0


def test_inspect_task_rejects_missing_required_statistics() -> None:
    metadata = FakeMetadata(
        name="BrokenRetrieval",
        eval_splits=("train",),
        descriptive_stats={"train": {}},
    )

    with pytest.raises(InvalidNanoBeirMetadataError, match="num_documents"):
        inspect_task(metadata)


def test_build_report_aggregates_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devatlas.evaluation.nanobeir_inspection.version", lambda _: "2.20.11"
    )
    inspections = [
        TaskInspection("one", "train", 10, 2, 3, 1000, 95.0, 1.5),
        TaskInspection("two", "train", 20, 4, 8, 2200, 105.0, 2.0),
    ]

    report = build_report(inspections)

    assert report["mteb_version"] == "2.20.11"
    assert report["totals"] == {
        "document_count": 30,
        "query_count": 6,
        "relevant_judgment_count": 11,
        "character_count": 3200,
    }
