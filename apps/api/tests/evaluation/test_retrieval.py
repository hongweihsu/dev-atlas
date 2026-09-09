import json
from pathlib import Path

import httpx
import pytest

from devatlas.evaluation.retrieval import (
    CorpusLoadError,
    InvalidEvaluationDatasetError,
    ManifestEntry,
    RankedDocument,
    RetrievalCase,
    RetrievedCandidate,
    _unique_documents,
    document_rankings,
    load_cases,
    score_document_rankings,
    score_evidence_hits,
    upload_corpus,
    validate_cases_against_corpus,
    write_manifest,
)


def make_case() -> RetrievalCase:
    return RetrievalCase(
        case_id="transaction-boundary",
        query="where does commit happen?",
        relevant_documents=("transactions",),
        relevant_passages=("commits after the operation succeeds",),
    )


def test_load_cases_validates_and_normalizes_jsonl(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "case_id": " transaction-boundary ",
                "query": " where does commit happen? ",
                "relevant_documents": ["transactions"],
                "relevant_passages": ["commits after the operation succeeds"],
            }
        ),
        encoding="utf-8",
    )

    assert load_cases(dataset) == [make_case()]


@pytest.mark.parametrize(
    "content",
    [
        "",
        '{"case_id":"same","query":"q","relevant_documents":["A"],'
        '"relevant_passages":["one"]}\n'
        '{"case_id":"same","query":"q2","relevant_documents":["B"],'
        '"relevant_passages":["two"]}\n',
        '{"case_id":"missing","query":"q","relevant_documents":[], '
        '"relevant_passages":[]}',
    ],
)
def test_load_cases_rejects_unevaluable_datasets(tmp_path: Path, content: str) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(content, encoding="utf-8")

    with pytest.raises(InvalidEvaluationDatasetError):
        load_cases(dataset)


def test_upload_corpus_returns_and_writes_runtime_id_manifest(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "transactions.txt").write_text("transaction text", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/documents"
        return httpx.Response(
            201,
            json={
                "document_id": "doc-123",
                "version_id": "version-456",
                "checksum": "abc",
            },
        )

    with httpx.Client(
        base_url="http://test", transport=httpx.MockTransport(handler)
    ) as client:
        manifest = upload_corpus(client, corpus)
    manifest_path = tmp_path / "runs" / "manifest.json"
    write_manifest(manifest_path, manifest)

    assert manifest["transactions"].document_id == "doc-123"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {
        "documents": {
            "transactions": {
                "document_id": "doc-123",
                "document_key": "transactions",
                "version_id": "version-456",
            }
        }
    }


def test_upload_corpus_rejects_empty_directory(tmp_path: Path) -> None:
    with httpx.Client(base_url="http://test") as client:
        with pytest.raises(CorpusLoadError, match="at least one"):
            upload_corpus(client, tmp_path)


def test_cases_must_reference_evidence_inside_their_corpus_document(
    tmp_path: Path,
) -> None:
    (tmp_path / "transactions.txt").write_text(
        "commits after the\noperation succeeds", encoding="utf-8"
    )
    validate_cases_against_corpus([make_case()], tmp_path)

    bad_case = RetrievalCase("bad", "q", ("transactions",), ("not present",))
    with pytest.raises(InvalidEvaluationDatasetError, match="evidence outside"):
        validate_cases_against_corpus([bad_case], tmp_path)


def test_document_rankings_use_manifest_ids_and_deduplicate_chunks() -> None:
    candidates = {
        "q1": [
            RetrievedCandidate("doc-1", "first", 0.95),
            RetrievedCandidate("doc-1", "second", 0.90),
            RetrievedCandidate("doc-2", "third", 0.80),
        ]
    }
    manifest = {"transactions": ManifestEntry("transactions", "doc-1", "v1")}

    assert document_rankings(candidates, manifest) == {
        "q1": [
            RankedDocument("transactions", 0.95),
            RankedDocument("unjudged:doc-2", 0.80),
        ]
    }
    assert _unique_documents(candidates["q1"], {"doc-1": "transactions"}) == [
        RankedDocument("transactions", 0.95),
        RankedDocument("unjudged:doc-2", 0.80),
    ]


def test_standard_document_metrics_and_evidence_hits_are_separate() -> None:
    cases = [
        make_case(),
        RetrievalCase("q2", "proxy", ("vite",), ("proxies to FastAPI",)),
    ]
    rankings = {
        "transaction-boundary": [RankedDocument("transactions", 0.9)],
        "q2": [RankedDocument("other", 0.9), RankedDocument("vite", 0.8)],
    }
    candidates = {
        "transaction-boundary": [
            RetrievedCandidate("doc-1", "only a transaction overview", 0.9),
            RetrievedCandidate(
                "doc-1", "The Unit of Work commits after the operation succeeds.", 0.8
            ),
        ],
        "q2": [RetrievedCandidate("doc-2", "Vite proxies to FastAPI.", 0.8)],
    }

    assert score_document_rankings(cases, rankings) == {
        "DocumentMRR@5": 0.75,
        "DocumentRecall@1": 0.5,
        "DocumentRecall@3": 1.0,
    }
    assert score_evidence_hits(cases, candidates) == {
        "EvidenceHit@1": 0.5,
        "EvidenceHit@3": 1.0,
        "EvidenceHit@5": 1.0,
    }
