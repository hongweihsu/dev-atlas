from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from math import hypot
from typing import Any, cast

from pypdf import PageObject, PdfReader


@dataclass(frozen=True, slots=True)
class PdfPageLayout:
    page_number: int
    has_text: bool
    table_rectangle_count: int
    largest_image_area_ratio: float
    suspicious_reading_order: bool
    reasons: tuple[str, ...]

    @property
    def requires_multimodal(self) -> bool:
        return bool(self.reasons)


def analyze_pdf_pages(content: bytes) -> tuple[PdfPageLayout, ...]:
    """Conservatively identify pages whose visual structure may carry meaning."""
    reader = PdfReader(BytesIO(content))
    return tuple(
        _analyze_page(page, page_number=page_number)
        for page_number, page in enumerate(reader.pages, start=1)
    )


def _analyze_page(page: PageObject, *, page_number: int) -> PdfPageLayout:
    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)
    page_area = max(page_width * page_height, 1.0)
    rectangles: list[float] = []
    image_ratios: list[float] = []
    positions: list[tuple[float, float]] = []
    visible_text: list[str] = []

    def visit_operand(
        operator: bytes,
        operands: list[Any],
        current_matrix: list[float],
        _text_matrix: list[float],
    ) -> None:
        if operator == b"re" and len(operands) >= 4:
            width = abs(float(operands[2]))
            height = abs(float(operands[3]))
            ratio = width * height / page_area
            if width >= 5 and height >= 5 and ratio < 0.5:
                rectangles.append(ratio)
        elif _is_image_operator(page, operator, operands):
            width = hypot(current_matrix[0], current_matrix[1])
            height = hypot(current_matrix[2], current_matrix[3])
            image_ratios.append(min(width * height / page_area, 1.0))

    def visit_text(
        text: str,
        _current_matrix: list[float],
        text_matrix: list[float],
        _font: dict[str, Any] | None,
        _font_size: float,
    ) -> None:
        if text.strip():
            visible_text.append(text)
            positions.append((float(text_matrix[4]), float(text_matrix[5])))

    page.extract_text(
        visitor_operand_before=visit_operand,
        visitor_text=visit_text,
    )
    largest_image = max(image_ratios, default=0.0)
    suspicious_order = _has_suspicious_reading_order(positions, page_height=page_height)
    reasons: list[str] = []
    if not visible_text:
        reasons.append("no_text")
    if len(rectangles) >= 4:
        reasons.append("table_graphics")
    if largest_image >= 0.08:
        reasons.append("large_image")
    if suspicious_order:
        reasons.append("suspicious_reading_order")
    return PdfPageLayout(
        page_number=page_number,
        has_text=bool(visible_text),
        table_rectangle_count=len(rectangles),
        largest_image_area_ratio=largest_image,
        suspicious_reading_order=suspicious_order,
        reasons=tuple(reasons),
    )


def _is_image_operator(page: PageObject, operator: bytes, operands: list[Any]) -> bool:
    if operator == b"INLINE IMAGE":
        return True
    if operator != b"Do" or not operands:
        return False
    try:
        resources = cast(Any, page["/Resources"])
        xobjects = resources["/XObject"]
        reference = xobjects[operands[0]]
        return str(reference.get_object().get("/Subtype")) == "/Image"
    except (KeyError, TypeError, AttributeError):
        return False


def _has_suspicious_reading_order(
    positions: list[tuple[float, float]], *, page_height: float
) -> bool:
    """Detect a content-stream jump back to a visually higher text region."""
    tolerance = max(12.0, page_height * 0.015)
    return any(
        next_y - current_y > tolerance
        for (_current_x, current_y), (_next_x, next_y) in zip(
            positions, positions[1:], strict=False
        )
    )
