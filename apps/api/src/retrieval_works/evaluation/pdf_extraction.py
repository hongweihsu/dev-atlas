from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from openai import AsyncOpenAI

from retrieval_works.core.config import Settings
from retrieval_works.domain.document_ingestion import (
    DocumentValidationCode,
    DocumentValidationError,
    PreparedTextDocument,
    prepare_document,
)
from retrieval_works.infrastructure.extraction import OpenAIMultimodalDocumentExtractor
from retrieval_works.infrastructure.extraction.pdf_layout import analyze_pdf_pages

ExtractionPath = Literal["native", "multimodal"]


class InvalidPdfEvaluationDatasetError(ValueError):
    """Raised when a PDF extraction case cannot be evaluated safely."""


@dataclass(frozen=True, slots=True)
class PdfExtractionCase:
    case_id: str
    filename: str
    category: str
    expected_path: ExtractionPath
    expected_pages: tuple[int, ...]
    evidence: tuple[str, ...]
    structure_evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PdfCaseResult:
    case_id: str
    category: str
    expected_path: ExtractionPath
    actual_path: ExtractionPath
    extracted_pages: tuple[int, ...]
    expected_pages: tuple[int, ...]
    evidence_hits: int
    evidence_total: int
    structure_hits: int
    structure_total: int
    character_count: int


def load_pdf_cases(path: Path) -> list[PdfExtractionCase]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InvalidPdfEvaluationDatasetError("dataset is not valid JSON") from error
    if not isinstance(payload, list) or not payload:
        raise InvalidPdfEvaluationDatasetError("dataset must be a non-empty list")

    cases: list[PdfExtractionCase] = []
    seen: set[str] = set()
    for index, value in enumerate(payload, start=1):
        if not isinstance(value, dict):
            raise InvalidPdfEvaluationDatasetError(f"case {index} must be an object")
        case_id = _string(value, "case_id", index)
        if case_id in seen:
            raise InvalidPdfEvaluationDatasetError(f"duplicate case_id {case_id!r}")
        seen.add(case_id)
        expected_path = _string(value, "expected_path", index)
        if expected_path not in {"native", "multimodal"}:
            raise InvalidPdfEvaluationDatasetError(
                f"case {index} has invalid expected_path"
            )
        pages = _positive_ints(value, "expected_pages", index)
        cases.append(
            PdfExtractionCase(
                case_id=case_id,
                filename=_string(value, "filename", index),
                category=_string(value, "category", index),
                expected_path=cast(ExtractionPath, expected_path),
                expected_pages=pages,
                evidence=_strings(value, "evidence", index),
                structure_evidence=_strings(
                    value, "structure_evidence", index, allow_empty=True
                ),
            )
        )
    return cases


def detect_extraction_path(content: bytes, filename: str) -> ExtractionPath:
    try:
        prepare_document(
            content=content,
            source_filename=filename,
            media_type="application/pdf",
        )
    except DocumentValidationError as error:
        if error.code is DocumentValidationCode.NO_EXTRACTABLE_TEXT:
            return "multimodal"
        raise
    return (
        "multimodal"
        if any(page.requires_multimodal for page in analyze_pdf_pages(content))
        else "native"
    )


def score_pdf_case(
    case: PdfExtractionCase,
    prepared: PreparedTextDocument,
    actual_path: ExtractionPath,
) -> PdfCaseResult:
    text = _normalized_text(prepared.normalized_text)
    structure_text = _normalized_structure_text(prepared.normalized_text)
    return PdfCaseResult(
        case_id=case.case_id,
        category=case.category,
        expected_path=case.expected_path,
        actual_path=actual_path,
        extracted_pages=tuple(span.page_number for span in prepared.page_spans),
        expected_pages=case.expected_pages,
        evidence_hits=sum(
            " ".join(item.split()).casefold() in text for item in case.evidence
        ),
        evidence_total=len(case.evidence),
        structure_hits=sum(
            _normalized_structure_text(item) in structure_text
            for item in case.structure_evidence
        ),
        structure_total=len(case.structure_evidence),
        character_count=prepared.character_count,
    )


def summarize_pdf_results(results: list[PdfCaseResult]) -> dict[str, float]:
    evidence_total = sum(result.evidence_total for result in results)
    structure_total = sum(result.structure_total for result in results)
    return {
        "PathAccuracy": sum(
            result.actual_path == result.expected_path for result in results
        )
        / len(results),
        "PageCoverage": sum(
            result.extracted_pages == result.expected_pages for result in results
        )
        / len(results),
        "EvidenceRetention": (
            sum(result.evidence_hits for result in results) / evidence_total
        ),
        "StructureRetention": (
            sum(result.structure_hits for result in results) / structure_total
            if structure_total
            else 1.0
        ),
    }


def _normalized_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _normalized_structure_text(value: str) -> str:
    return _normalized_text(value.replace("|", " "))


async def run_pdf_evaluation(
    cases: list[PdfExtractionCase], corpus: Path, settings: Settings
) -> list[PdfCaseResult]:
    if settings.openai_api_key is None:
        raise RuntimeError("OPENAI_API_KEY is required for PDF evaluation")
    client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    extractor = OpenAIMultimodalDocumentExtractor(client, model=settings.answer_model)
    try:
        results: list[PdfCaseResult] = []
        for case in cases:
            path = corpus / case.filename
            if not path.is_file():
                raise InvalidPdfEvaluationDatasetError(
                    f"missing PDF fixture {case.filename!r}"
                )
            content = path.read_bytes()
            actual_path = detect_extraction_path(content, case.filename)
            prepared = await extractor.prepare(
                content=content,
                source_filename=case.filename,
                media_type="application/pdf",
            )
            results.append(score_pdf_case(case, prepared, actual_path))
        return results
    finally:
        await client.close()


def _string(value: dict[str, Any], field: str, index: int) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise InvalidPdfEvaluationDatasetError(
            f"case {index} needs a non-empty {field}"
        )
    return item.strip()


def _strings(
    value: dict[str, Any], field: str, index: int, *, allow_empty: bool = False
) -> tuple[str, ...]:
    items = value.get(field)
    if not isinstance(items, list) or (not items and not allow_empty):
        raise InvalidPdfEvaluationDatasetError(f"case {index} needs {field}")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise InvalidPdfEvaluationDatasetError(
            f"case {index} has an invalid {field} item"
        )
    return tuple(item.strip() for item in items)


def _positive_ints(value: dict[str, Any], field: str, index: int) -> tuple[int, ...]:
    items = value.get(field)
    if (
        not isinstance(items, list)
        or not items
        or any(not isinstance(item, int) or item <= 0 for item in items)
    ):
        raise InvalidPdfEvaluationDatasetError(f"case {index} needs positive {field}")
    result = tuple(items)
    if result != tuple(range(1, len(result) + 1)):
        raise InvalidPdfEvaluationDatasetError(
            f"case {index} {field} must be consecutive from 1"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PDF text extraction")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    cases = load_pdf_cases(args.dataset)
    results = asyncio.run(run_pdf_evaluation(cases, args.corpus, Settings()))
    report = {
        "case_count": len(cases),
        "metrics": summarize_pdf_results(results),
        "cases": [asdict(result) for result in results],
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
