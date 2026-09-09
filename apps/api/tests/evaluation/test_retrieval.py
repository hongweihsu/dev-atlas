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
    build_case_results,
    document_rankings,
    load_cases,
    load_manifest,
    score_by_category,
    score_document_rankings,
    score_evidence_hits,
    sync_manifest,
    upload_corpus,
    validate_cases_against_corpus,
    validate_manifest,
    write_manifest,
)


def make_case() -> RetrievalCase:
    return RetrievalCase(
        case_id="transaction-boundary",
        category="semantic",
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
                "category": " semantic ",
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
        '{"case_id":"same","category":"semantic","query":"q",'
        '"relevant_documents":["A"],'
        '"relevant_passages":["one"]}\n'
        '{"case_id":"same","category":"semantic","query":"q2",'
        '"relevant_documents":["B"],'
        '"relevant_passages":["two"]}\n',
        '{"case_id":"missing","category":"semantic","query":"q",'
        '"relevant_documents":[], '
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
    assert load_manifest(manifest_path) == manifest


def test_validate_manifest_requires_matching_active_database_document() -> None:
    entry = ManifestEntry("transactions", "doc-123", "version-456")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/documents"
        return httpx.Response(
            200,
            json=[
                {
                    "document_id": "doc-123",
                    "title": "transactions",
                    "active_version_id": "version-456",
                }
            ],
        )

    with httpx.Client(
        base_url="http://test", transport=httpx.MockTransport(handler)
    ) as client:
        validate_manifest(client, {"transactions": entry})


def test_validate_manifest_rejects_stale_version() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "document_id": "doc-123",
                    "title": "transactions",
                    "active_version_id": "new-version",
                }
            ],
        )

    with httpx.Client(
        base_url="http://test", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(CorpusLoadError, match="does not match"):
            validate_manifest(
                client,
                {"transactions": ManifestEntry("transactions", "doc-123", "old")},
            )


def test_sync_manifest_uploads_only_missing_corpus_files(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "existing.txt").write_text("existing", encoding="utf-8")
    (corpus / "new.txt").write_text("new", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    write_manifest(
        manifest_path,
        {"existing": ManifestEntry("existing", "doc-existing", "v-existing")},
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "document_id": "doc-existing",
                        "title": "existing",
                        "active_version_id": "v-existing",
                    }
                ],
            )
        return httpx.Response(
            201,
            json={"document_id": "doc-new", "version_id": "v-new"},
        )

    with httpx.Client(
        base_url="http://test", transport=httpx.MockTransport(handler)
    ) as client:
        manifest = sync_manifest(client, corpus, manifest_path)

    assert calls == ["GET /documents", "POST /documents"]
    assert manifest == {
        "existing": ManifestEntry("existing", "doc-existing", "v-existing"),
        "new": ManifestEntry("new", "doc-new", "v-new"),
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

    bad_case = RetrievalCase(
        "bad", "semantic", "q", ("transactions",), ("not present",)
    )
    with pytest.raises(InvalidEvaluationDatasetError, match="retrievable chunk"):
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
        RetrievalCase("q2", "identifier", "proxy", ("vite",), ("proxies to FastAPI",)),
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
    assert score_by_category(cases, candidates, rankings) == {
        "identifier": {
            "DocumentMRR@5": 0.5,
            "DocumentRecall@1": 0.0,
            "DocumentRecall@3": 1.0,
            "EvidenceHit@1": 1.0,
            "EvidenceHit@3": 1.0,
            "EvidenceHit@5": 1.0,
        },
        "semantic": {
            "DocumentMRR@5": 1.0,
            "DocumentRecall@1": 1.0,
            "DocumentRecall@3": 1.0,
            "EvidenceHit@1": 0.0,
            "EvidenceHit@3": 1.0,
            "EvidenceHit@5": 1.0,
        },
    }

    assert build_case_results(cases, candidates, rankings) == [
        {
            "case_id": "transaction-boundary",
            "category": "semantic",
            "document_rank": 1,
            "evidence_rank": 2,
            "retrieved_documents": [
                {"rank": 1, "document_key": "transactions", "score": 0.9}
            ],
            "retrieved_chunks": [
                {
                    "rank": 1,
                    "document_id": "doc-1",
                    "score": 0.9,
                    "contains_evidence": False,
                },
                {
                    "rank": 2,
                    "document_id": "doc-1",
                    "score": 0.8,
                    "contains_evidence": True,
                },
            ],
        },
        {
            "case_id": "q2",
            "category": "identifier",
            "document_rank": 2,
            "evidence_rank": 1,
            "retrieved_documents": [
                {"rank": 1, "document_key": "other", "score": 0.9},
                {"rank": 2, "document_key": "vite", "score": 0.8},
            ],
            "retrieved_chunks": [
                {
                    "rank": 1,
                    "document_id": "doc-2",
                    "score": 0.8,
                    "contains_evidence": True,
                }
            ],
        },
    ]
