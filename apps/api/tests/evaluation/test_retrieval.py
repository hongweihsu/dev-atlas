import json
from pathlib import Path

import pytest

from devatlas.evaluation.retrieval import (
    InvalidEvaluationDatasetError,
    RankedDocument,
    RetrievalCase,
    _unique_documents,
    load_cases,
    score_rankings,
)


def test_load_cases_validates_and_normalizes_jsonl(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "case_id": " transaction-boundary ",
                "query": " where does commit happen? ",
                "relevant_documents": ["Transactions"],
            }
        ),
        encoding="utf-8",
    )

    assert load_cases(dataset) == [
        RetrievalCase(
            case_id="transaction-boundary",
            query="where does commit happen?",
            relevant_documents=("Transactions",),
        )
    ]


@pytest.mark.parametrize(
    "content",
    [
        "",
        '{"case_id":"same","query":"q","relevant_documents":["A"]}\n'
        '{"case_id":"same","query":"q2","relevant_documents":["B"]}\n',
        '{"case_id":"missing-relevance","query":"q","relevant_documents":[]}',
    ],
)
def test_load_cases_rejects_unevaluable_datasets(tmp_path: Path, content: str) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(content, encoding="utf-8")

    with pytest.raises(InvalidEvaluationDatasetError):
        load_cases(dataset)


def test_unique_documents_keeps_highest_ranked_chunk_per_document() -> None:
    rows = [
        {"document_title": "Transactions", "similarity": 0.95},
        {"document_title": "Transactions", "similarity": 0.90},
        {"document_title": "Vite proxy", "similarity": 0.80},
    ]

    assert _unique_documents(rows) == [
        RankedDocument("Transactions", 0.95),
        RankedDocument("Vite proxy", 0.80),
    ]


def test_score_rankings_uses_standard_ir_metrics() -> None:
    cases = [
        RetrievalCase("q1", "transaction", ("Transactions",)),
        RetrievalCase("q2", "proxy", ("Vite proxy",)),
    ]
    rankings = {
        "q1": [RankedDocument("Transactions", 0.9)],
        "q2": [
            RankedDocument("Other", 0.9),
            RankedDocument("Vite proxy", 0.8),
        ],
    }

    assert score_rankings(cases, rankings) == {
        "MRR@5": 0.75,
        "Recall@1": 0.5,
        "Recall@3": 1.0,
    }
