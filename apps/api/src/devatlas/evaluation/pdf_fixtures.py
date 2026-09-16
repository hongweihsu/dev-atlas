from __future__ import annotations

import argparse
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-not-found]
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfgen import canvas  # type: ignore[import-untyped]


def generate_pdf_fixtures(output: Path) -> tuple[Path, ...]:
    output.mkdir(parents=True, exist_ok=True)
    native = output / "native-table.pdf"
    scanned = output / "scanned-table.pdf"
    mixed = output / "mixed-pages.pdf"
    column_order = output / "column-order-table.pdf"
    _native_table(native)
    scanned_page = _scanned_table_page()
    _image_pdf(scanned, scanned_page)
    _mixed_pdf(mixed, scanned_page)
    _column_order_table(column_order)
    return native, scanned, mixed, column_order


def _native_table(path: Path) -> None:
    document = canvas.Canvas(str(path), pagesize=A4)
    _paint_white_page(document)
    document.setTitle("Native table fixture")
    document.setFillColor(colors.HexColor("#102a43"))
    document.setFont("Helvetica-Bold", 22)
    document.drawString(24 * mm, 270 * mm, "Native Service Register")
    rows = [
        ("Service", "Code", "State", "Owner"),
        ("Telemetry agent", "OBS-117", "Active", "Reliability"),
        ("Audit relay", "AUD-208", "Standby", "Security"),
    ]
    _draw_table(document, rows, top=245 * mm)
    document.save()


def _scanned_table_page() -> Image.Image:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=32)
    bold = ImageFont.load_default(size=48)
    draw.text((110, 110), "Scanned Vision Register", fill="#102a43", font=bold)
    rows = [
        ("Component", "Release", "State", "Owner"),
        ("Vision gateway", "MM-731", "Pilot", "AI Systems"),
        ("Page mapper", "PAGE-18", "Ready", "Search"),
    ]
    left, top, row_height = 110, 260, 90
    widths = (330, 250, 200, 280)
    for row_index, row in enumerate(rows):
        x = left
        y = top + row_index * row_height
        fill = "#243b53" if row_index == 0 else "#e8eef4"
        text_fill = "white" if row_index == 0 else "#102a43"
        for width, value in zip(widths, row, strict=True):
            draw.rectangle(
                (x, y, x + width, y + row_height), fill=fill, outline="#627d98", width=2
            )
            draw.text((x + 14, y + 24), value, fill=text_fill, font=font)
            x += width
    draw.text(
        (110, 650),
        "Flow: Upload -> Extract -> Chunk -> Cite",
        fill="#102a43",
        font=font,
    )
    return image


def _image_pdf(path: Path, image: Image.Image) -> None:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    document = canvas.Canvas(str(path), pagesize=A4)
    document.drawInlineImage(Image.open(BytesIO(buffer.getvalue())), 0, 0, *A4)
    document.save()


def _mixed_pdf(path: Path, scanned_page: Image.Image) -> None:
    first = BytesIO()
    document = canvas.Canvas(first, pagesize=A4)
    _paint_white_page(document)
    document.setFillColor(colors.HexColor("#102a43"))
    document.setFont("Helvetica-Bold", 20)
    document.drawString(24 * mm, 270 * mm, "Mixed-mode Approval Policy")
    document.setFont("Helvetica", 13)
    document.drawString(
        24 * mm, 250 * mm, "Policy code MIX-201 requires human approval."
    )
    document.save()
    second = BytesIO()
    scanned_page.save(second, format="PDF")
    writer = PdfWriter()
    writer.add_page(PdfReader(BytesIO(first.getvalue())).pages[0])
    writer.add_page(PdfReader(BytesIO(second.getvalue())).pages[0])
    with path.open("wb") as target:
        writer.write(target)


def _column_order_table(path: Path) -> None:
    document = canvas.Canvas(str(path), pagesize=A4)
    _paint_white_page(document)
    document.setTitle("Column-order table boundary fixture")
    document.setFillColor(colors.HexColor("#102a43"))
    document.setFont("Helvetica-Bold", 22)
    document.drawString(24 * mm, 270 * mm, "Search Index Status")
    rows = [
        ("Component", "Code", "State", "Owner"),
        ("Index builder", "IDX-440", "Degraded", "Search"),
        ("Cache warmer", "CCH-229", "Active", "Platform"),
    ]
    left, top, row_height = 24 * mm, 245 * mm, 16 * mm
    widths = (48 * mm, 36 * mm, 35 * mm, 39 * mm)
    x = left
    for column_index, width in enumerate(widths):
        for row_index, row in enumerate(rows):
            y = top - row_index * row_height
            document.setFillColor(
                colors.HexColor("#243b53")
                if row_index == 0
                else colors.HexColor("#e8eef4")
            )
            document.rect(x, y - row_height, width, row_height, fill=1, stroke=1)
            document.setFillColor(
                colors.white if row_index == 0 else colors.HexColor("#102a43")
            )
            document.setFont("Helvetica-Bold" if row_index == 0 else "Helvetica", 10)
            document.drawString(x + 3 * mm, y - 10 * mm, row[column_index])
        x += width
    document.save()


def _draw_table(
    document: canvas.Canvas, rows: Sequence[tuple[str, ...]], *, top: float
) -> None:
    left, row_height = 24 * mm, 16 * mm
    widths = (48 * mm, 36 * mm, 35 * mm, 39 * mm)
    for row_index, row in enumerate(rows):
        x = left
        y = top - row_index * row_height
        for width in widths:
            document.setFillColor(
                colors.HexColor("#243b53")
                if row_index == 0
                else colors.HexColor("#e8eef4")
            )
            document.rect(x, y - row_height, width, row_height, fill=1, stroke=1)
            x += width
        x = left
        for width, value in zip(widths, row, strict=True):
            document.setFillColor(
                colors.white if row_index == 0 else colors.HexColor("#102a43")
            )
            document.setFont("Helvetica-Bold" if row_index == 0 else "Helvetica", 10)
            document.drawString(x + 3 * mm, y - 10 * mm, value)
            x += width


def _paint_white_page(document: canvas.Canvas) -> None:
    document.setFillColor(colors.white)
    document.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 18 PDF fixtures")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in generate_pdf_fixtures(args.output):
        print(path)


if __name__ == "__main__":
    main()
