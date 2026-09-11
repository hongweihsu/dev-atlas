from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, cast

from devatlas.evaluation.nanobeir_inspection import SELECTED_TASKS

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

type TokenEncoder = Callable[[str], Sequence[int]]


class LoadedRetrievalTask(Protocol):
    corpus: Mapping[str, Mapping[str, Mapping[str, str]]]
    queries: Mapping[str, Mapping[str, str]]


@dataclass(frozen=True, slots=True)
class TaskTokenInspection:
    task_name: str
    split: str
    document_count: int
    query_count: int
    document_tokens: int
    query_tokens: int
    maximum_document_tokens: int
    corpus_sha256: str
    queries_sha256: str


def inspect_task_tokens(
    *,
    task_name: str,
    split: str,
    corpus: Mapping[str, Mapping[str, str]],
    queries: Mapping[str, str],
    encode: TokenEncoder,
) -> TaskTokenInspection:
    document_texts = {
        document_id: _document_text(record)
        for document_id, record in corpus.items()
    }
    document_token_counts = [
        len(encode(text)) for text in document_texts.values()
    ]
    query_token_counts = [len(encode(text)) for text in queries.values()]
    return TaskTokenInspection(
        task_name=task_name,
        split=split,
        document_count=len(document_texts),
        query_count=len(queries),
        document_tokens=sum(document_token_counts),
        query_tokens=sum(query_token_counts),
        maximum_document_tokens=max(document_token_counts, default=0),
        corpus_sha256=_fingerprint(document_texts),
        queries_sha256=_fingerprint(queries),
    )


def build_token_report(
    inspections: Sequence[TaskTokenInspection],
    *,
    embedding_model: str,
) -> dict[str, Any]:
    document_tokens = sum(item.document_tokens for item in inspections)
    query_tokens = sum(item.query_tokens for item in inspections)
    return {
        "embedding_model": embedding_model,
        "tasks": [asdict(item) for item in inspections],
        "totals": {
            "document_count": sum(item.document_count for item in inspections),
            "query_count": sum(item.query_count for item in inspections),
            "document_tokens": document_tokens,
            "query_tokens": query_tokens,
            "all_tokens": document_tokens + query_tokens,
        },
    }


def load_selected_token_inspections(
    *,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> list[TaskTokenInspection]:
    try:
        import mteb
        import tiktoken
    except ImportError as error:
        raise RuntimeError(
            "token inspection requires the benchmark optional dependencies"
        ) from error

    encoding = tiktoken.encoding_for_model(embedding_model)
    results: list[TaskTokenInspection] = []
    for task_name in SELECTED_TASKS:
        task = mteb.get_task(task_name)
        task.load_data()
        split = task.metadata.eval_splits[0]
        loaded_task = cast(LoadedRetrievalTask, task)
        corpus = loaded_task.corpus[split]
        queries = loaded_task.queries[split]
        results.append(
            inspect_task_tokens(
                task_name=task_name,
                split=split,
                corpus=corpus,
                queries=queries,
                encode=lambda text: encoding.encode(text, disallowed_special=()),
            )
        )
        task.unload_data()
    return results


def _document_text(record: Mapping[str, str]) -> str:
    parts = [record.get(field, "").strip() for field in ("title", "text")]
    return "\n".join(part for part in parts if part)


def _fingerprint(records: Mapping[str, str]) -> str:
    digest = sha256()
    for record_id, text in sorted(records.items()):
        for value in (record_id, text):
            encoded = value.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, byteorder="big"))
            digest.update(encoded)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download selected NanoBEIR text and count embedding tokens"
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    args = parser.parse_args()
    report = build_token_report(
        load_selected_token_inspections(embedding_model=args.embedding_model),
        embedding_model=args.embedding_model,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
