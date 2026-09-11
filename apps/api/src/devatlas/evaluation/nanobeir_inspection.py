from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Protocol, cast

SELECTED_TASKS = (
    "NanoSciFactRetrieval",
    "NanoNFCorpusRetrieval",
    "NanoHotpotQARetrieval",
)


class InvalidNanoBeirMetadataError(ValueError):
    """Raised when required MTEB descriptive statistics are absent."""


@dataclass(frozen=True, slots=True)
class TaskInspection:
    task_name: str
    split: str
    document_count: int
    query_count: int
    relevant_judgment_count: int
    character_count: int
    average_document_characters: float
    average_relevant_documents_per_query: float


class TaskMetadata(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def eval_splits(self) -> Sequence[str]: ...

    @property
    def descriptive_stats(self) -> Mapping[str, Mapping[str, Any]]: ...


def inspect_task(metadata: TaskMetadata) -> TaskInspection:
    if len(metadata.eval_splits) != 1:
        raise InvalidNanoBeirMetadataError(
            f"{metadata.name} must expose exactly one evaluation split"
        )
    split = metadata.eval_splits[0]
    try:
        stats = metadata.descriptive_stats[split]
        document_stats = cast(
            Mapping[str, Any], stats.get("documents_text_statistics") or {}
        )
        query_stats = cast(
            Mapping[str, Any], stats.get("queries_text_statistics") or {}
        )
        relevance_stats = cast(
            Mapping[str, Any], stats.get("relevant_docs_statistics") or {}
        )
        return TaskInspection(
            task_name=metadata.name,
            split=split,
            document_count=_required_int(
                stats.get("num_documents", document_stats.get("unique_texts")),
                "num_documents",
            ),
            query_count=_required_int(
                stats.get("num_queries", query_stats.get("unique_texts")),
                "num_queries",
            ),
            relevant_judgment_count=_required_int(
                stats.get(
                    "num_relevant_docs", relevance_stats.get("num_relevant_docs")
                ),
                "num_relevant_docs",
            ),
            character_count=_required_int(
                stats.get("number_of_characters"), "number_of_characters"
            ),
            average_document_characters=_required_float(
                stats.get(
                    "average_document_length",
                    document_stats.get("average_text_length"),
                ),
                "average_document_length",
            ),
            average_relevant_documents_per_query=_required_float(
                stats.get(
                    "average_relevant_docs_per_query",
                    relevance_stats.get("average_relevant_docs_per_query"),
                ),
                "average_relevant_docs_per_query",
            ),
        )
    except (KeyError, TypeError) as error:
        raise InvalidNanoBeirMetadataError(
            f"{metadata.name} has invalid descriptive statistics"
        ) from error


def build_report(inspections: Sequence[TaskInspection]) -> dict[str, Any]:
    return {
        "mteb_version": version("mteb"),
        "tasks": [asdict(item) for item in inspections],
        "totals": {
            "document_count": sum(item.document_count for item in inspections),
            "query_count": sum(item.query_count for item in inspections),
            "relevant_judgment_count": sum(
                item.relevant_judgment_count for item in inspections
            ),
            "character_count": sum(item.character_count for item in inspections),
        },
    }


def load_selected_inspections() -> list[TaskInspection]:
    try:
        import mteb
    except ImportError as error:
        raise RuntimeError(
            "NanoBEIR inspection requires the benchmark optional dependency"
        ) from error
    return [
        inspect_task(cast(TaskMetadata, mteb.get_task(task_name).metadata))
        for task_name in SELECTED_TASKS
    ]


def _required_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InvalidNanoBeirMetadataError(f"invalid {field}")
    return value


def _required_float(value: object, field: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool) or value < 0:
        raise InvalidNanoBeirMetadataError(f"invalid {field}")
    return float(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect selected NanoBEIR metadata")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = build_report(load_selected_inspections())
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
