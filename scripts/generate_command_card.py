#!/usr/bin/env python3
"""Generate the print-ready Studio Inventory scanner command card."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import code128
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas


APP_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = APP_DIR / "frontend" / "src" / "commandCardData.json"
DEFAULT_OUTPUT_PATH = APP_DIR / "output" / "pdf" / "studio-inventory-command-card.pdf"

NAVY = HexColor("#102A43")
TEAL = HexColor("#0B7A75")
ORANGE = HexColor("#C96622")
RED = HexColor("#A6403A")
GOLD = HexColor("#A66A00")
INK = HexColor("#1F2933")
MUTED = HexColor("#52606D")
LINE = HexColor("#CBD5E1")
PALE_BLUE = HexColor("#EAF4F8")
PALE_TEAL = HexColor("#E8F5F3")
PALE_ORANGE = HexColor("#FFF4E8")
PALE_RED = HexColor("#FCEDEB")
PALE_GOLD = HexColor("#FFF7DC")
PALE_GRAY = HexColor("#F5F7FA")


def draw_qr(canvas: Canvas, value: str, x: float, y: float, size: float) -> None:
    qr = QrCodeWidget(value, barLevel="M")
    x1, y1, x2, y2 = qr.getBounds()
    width = x2 - x1
    height = y2 - y1
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, -x1, -y1])
    drawing.add(qr)
    renderPDF.draw(drawing, canvas, x, y)


def draw_code128(
    canvas: Canvas,
    value: str,
    x: float,
    y: float,
    max_width: float,
    height: float = 23,
) -> None:
    barcode = code128.Code128(value, barHeight=height, barWidth=0.68, quiet=True)
    if barcode.width > max_width:
        barcode.barWidth *= max_width / barcode.width
        barcode._calculate()
    barcode.drawOn(canvas, x + (max_width - barcode.width) / 2, y)


def fit_text(canvas: Canvas, text: str, font: str, size: float, max_width: float) -> float:
    while size > 5 and stringWidth(text, font, size) > max_width:
        size -= 0.25
    canvas.setFont(font, size)
    return size


def section_heading(
    canvas: Canvas,
    step: str,
    title: str,
    detail: str,
    x: float,
    top: float,
) -> None:
    canvas.setFillColor(TEAL)
    canvas.circle(x + 10, top - 10, 10, stroke=0, fill=1)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawCentredString(x + 10, top - 13, step)
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 10.5)
    canvas.drawString(x + 28, top - 8, title)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.8)
    canvas.drawString(x + 28, top - 18, detail)


def rounded_box(
    canvas: Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    fill,
    stroke=LINE,
    radius: float = 7,
) -> None:
    canvas.setFillColor(fill)
    canvas.setStrokeColor(stroke)
    canvas.setLineWidth(0.7)
    canvas.roundRect(x, y, width, height, radius, stroke=1, fill=1)


def site_origin(value: str) -> str:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/")
    ):
        raise argparse.ArgumentTypeError("origin must be a site origin such as https://erp.example.com")
    return f"{parsed.scheme}://{parsed.netloc}"


def build_pdf(data: dict, output_path: Path, origin: str, brand: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = letter
    margin = 24
    content_width = page_width - 2 * margin
    app_url = f"{origin}{data['appPath']}"

    canvas = Canvas(str(output_path), pagesize=letter, pageCompression=1)
    canvas.setTitle(f"{brand} - Studio Inventory Scanner Command Card")
    canvas.setAuthor(brand)
    canvas.setSubject("Barcode and QR command card for ERPNext Studio Inventory")

    canvas.setFillColor(NAVY)
    fit_text(canvas, brand.upper(), "Helvetica-Bold", 8, 330)
    canvas.drawString(margin, 770, brand.upper())
    canvas.setFont("Helvetica-Bold", 17)
    canvas.drawString(margin, 750, "Studio Inventory scanner card")
    canvas.setFillColor(TEAL)
    canvas.roundRect(489, 746, 99, 25, 12, stroke=0, fill=1)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawCentredString(538.5, 755, "SCAN - ENTER")

    start_bottom = 624
    rounded_box(canvas, margin, start_bottom, content_width, 112, PALE_BLUE, HexColor("#B7D8E5"), 9)
    draw_qr(canvas, app_url, 35, start_bottom + 13, 86)
    canvas.setFillColor(TEAL)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawString(139, start_bottom + 87, "START HERE")
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(139, start_bottom + 67, "Open Studio Inventory")
    canvas.setFillColor(INK)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(139, start_bottom + 49, "Phone: scan with the camera. Tera: focus the browser address bar, then scan.")
    canvas.drawString(139, start_bottom + 36, "The scanner's Enter suffix opens the page. Sign in if ERPNext asks.")
    canvas.setFillColor(white)
    canvas.roundRect(136, start_bottom + 10, 431, 18, 4, stroke=0, fill=1)
    canvas.setFillColor(MUTED)
    fit_text(canvas, app_url, "Courier", 6.8, 417)
    canvas.drawString(143, start_bottom + 16, app_url)

    section_heading(
        canvas,
        "1",
        "Choose a mode, then scan the paper label",
        "The next scan selects the item, roll, pack, or batch you are changing.",
        margin,
        613,
    )
    mode_y = 507
    mode_gap = 6
    mode_width = (content_width - 2 * mode_gap) / 3
    for index, mode in enumerate(data["modes"]):
        x = margin + index * (mode_width + mode_gap)
        rounded_box(canvas, x, mode_y, mode_width, 80, white)
        mode_url = f"{app_url}?mode={mode['mode']}"
        draw_qr(canvas, mode_url, x + 8, mode_y + 8, 64)
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 10.5)
        canvas.drawString(x + 80, mode_y + 48, mode["label"])
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 6.8)
        canvas.drawString(x + 80, mode_y + 34, mode["detail"])
        canvas.setFont("Helvetica", 6.1)
        canvas.drawString(x + 80, mode_y + 21, "QR deep link")

    section_heading(
        canvas,
        "2",
        "For Consume, choose how to enter the change",
        "Skip this row for Receive or Count.",
        margin,
        496,
    )
    entry_y = 430
    entry_gap = 8
    entry_width = (content_width - entry_gap) / 2
    for index, entry in enumerate(data["entryModes"]):
        x = margin + index * (entry_width + entry_gap)
        rounded_box(canvas, x, entry_y, entry_width, 40, PALE_GRAY)
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(x + 9, entry_y + 25, entry["label"])
        canvas.setFillColor(MUTED)
        canvas.setFont("Courier", 5.7)
        canvas.drawString(x + 9, entry_y + 12, entry["code"])
        draw_code128(canvas, entry["code"], x + 88, entry_y + 8, entry_width - 98, 24)

    section_heading(
        canvas,
        "3",
        "Enter quantity",
        "Feet may use Decimal. Packs and sheets should stay whole numbers.",
        margin,
        419,
    )
    keypad_top = 391
    cell_gap = 5
    cell_width = (content_width - 3 * cell_gap) / 4
    cell_height = 42
    row_gap = 4
    for index, key in enumerate(data["keys"]):
        row = index // 4
        column = index % 4
        x = margin + column * (cell_width + cell_gap)
        y = keypad_top - (row + 1) * cell_height - row * row_gap
        fill = PALE_ORANGE if key["label"] in {"Backspace", "Clear", "Decimal"} else white
        rounded_box(canvas, x, y, cell_width, cell_height, fill)
        canvas.setFillColor(NAVY)
        label_size = 8.5 if len(key["label"]) <= 3 else 6.8
        canvas.setFont("Helvetica-Bold", label_size)
        canvas.drawString(x + 7, y + 29, key["label"])
        canvas.setFillColor(MUTED)
        canvas.setFont("Courier", 5.1)
        canvas.drawRightString(x + cell_width - 6, y + 29, key["code"])
        draw_code128(canvas, key["code"], x + 7, y + 5, cell_width - 14, 19)

    section_heading(
        canvas,
        "4",
        "Finish",
        "Confirm still uses ERPNext validation. Undo targets only the latest transaction.",
        margin,
        202,
    )
    action_y = 104
    action_gap = 6
    action_width = (content_width - 2 * action_gap) / 3
    tones = {
        "confirm": (PALE_TEAL, TEAL),
        "cancel": (PALE_RED, RED),
        "undo": (PALE_GOLD, GOLD),
    }
    for index, action in enumerate(data["actions"]):
        x = margin + index * (action_width + action_gap)
        fill, accent = tones[action["tone"]]
        rounded_box(canvas, x, action_y, action_width, 72, fill, accent)
        canvas.setFillColor(accent)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(x + 8, action_y + 55, action["label"])
        canvas.setFillColor(MUTED)
        fit_text(canvas, action["detail"], "Helvetica", 6.2, action_width - 16)
        canvas.drawString(x + 8, action_y + 44, action["detail"])
        draw_code128(canvas, action["code"], x + 8, action_y + 14, action_width - 16, 23)
        canvas.setFillColor(MUTED)
        canvas.setFont("Courier", 5.4)
        canvas.drawCentredString(x + action_width / 2, action_y + 5, action["code"])

    canvas.setStrokeColor(LINE)
    canvas.line(margin, 90, page_width - margin, 90)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawString(margin, 77, "Scanner: Bluetooth HID or 2.4G keyboard mode, Enter suffix enabled.")
    canvas.drawRightString(page_width - margin, 77, "Print at 100% - matte lamination recommended")
    canvas.setFont("Helvetica-Bold", 6.5)
    canvas.setFillColor(NAVY)
    canvas.drawString(margin, 64, "Workflow: mode -> paper label -> entry type (Consume only) -> quantity -> Confirm")

    canvas.showPage()
    canvas.save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True, type=site_origin, help="ERPNext site origin")
    parser.add_argument("--brand", default="Studio Inventory", help="optional heading and PDF author")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="destination PDF path")
    args = parser.parse_args()
    brand = args.brand.strip()
    if not brand:
        parser.error("brand must not be blank")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    build_pdf(data, args.output, args.origin, brand)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
