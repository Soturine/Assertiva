"""Regenerate warehouse/docs/requirements.pdf (dev-only; needs Pillow and reportlab, which Assertiva does not depend on).

Page 1 carries RF-01 as text. Page 2 carries Figure 1, the exception flow, as a raster image only: no text layer, no
alternative text, and nothing in the metadata names the rule. A text extractor therefore sees RF-01 and a caption,
never the approval threshold. tests/test_document_assurance_demo.py checks those properties of the committed file.

    python tools/make_requirements_pdf.py   (from examples/document-assurance)
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[1] / "warehouse" / "docs" / "requirements.pdf"

PAGE1 = [
    ("Warehouse service - functional requirements", 15),
    ("Revision B (approved), synthetic document for the Assertiva demo", 9),
    ("", 9),
    ("RF-01 Stock transfer", 12),
    ("An operator moves a quantity of one item from a source location to a destination location.", 10),
    ("1. The operator must hold the permission stock:transfer; otherwise the request is refused (403).", 10),
    ("2. The quantity is a positive integer and the two locations differ; otherwise 422.", 10),
    ("3. The source must hold at least the requested quantity; otherwise 409 INSUFFICIENT_STOCK.", 10),
    ("4. Stock is moved atomically: on any failure no location changes.", 10),
    ("5. After a successful move, the event stock.transferred is published once.", 10),
    ("", 10),
    ("Exception flows are specified in Figure 1 (page 2).", 10),
]


def _font(size: int, bold: bool = False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _box(draw, xy, text, font, shape="rect"):
    x0, y0, x1, y1 = xy
    if shape == "diamond":
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        draw.polygon([(cx, y0), (x1, cy), (cx, y1), (x0, cy)], outline="black", width=4, fill="#fff7d6")
    else:
        draw.rounded_rectangle(xy, radius=18, outline="black", width=4, fill="#e8f0ff" if shape == "rect" else "#ffe3e3")
    lines = text.split("\n")
    heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    y = (y0 + y1) / 2 - sum(heights) / 2 - 6 * (len(lines) - 1) / 2
    for line, h in zip(lines, heights):
        w = draw.textbbox((0, 0), line, font=font)[2]
        draw.text(((x0 + x1) / 2 - w / 2, y), line, fill="black", font=font)
        y += h + 6


def _arrow(draw, a, b, label=None, font=None):
    draw.line([a, b], fill="black", width=4)
    (ax, ay), (bx, by) = a, b
    if bx == ax:
        d = 1 if by > ay else -1
        draw.polygon([(bx - 12, by - 22 * d), (bx + 12, by - 22 * d), (bx, by)], fill="black")
    else:
        d = 1 if bx > ax else -1
        draw.polygon([(bx - 22 * d, by - 12), (bx - 22 * d, by + 12), (bx, by)], fill="black")
    if label:
        draw.text(((ax + bx) / 2 + 10, (ay + by) / 2 - 34), label, fill="black", font=font)


def figure() -> Image.Image:
    img = Image.new("RGB", (1600, 1500), "white")
    d = ImageDraw.Draw(img)
    f, fb = _font(34), _font(38, bold=True)
    d.text((60, 40), "Figure 1 - Transfer exception flow", fill="black", font=fb)
    _box(d, (500, 140, 1100, 260), "Valid request from an\nauthorized operator", f)
    _arrow(d, (800, 260), (800, 340))
    _box(d, (450, 340, 1150, 620), "qty > 100 ?", fb, shape="diamond")
    _arrow(d, (800, 620), (800, 1180), "no", f)
    _arrow(d, (1150, 480), (1300, 480), "yes", f)
    _box(d, (1180, 520, 1560, 820), "supervisor\napproval\npresent ?", f, shape="diamond")
    _arrow(d, (1370, 820), (1370, 1180), "yes", f)
    _arrow(d, (1180, 670), (500, 670), "no", f)
    _box(d, (40, 600, 500, 900), "Reject 409\nAPPROVAL_REQUIRED\nno stock moved\nno event", f, shape="reject")
    _box(d, (600, 1180, 1560, 1320), "Continue with RF-01 steps 3-5", f)
    d.text((60, 1400), "A quantity of exactly 100 needs no approval.", fill="black", font=f)
    return img


def build() -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=1)  # invariant: reproducible bytes (no dates, fixed id)
    pdf.setTitle("Warehouse service - functional requirements")
    pdf.setAuthor("Assertiva demo")
    pdf.setSubject("")
    width, height = A4
    y = height - 72
    for text, size in PAGE1:
        pdf.setFont("Helvetica-Bold" if size >= 12 else "Helvetica", size)
        pdf.drawString(56, y, text)
        y -= size + 10
    pdf.setFont("Helvetica", 8)
    pdf.drawString(56, 40, "page 1 of 2")
    pdf.showPage()
    png = io.BytesIO()
    figure().save(png, format="PNG", optimize=True)
    png.seek(0)
    pdf.drawImage(ImageReader(png), 40, 160, width=width - 80, height=(width - 80) * 1500 / 1600)
    pdf.showPage()  # page 2 carries no text at all, not even a page number: the figure is the only content
    pdf.save()
    return buffer.getvalue()


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(build())
    print(OUT)
