"""Build a notes-pages PDF: each page is one slide above its speaker notes.

WHY NOT POWERPOINT'S OWN NOTES PAGES EXPORT
-------------------------------------------
That export needs PowerPoint, and it shrinks the slide to roughly the top third
of the page with the notes in a fixed placeholder that clips long text. These
notes run to a thousand characters on some slides, so they would be cut.

This lays the page out for reading instead: the slide as large as the width
allows, then every note paragraph below it, wrapping freely down the page and
continuing onto a second page when a note is long enough to need it.

HOW
---
1. LibreOffice converts the .pptx to a slides-only PDF.
2. PyMuPDF rasterises each page of that PDF to a PNG.
3. reportlab lays out one document: slide image, rule, notes, footer.

Notes are read from the .pptx directly rather than from the PDF, since the
slides-only export does not carry them.

Run:
    python docs/presentation/_build_notes_pages_pdf.py [deck.pptx] [out.pdf]

Defaults to v12 and writes beside it; pass an output path to put it elsewhere.
"""
from __future__ import annotations

import html
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz
from pptx import Presentation
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer)
from reportlab.platypus.flowables import HRFlowable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DECK = ROOT / "docs/presentation/WellSight_Presentation v12.pptx"

SOFFICE = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
RENDER_DPI = 140

MARGIN = 0.55 * inch
PAGE_W, PAGE_H = letter

INK = "#141A1F"
MUTED = "#6B7278"
RULE = "#C8C8C0"


def render_slides(deck: Path, workdir: Path) -> list[Path]:
    """pptx -> pdf -> one PNG per slide."""
    if not SOFFICE.exists():
        raise SystemExit(f"LibreOffice not found at {SOFFICE}")
    print("  converting deck to PDF ...")
    subprocess.run([str(SOFFICE), "--headless", "--convert-to", "pdf",
                    "--outdir", str(workdir), str(deck)],
                   check=True, capture_output=True, timeout=1800)
    pdfs = list(workdir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit("LibreOffice produced no PDF")
    doc = fitz.open(pdfs[0])
    print(f"  rasterising {doc.page_count} pages at {RENDER_DPI} dpi ...")
    out = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=RENDER_DPI)
        p = workdir / f"slide_{i + 1:03d}.png"
        pix.save(p)
        out.append(p)
    doc.close()
    return out


def styles():
    body = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=10.5, leading=14.5,
        textColor=INK, alignment=TA_LEFT, spaceAfter=7)
    head = ParagraphStyle(
        "head", fontName="Helvetica-Bold", fontSize=10, leading=13,
        textColor=MUTED, spaceAfter=10)
    return head, body


def main() -> int:
    deck = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DECK
    out = (Path(sys.argv[2]) if len(sys.argv) > 2
           else deck.with_name(deck.stem + " - notes pages.pdf"))
    if not deck.exists():
        raise SystemExit(f"deck not found: {deck}")

    prs = Presentation(deck)
    notes = []
    for s in prs.slides:
        t = (s.notes_slide.notes_text_frame.text.strip()
             if s.has_notes_slide else "")
        notes.append(t)

    work = Path(tempfile.mkdtemp(prefix="notespages_"))
    try:
        pngs = render_slides(deck, work)
        if len(pngs) != len(notes):
            print(f"  WARNING: {len(pngs)} rendered pages vs "
                  f"{len(notes)} slides; pairing by position")

        head, body = styles()
        img_w = PAGE_W - 2 * MARGIN
        img_h = img_w * 7.5 / 13.3333          # the deck's own 16:9 slide size

        doc = SimpleDocTemplate(
            str(out), pagesize=letter,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=MARGIN, bottomMargin=MARGIN,
            title=f"{deck.stem} - slides and speaker notes",
            author="Colton Goodrich")

        story = []
        n = min(len(pngs), len(notes))
        for i in range(n):
            img = Image(str(pngs[i]), width=img_w, height=img_h)
            # a hairline around the slide, because the slide's own background
            # is near-white and otherwise bleeds into the page
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.7,
                                    color=RULE, spaceBefore=2, spaceAfter=8))
            story.append(Paragraph(f"Slide {i + 1} of {n}", head))
            text = notes[i] or "(no notes)"
            for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
                story.append(Paragraph(
                    html.escape(para).replace("\n", " "), body))
            if i != n - 1:
                story.append(PageBreak())

        print(f"  writing {n} pages ...")
        doc.build(story)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    size = out.stat().st_size / 1e6
    print(f"\n  {n} pages, {size:.1f} MB")
    print(f"  {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
