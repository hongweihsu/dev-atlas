from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import ir_measures
from ir_measures import RR, Recall

DEFAULT_SEARCH_LIMIT = 5


class InvalidEvaluationDatasetError(ValueError):
    """Raised when a retrieval case cannot be evaluated safely."""


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    case_id: str
    query: str
    relevant_documents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RankedDocument:
    document_title: str
    score: float


def load_cases(path: Path) -> list[RetrievalCase]:
    cases: list[RetrievalCase] = []
    seen_ids: set[str] = set()

    with path.open(encoding="utf-8") as dataset:
        for line_number, raw_line in enumerate(dataset, start=1):
            if not raw_line.strip():
                continue
            try:
                value: Any = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise InvalidEvaluationDatasetError(
                    f"line {line_number} is not valid JSON"
                ) from error
            case = _parse_case(value, line_number=line_number)
            if case.case_id in seen_ids:
                raise InvalidEvaluationDatasetError(
                    f"line {line_number} repeats case_id {case.case_id!r}"
                )
            seen_ids.add(case.case_id)
            cases.append(case)

    if not cases:
        raise InvalidEvaluationDatasetError("dataset must contain at least one case")
    return cases


def score_rankings(
    cases: Sequence[RetrievalCase],
    rankings: Mapping[str, Sequence[RankedDocument]],
) -> dict[str, float]:
    qrels = [
        ir_measures.Qrel(case.case_id, title, 1)
        for case in cases
        for title in case.relevant_documents
    ]
    run = [
        ir_measures.ScoredDoc(case.case_id, result.document_title, result.score)
        for case in cases
        for result in rankings.get(case.case_id, ())
    ]
    recall_at_1 = Recall @ 1
    recall_at_3 = Recall @ 3
    reciprocal_rank_at_5 = RR @ DEFAULT_SEARCH_LIMIT
    measured = ir_measures.calc_aggregate(
        [recall_at_1, recall_at_3, reciprocal_rank_at_5], qrels, run
    )
    return {
        "Recall@1": measured[recall_at_1],
        "Recall@3": measured[recall_at_3],
        "MRR@5": measured[reciprocal_rank_at_5],
    }


def fetch_rankings(
    cases: Iterable[RetrievalCase],
    *,
    base_url: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> dict[str, list[RankedDocument]]:
    rankings: dict[str, list[RankedDocument]] = {}
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        for case in cases:
            response = client.post(
                "/search", json={"query": case.query, "limit": limit}
            )
            response.raise_for_status()
            rows = response.json()["results"]
            rankings[case.case_id] = _unique_documents(rows)
    return rankings


def _unique_documents(rows: Iterable[dict[str, Any]]) -> list[RankedDocument]:
    results: list[RankedDocument] = []
    seen_titles: set[str] = set()
    for row in rows:
        title = str(row["document_title"])
        if title in seen_titles:
            continue
        seen_titles.add(title)
        results.append(RankedDocument(title, float(row["similarity"])))
    return results


def _parse_case(value: Any, *, line_number: int) -> RetrievalCase:
    if not isinstance(value, dict):
        raise InvalidEvaluationDatasetError(f"line {line_number} must be an object")
    case_id = value.get("case_id")
    query = value.get("query")
    relevant = value.get("relevant_documents")
    if not isinstance(case_id, str) or not case_id.strip():
        raise InvalidEvaluationDatasetError(
            f"line {line_number} needs a non-empty case_id"
        )
    if not isinstance(query, str) or not query.strip():
        raise InvalidEvaluationDatasetError(
            f"line {line_number} needs a non-empty query"
        )
    if (
        not isinstance(relevant, list)
        or not relevant
        or any(not isinstance(title, str) or not title.strip() for title in relevant)
    ):
        raise InvalidEvaluationDatasetError(
            f"line {line_number} needs non-empty relevant_documents"
        )
    if len(set(relevant)) != len(relevant):
        raise InvalidEvaluationDatasetError(
            f"line {line_number} repeats a relevant document"
        )
    return RetrievalCase(case_id.strip(), query.strip(), tuple(relevant))


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure live document retrieval")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    rankings = fetch_rankings(cases, base_url=args.base_url)
    report = {
        "case_count": len(cases),
        "search_limit": DEFAULT_SEARCH_LIMIT,
        "metrics": score_rankings(cases, rankings),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
