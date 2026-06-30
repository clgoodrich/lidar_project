"""Render a Markdown file to PDF with reportlab (no pandoc/LaTeX needed).

Handles the subset used by the FINESST proposal: ATX headings, paragraphs,
**bold**/*italic*/`code`/[links], pipe tables, ![images] (paths relative to the
md file), > blockquotes, horizontal rules, and - bullet lists.

Single source of truth = the .md; rerun to regenerate the .pdf after edits.

Run:  python barlow/build/_md_to_pdf.py barlow/docs/finesst_proposal.md
      (output -> same name with .pdf)
"""
from __future__ import annotations

import re
import sys
from html import escape
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                Table, TableStyle, HRFlowable, ListFlowable,
                                ListItem, KeepTogether)
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

NAVY = colors.HexColor("#1f3864")
ACCENT = colors.HexColor("#2e5496")
GREY = colors.HexColor("#666666")

# reportlab's builtin Helvetica is WinAnsi-only (no →, Δ, ≤, … glyphs). Register
# matplotlib's bundled DejaVu (full Unicode) so every char in the markdown renders.
FONT, FONT_B, FONT_I, FONT_BI, FONT_MONO = ("Helvetica", "Helvetica-Bold",
                                            "Helvetica-Oblique", "Helvetica-BoldOblique",
                                            "Courier")
try:
    import matplotlib
    _ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for name, fn in [("DejaVu", "DejaVuSans.ttf"), ("DejaVu-Bold", "DejaVuSans-Bold.ttf"),
                     ("DejaVu-Oblique", "DejaVuSans-Oblique.ttf"),
                     ("DejaVu-BoldOblique", "DejaVuSans-BoldOblique.ttf"),
                     ("DejaVuMono", "DejaVuSansMono.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(_ttf / fn)))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                                  italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")
    FONT, FONT_B, FONT_I, FONT_BI, FONT_MONO = ("DejaVu", "DejaVu-Bold", "DejaVu-Oblique",
                                                "DejaVu-BoldOblique", "DejaVuMono")
except Exception as e:  # fall back to Helvetica (some glyphs may drop)
    print(f"  [warn] DejaVu unavailable ({e}); using Helvetica")


def _styles():
    # uniform black text; hierarchy via size + bold on headings only (no color,
    # no inline bold in body, see inline()).
    base = dict(fontName=FONT, fontSize=9.5, leading=13, alignment=TA_LEFT,
                textColor=colors.black)
    out = {
        "title": ParagraphStyle("title", **{**base, "fontName": FONT_B,
                                            "fontSize": 16, "leading": 20, "spaceAfter": 10}),
        "h1": ParagraphStyle("h1", **{**base, "fontName": FONT_B,
                                      "fontSize": 13, "leading": 16,
                                      "spaceBefore": 12, "spaceAfter": 5}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": FONT_B,
                                      "fontSize": 11, "leading": 14,
                                      "spaceBefore": 9, "spaceAfter": 4}),
        "h3": ParagraphStyle("h3", **{**base, "fontName": FONT_B,
                                      "fontSize": 10, "leading": 13, "spaceBefore": 6,
                                      "spaceAfter": 3}),
        "body": ParagraphStyle("body", **{**base, "spaceAfter": 6}),
        "quote": ParagraphStyle("quote", **{**base, "fontSize": 9, "leading": 12,
                                            "leftIndent": 12, "borderPadding": 4,
                                            "spaceAfter": 6, "fontName": FONT_I}),
        "cap": ParagraphStyle("cap", **{**base, "fontSize": 8.3, "leading": 11,
                                        "spaceAfter": 8, "fontName": FONT_I}),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 8.2, "leading": 10}),
        "cellh": ParagraphStyle("cellh", **{**base, "fontSize": 8.2, "leading": 10,
                                            "fontName": FONT_B}),
        "li": ParagraphStyle("li", **{**base, "spaceAfter": 2}),
    }
    return out


def inline(md: str) -> str:
    """Markdown inline -> reportlab mini-HTML. Bold is dropped (no inline bolding);
    italic and code are kept."""
    # map emoji (not in DejaVu) to safe glyphs; strip variation selectors
    md = (md.replace("️", "").replace("✅", "✓").replace("⚠", "▲")
            .replace("⛔", "✗").replace("⚙", "•"))
    md = escape(md, quote=False)
    md = re.sub(r"\*\*\*([^*]+)\*\*\*", r"<i>\1</i>", md)  # bolditalic -> italic
    md = re.sub(r"`([^`]+)`", rf'<font face="{FONT_MONO}" size="8.5">\1</font>', md)
    md = re.sub(r"\*\*([^*]+)\*\*", r"\1", md)             # bold -> plain text
    md = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", md)
    md = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", md)     # links -> text
    return md


def build(md_path: Path):
    src = md_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    lines = src.split("\n")
    st = _styles()
    story = []
    page_w = letter[0] - 1.3 * inch  # usable width given margins below

    i, n = 0, len(lines)
    first_h1 = True
    while i < n:
        ln = lines[i]
        s = ln.strip()

        # blank
        if not s:
            i += 1
            continue

        # horizontal rule
        if re.fullmatch(r"-{3,}", s):
            story.append(Spacer(1, 2))
            story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#bbbbbb")))
            story.append(Spacer(1, 2))
            i += 1
            continue

        # images:  ![alt](path)
        m = re.fullmatch(r"!\[[^\]]*\]\(([^)]+)\)", s)
        if m:
            img_path = (md_path.parent / m.group(1)).resolve()
            if img_path.exists():
                from reportlab.lib.utils import ImageReader
                iw, ih = ImageReader(str(img_path)).getSize()
                w = page_w
                h = w * ih / iw
                max_h = 3.6 * inch
                if h > max_h:
                    h = max_h
                    w = h * iw / ih
                story.append(Spacer(1, 2))
                story.append(Image(str(img_path), width=w, height=h))
            i += 1
            continue

        # headings
        m = re.match(r"(#{1,3})\s+(.*)", s)
        if m:
            level = len(m.group(1))
            txt = inline(m.group(2))
            if level == 1 and first_h1:
                story.append(Paragraph(txt, st["title"]))
                first_h1 = False
            else:
                story.append(Paragraph(txt, st[f"h{level}"]))
            i += 1
            continue

        # blockquote (possibly multi-line)
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            story.append(Paragraph(inline(" ".join(b.strip() for b in buf)), st["quote"]))
            continue

        # table block (header row then |---| separator)
        if s.startswith("|") and i + 1 < n and re.match(r"\s*\|?[\s:|-]+\|", lines[i + 1]):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            # drop separator row (row index 1)
            cells = []
            for r_idx, raw in enumerate(rows):
                if r_idx == 1:
                    continue
                parts = [c.strip() for c in raw.strip().strip("|").split("|")]
                style = st["cellh"] if r_idx == 0 else st["cell"]
                cells.append([Paragraph(inline(p), style) for p in parts])
            ncol = max(len(r) for r in cells)
            for r in cells:
                while len(r) < ncol:
                    r.append(Paragraph("", st["cell"]))
            tbl = Table(cells, colWidths=[page_w / ncol] * ncol, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#999999")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(Spacer(1, 2))
            story.append(tbl)
            story.append(Spacer(1, 6))
            continue

        # bullet list block
        if re.match(r"[-*]\s+", s):
            items = []
            while i < n and re.match(r"\s*[-*]\s+", lines[i]):
                txt = re.sub(r"^\s*[-*]\s+", "", lines[i])
                items.append(ListItem(Paragraph(inline(txt), st["li"]), leftIndent=12))
                i += 1
            story.append(ListFlowable(items, bulletType="bullet", start="•",
                                      leftIndent=14, bulletFontSize=7))
            story.append(Spacer(1, 4))
            continue

        # caption (italic line right after an image, starts with *** or *)
        if s.startswith("*") and s.endswith("*") and not s.startswith("**"):
            story.append(Paragraph(inline(s.strip("*").strip()), st["cap"]))
            i += 1
            continue

        # default: paragraph (gather until blank)
        buf = [ln]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r"(#{1,3}\s|[-*]\s|>|\||!\[|-{3,}$)", lines[i].strip()):
            buf.append(lines[i])
            i += 1
        story.append(Paragraph(inline(" ".join(b.strip() for b in buf)), st["body"]))

    out_pdf = md_path.with_suffix(".pdf")

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(0.65 * inch, 0.45 * inch,
                          "FINESST S/T/M: MDV ephemeral-channel attribution (draft)")
        canvas.drawRightString(letter[0] - 0.65 * inch, 0.45 * inch,
                               f"p. {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(out_pdf), pagesize=letter,
                            leftMargin=0.65 * inch, rightMargin=0.65 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.65 * inch,
                            title="FINESST Proposal: MDV ephemeral-channel attribution")
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"wrote {out_pdf}  ({out_pdf.stat().st_size/1024:.0f} KB, {doc.page} pages)")


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).resolve().parents[1] / "docs" / "finesst_proposal.md"
    build(p)
