from retrieval_works.infrastructure.extraction.pdf_layout import (
    PdfPageLayout,
    _has_suspicious_reading_order,
)


def test_reading_order_detects_jump_back_to_higher_visual_row() -> None:
    column_major_positions = [
        (70.0, 700.0),
        (70.0, 650.0),
        (70.0, 600.0),
        (210.0, 700.0),
    ]

    assert _has_suspicious_reading_order(column_major_positions, page_height=842.0)


def test_reading_order_accepts_top_to_bottom_rows() -> None:
    row_major_positions = [
        (70.0, 700.0),
        (210.0, 700.0),
        (70.0, 650.0),
        (210.0, 650.0),
    ]

    assert not _has_suspicious_reading_order(row_major_positions, page_height=842.0)


def test_page_requires_multimodal_when_any_reason_is_present() -> None:
    plain = PdfPageLayout(1, True, 0, 0.0, False, ())
    table = PdfPageLayout(1, True, 8, 0.0, False, ("table_graphics",))

    assert plain.requires_multimodal is False
    assert table.requires_multimodal is True
