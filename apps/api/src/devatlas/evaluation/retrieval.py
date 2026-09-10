from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
import ir_measures
from ir_measures import RR, Recall

from devatlas.domain.text_processing import chunk_text, normalize_text

ANSWER_CONTEXT_LIMIT = 5
COLLECTION_LIMIT = 20


class InvalidEvaluationDatasetError(ValueError):
    """Raised when a retrieval case cannot be evaluated safely."""


class CorpusLoadError(RuntimeError):
    """Raised when a controlled corpus cannot be mapped to the live database."""


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    case_id: str
    category: str
    query: str
    relevant_documents: tuple[str, ...]
    relevant_passages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    document_key: str
    document_id: str
    version_id: str


@dataclass(frozen=True, slots=True)
class RetrievedCandidate:
    document_id: str
    text: str
    score: float


@dataclass(frozen=True, slots=True)
class RankedDocument:
    document_key: str
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


def validate_cases_against_corpus(
    cases: Sequence[RetrievalCase], corpus_directory: Path
) -> None:
    corpus = {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(corpus_directory.glob("*.txt"))
    }
    if not corpus:
        raise CorpusLoadError("corpus directory must contain at least one .txt file")
    for case in cases:
        unknown = set(case.relevant_documents) - corpus.keys()
        if unknown:
            raise InvalidEvaluationDatasetError(
                f"case {case.case_id!r} references unknown documents: "
                f"{', '.join(sorted(unknown))}"
            )
        relevant_chunks = [
            _normalized_evidence_text(chunk.text)
            for key in case.relevant_documents
            for chunk in chunk_text(normalize_text(corpus[key]))
        ]
        missing = [
            passage
            for passage in case.relevant_passages
            if not any(
                _normalized_evidence_text(passage) in chunk for chunk in relevant_chunks
            )
        ]
        if missing:
            raise InvalidEvaluationDatasetError(
                f"case {case.case_id!r} has evidence outside one retrievable chunk"
            )


def upload_corpus(
    client: httpx.Client, corpus_directory: Path
) -> dict[str, ManifestEntry]:
    paths = sorted(corpus_directory.glob("*.txt"))
    if not paths:
        raise CorpusLoadError("corpus directory must contain at least one .txt file")
    return _upload_paths(client, paths)


def _upload_paths(
    client: httpx.Client, paths: Sequence[Path]
) -> dict[str, ManifestEntry]:
    manifest: dict[str, ManifestEntry] = {}
    for path in paths:
        document_key = path.stem
        with path.open("rb") as source:
            response = client.post(
                "/documents",
                data={"title": document_key},
                files={"file": (path.name, source, "text/plain")},
            )
        if response.status_code == 201:
            payload = response.json()
        elif response.status_code == 409:
            payload = _resolve_existing_document(client, response, document_key)
        else:
            response.raise_for_status()
            raise AssertionError("unreachable")
        manifest[document_key] = ManifestEntry(
            document_key=document_key,
            document_id=str(payload["document_id"]),
            version_id=str(payload["version_id"]),
        )
    return manifest


def write_manifest(path: Path, manifest: Mapping[str, ManifestEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "documents": {key: asdict(entry) for key, entry in sorted(manifest.items())}
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_manifest(path: Path) -> dict[str, ManifestEntry]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
        documents = payload["documents"]
        return {
            str(key): ManifestEntry(
                document_key=str(value["document_key"]),
                document_id=str(value["document_id"]),
                version_id=str(value["version_id"]),
            )
            for key, value in documents.items()
        }
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as error:
        raise CorpusLoadError("manifest has an invalid structure") from error


def validate_manifest(
    client: httpx.Client, manifest: Mapping[str, ManifestEntry]
) -> None:
    response = client.get("/documents")
    response.raise_for_status()
    documents_by_id = {
        str(document["document_id"]): document for document in response.json()
    }
    for key, entry in manifest.items():
        document = documents_by_id.get(entry.document_id)
        if (
            document is None
            or document["title"] != key
            or document["active_version_id"] != entry.version_id
        ):
            raise CorpusLoadError(
                f"manifest entry {key!r} does not match an active database document"
            )


def sync_manifest(
    client: httpx.Client,
    corpus_directory: Path,
    manifest_path: Path,
) -> dict[str, ManifestEntry]:
    paths_by_key = {path.stem: path for path in sorted(corpus_directory.glob("*.txt"))}
    if not paths_by_key:
        raise CorpusLoadError("corpus directory must contain at least one .txt file")
    manifest = load_manifest(manifest_path) if manifest_path.exists() else {}
    if manifest:
        validate_manifest(client, manifest)
    extra_keys = manifest.keys() - paths_by_key.keys()
    if extra_keys:
        raise CorpusLoadError(
            "manifest contains files absent from corpus: "
            f"{', '.join(sorted(extra_keys))}"
        )
    missing_paths = [path for key, path in paths_by_key.items() if key not in manifest]
    manifest.update(_upload_paths(client, missing_paths))
    write_manifest(manifest_path, manifest)
    return manifest


def fetch_candidates(
    client: httpx.Client,
    cases: Iterable[RetrievalCase],
    *,
    strategy: str = "hybrid",
) -> dict[str, list[RetrievedCandidate]]:
    candidates: dict[str, list[RetrievedCandidate]] = {}
    for case in cases:
        response = client.post(
            "/search",
            json={
                "query": case.query,
                "limit": COLLECTION_LIMIT,
                "strategy": strategy,
            },
        )
        response.raise_for_status()
        candidates[case.case_id] = [
            RetrievedCandidate(
                document_id=str(row["document_id"]),
                text=str(row["text"]),
                score=float(row["similarity"]),
            )
            for row in response.json()["results"]
        ]
    return candidates


def document_rankings(
    candidates: Mapping[str, Sequence[RetrievedCandidate]],
    manifest: Mapping[str, ManifestEntry],
) -> dict[str, list[RankedDocument]]:
    keys_by_id = {entry.document_id: key for key, entry in manifest.items()}
    return {
        case_id: _unique_documents(results, keys_by_id)
        for case_id, results in candidates.items()
    }


def score_document_rankings(
    cases: Sequence[RetrievalCase],
    rankings: Mapping[str, Sequence[RankedDocument]],
) -> dict[str, float]:
    qrels = [
        ir_measures.Qrel(case.case_id, document_key, 1)
        for case in cases
        for document_key in case.relevant_documents
    ]
    run = [
        ir_measures.ScoredDoc(case.case_id, result.document_key, result.score)
        for case in cases
        for result in rankings.get(case.case_id, ())[:ANSWER_CONTEXT_LIMIT]
    ]
    recall_at_1 = Recall @ 1
    recall_at_3 = Recall @ 3
    reciprocal_rank_at_5 = RR @ ANSWER_CONTEXT_LIMIT
    measured = ir_measures.calc_aggregate(
        [recall_at_1, recall_at_3, reciprocal_rank_at_5], qrels, run
    )
    return {
        "DocumentRecall@1": measured[recall_at_1],
        "DocumentRecall@3": measured[recall_at_3],
        "DocumentMRR@5": measured[reciprocal_rank_at_5],
    }


def score_evidence_hits(
    cases: Sequence[RetrievalCase],
    candidates: Mapping[str, Sequence[RetrievedCandidate]],
) -> dict[str, float]:
    return {
        f"EvidenceHit@{cutoff}": sum(
            _has_evidence(case, candidates.get(case.case_id, ()), cutoff=cutoff)
            for case in cases
        )
        / len(cases)
        for cutoff in (1, 3, ANSWER_CONTEXT_LIMIT)
    }


def score_by_category(
    cases: Sequence[RetrievalCase],
    candidates: Mapping[str, Sequence[RetrievedCandidate]],
    rankings: Mapping[str, Sequence[RankedDocument]],
) -> dict[str, dict[str, float]]:
    return {
        category: {
            **score_document_rankings(category_cases, rankings),
            **score_evidence_hits(category_cases, candidates),
        }
        for category in sorted({case.category for case in cases})
        if (category_cases := [case for case in cases if case.category == category])
    }


def build_case_results(
    cases: Sequence[RetrievalCase],
    candidates: Mapping[str, Sequence[RetrievedCandidate]],
    rankings: Mapping[str, Sequence[RankedDocument]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in cases:
        case_candidates = candidates.get(case.case_id, ())
        case_rankings = rankings.get(case.case_id, ())
        results.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "document_rank": _first_relevant_document_rank(case, case_rankings),
                "evidence_rank": _first_evidence_rank(case, case_candidates),
                "retrieved_documents": [
                    {
                        "rank": rank,
                        "document_key": result.document_key,
                        "score": result.score,
                    }
                    for rank, result in enumerate(
                        case_rankings[:ANSWER_CONTEXT_LIMIT], start=1
                    )
                ],
                "retrieved_chunks": [
                    {
                        "rank": rank,
                        "document_id": result.document_id,
                        "score": result.score,
                        "contains_evidence": _candidate_contains_evidence(case, result),
                    }
                    for rank, result in enumerate(
                        case_candidates[:ANSWER_CONTEXT_LIMIT], start=1
                    )
                ],
            }
        )
    return results


def _has_evidence(
    case: RetrievalCase,
    candidates: Sequence[RetrievedCandidate],
    *,
    cutoff: int,
) -> bool:
    return any(
        _candidate_contains_evidence(case, candidate)
        for candidate in candidates[:cutoff]
    )


def _candidate_contains_evidence(
    case: RetrievalCase, candidate: RetrievedCandidate
) -> bool:
    candidate_text = _normalized_evidence_text(candidate.text)
    return any(
        _normalized_evidence_text(passage) in candidate_text
        for passage in case.relevant_passages
    )


def _first_relevant_document_rank(
    case: RetrievalCase, rankings: Sequence[RankedDocument]
) -> int | None:
    relevant = set(case.relevant_documents)
    return next(
        (
            rank
            for rank, result in enumerate(rankings, start=1)
            if result.document_key in relevant
        ),
        None,
    )


def _first_evidence_rank(
    case: RetrievalCase, candidates: Sequence[RetrievedCandidate]
) -> int | None:
    return next(
        (
            rank
            for rank, candidate in enumerate(candidates, start=1)
            if _candidate_contains_evidence(case, candidate)
        ),
        None,
    )


def _normalized_evidence_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _unique_documents(
    candidates: Iterable[RetrievedCandidate],
    keys_by_id: Mapping[str, str],
) -> list[RankedDocument]:
    results: list[RankedDocument] = []
    seen_ids: set[str] = set()
    for candidate in candidates:
        if candidate.document_id in seen_ids:
            continue
        seen_ids.add(candidate.document_id)
        document_key = keys_by_id.get(
            candidate.document_id, f"unjudged:{candidate.document_id}"
        )
        results.append(RankedDocument(document_key, candidate.score))
    return results


def _resolve_existing_document(
    client: httpx.Client,
    conflict_response: httpx.Response,
    document_key: str,
) -> dict[str, Any]:
    detail = conflict_response.json().get("detail", {})
    document_id = detail.get("document_id")
    if not document_id:
        raise CorpusLoadError(
            f"duplicate corpus file {document_key!r} did not identify its document"
        )
    response = client.get("/documents")
    response.raise_for_status()
    for document in response.json():
        if document["document_id"] != document_id:
            continue
        if document["title"] != document_key:
            raise CorpusLoadError(
                f"corpus content for {document_key!r} already belongs to title "
                f"{document['title']!r}; use an isolated evaluation database"
            )
        return {
            "document_id": document_id,
            "version_id": document["active_version_id"],
        }
    raise CorpusLoadError(f"existing document {document_id!r} was not listed")


def _parse_case(value: Any, *, line_number: int) -> RetrievalCase:
    if not isinstance(value, dict):
        raise InvalidEvaluationDatasetError(f"line {line_number} must be an object")
    case_id = _non_empty_string(value.get("case_id"), line_number, "case_id")
    category = _non_empty_string(value.get("category"), line_number, "category")
    query = _non_empty_string(value.get("query"), line_number, "query")
    documents = _non_empty_string_list(
        value.get("relevant_documents"), line_number, "relevant_documents"
    )
    passages = _non_empty_string_list(
        value.get("relevant_passages"), line_number, "relevant_passages"
    )
    return RetrievalCase(case_id, category, query, documents, passages)


def _non_empty_string(value: Any, line_number: int, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidEvaluationDatasetError(
            f"line {line_number} needs a non-empty {field}"
        )
    return value.strip()


def _non_empty_string_list(value: Any, line_number: int, field: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise InvalidEvaluationDatasetError(
            f"line {line_number} needs non-empty {field}"
        )
    normalized = tuple(item.strip() for item in value)
    if len(set(normalized)) != len(normalized):
        raise InvalidEvaluationDatasetError(f"line {line_number} repeats {field}")
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure live document retrieval")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    manifest_mode = parser.add_mutually_exclusive_group()
    manifest_mode.add_argument("--reuse-manifest", action="store_true")
    manifest_mode.add_argument("--sync-manifest", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--strategy",
        choices=("vector", "lexical", "hybrid"),
        default="hybrid",
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    cases = load_cases(args.dataset)
    validate_cases_against_corpus(cases, args.corpus)
    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        if args.reuse_manifest:
            manifest = load_manifest(args.manifest)
            validate_manifest(client, manifest)
        elif args.sync_manifest:
            manifest = sync_manifest(client, args.corpus, args.manifest)
        else:
            manifest = upload_corpus(client, args.corpus)
            write_manifest(args.manifest, manifest)
        candidates = fetch_candidates(client, cases, strategy=args.strategy)
    rankings = document_rankings(candidates, manifest)
    report = {
        "case_count": len(cases),
        "chunk_collection_limit": COLLECTION_LIMIT,
        "answer_context_limit": ANSWER_CONTEXT_LIMIT,
        "strategy": args.strategy,
        "metrics": {
            **score_document_rankings(cases, rankings),
            **score_evidence_hits(cases, candidates),
        },
        "metrics_by_category": score_by_category(cases, candidates, rankings),
        "cases": build_case_results(cases, candidates, rankings),
    }
    rendered_report = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered_report, encoding="utf-8")
    print(rendered_report, end="")


if __name__ == "__main__":
    main()
