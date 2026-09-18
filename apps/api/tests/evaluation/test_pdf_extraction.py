import json
from pathlib import Path

import pytest

from retrieval_works.domain.document_ingestion import PageSpan, PreparedTextDocument
from retrieval_works.evaluation.pdf_extraction import (
    InvalidPdfEvaluationDatasetError,
    PdfExtractionCase,
    load_pdf_cases,
    score_pdf_case,
    summarize_pdf_results,
)


def make_case() -> PdfExtractionCase:
    return PdfExtractionCase(
        case_id="scanned-table",
        filename="scanned-table.pdf",
        category="scanned_table",
        expected_path="multimodal",
        expected_pages=(1,),
        evidence=("MM-731", "AI Systems"),
        structure_evidence=("Vision gateway MM-731 Pilot AI Systems",),
    )


def test_load_pdf_cases_validates_reviewed_contract(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "case_id": "scanned-table",
                    "filename": "scanned-table.pdf",
                    "category": "scanned_table",
                    "expected_path": "multimodal",
                    "expected_pages": [1],
                    "evidence": ["MM-731", "AI Systems"],
                    "structure_evidence": ["Vision gateway MM-731 Pilot AI Systems"],
                }
            ]
        ),
        encoding="utf-8",
    )

    assert load_pdf_cases(dataset) == [make_case()]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [{"case_id": "missing-fields"}],
        [
            {
                "case_id": "bad-pages",
                "filename": "x.pdf",
                "category": "x",
                "expected_path": "native",
                "expected_pages": [2],
                "evidence": ["x"],
                "structure_evidence": [],
            }
        ],
    ],
)
def test_load_pdf_cases_rejects_invalid_dataset(
    tmp_path: Path, payload: object
) -> None:
    dataset = tmp_path / "cases.json"
    dataset.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(InvalidPdfEvaluationDatasetError):
        load_pdf_cases(dataset)


def test_score_and_summary_keep_failure_visible() -> None:
    prepared = PreparedTextDocument(
        source_filename="scanned-table.pdf",
        media_type="application/pdf",
        normalized_text="Vision gateway MM-731 Pilot",
        content_checksum="checksum",
        byte_size=10,
        character_count=27,
        page_spans=(PageSpan(1, 0, 27),),
    )

    result = score_pdf_case(make_case(), prepared, "multimodal")
    metrics = summarize_pdf_results([result])

    assert result.evidence_hits == 1
    assert result.structure_hits == 0
    assert metrics == {
        "PathAccuracy": 1.0,
        "PageCoverage": 1.0,
        "EvidenceRetention": 0.5,
        "StructureRetention": 0.0,
    }


def test_structure_score_accepts_markdown_table_separators() -> None:
    text = "| Vision gateway | MM-731 | Pilot | AI Systems |"
    prepared = PreparedTextDocument(
        source_filename="scanned-table.pdf",
        media_type="application/pdf",
        normalized_text=text,
        content_checksum="checksum",
        byte_size=10,
        character_count=len(text),
        page_spans=(PageSpan(1, 0, len(text)),),
    )

    result = score_pdf_case(make_case(), prepared, "multimodal")

    assert result.structure_hits == 1
