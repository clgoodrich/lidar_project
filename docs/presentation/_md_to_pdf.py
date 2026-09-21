"""Render a Markdown document to a readable PDF.

Deliberately small. It handles exactly the constructs this project's documents
use -- headings, paragraphs, bullet lists, horizontal rules, inline bold and
inline code -- and nothing else. A general Markdown engine would be more code
and more failure modes for no gain here.

Questions set in bold at the start of a paragraph are given extra space above,
so a long Q&A document breaks into readable blocks rather than a wall.

Run:
    python docs/presentation/_md_to_pdf.py <in.md> <out.pdf> ["Doc title"]
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (ListFlowable, ListItem, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer)
from reportlab.platypus.flowables import HRFlowable

INK, MUTED, RULE, ACCENT = "#141A1F", "#6B7278", "#C8C8C0", "#0F5C8C"
MARGIN = 0.8 * inch


def inline(s: str) -> str:
    """Markdown inline -> reportlab markup, escaping everything else first."""
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', s)
    # em dash and arrow tidy-ups so they do not render as ASCII soup
    return s.replace("--&gt;", "&#8594;")


def styles():
    return {
        "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20,
                             leading=25, textColor=INK, spaceAfter=4),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14.5,
                             leading=19, textColor=ACCENT,
                             spaceBefore=20, spaceAfter=8),
        "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11.5,
                             leading=15, textColor=INK,
                             spaceBefore=12, spaceAfter=5),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10.5,
                               leading=15, textColor=INK, alignment=TA_LEFT,
                               spaceAfter=8),
        "q": ParagraphStyle("q", fontName="Helvetica", fontSize=10.5,
                            leading=15, textColor=INK, alignment=TA_LEFT,
                            spaceBefore=13, spaceAfter=8),
        "li": ParagraphStyle("li", fontName="Helvetica", fontSize=10.5,
                             leading=14.5, textColor=INK, spaceAfter=4),
    }


def build(md: str, out: Path, title: str) -> int:
    st = styles()
    story, bullets = [], []

    def flush():
        if bullets:
            story.append(ListFlowable(
                [ListItem(Paragraph(b, st["li"]), leftIndent=14)
                 for b in bullets],
                bulletType="bullet", start="•", leftIndent=16,
                bulletFontSize=8))
            story.append(Spacer(1, 6))
            bullets.clear()

    para: list[str] = []

    def flush_para():
        if not para:
            return
        text = " ".join(para).strip()
        para.clear()
        if not text:
            return
        # a question is a paragraph that is entirely bold
        is_q = text.startswith("**Q.") or (text.startswith("**")
                                           and text.rstrip().endswith("**"))
        story.append(Paragraph(inline(text), st["q"] if is_q else st["body"]))

    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("# "):
            flush_para(); flush()
            story.append(Paragraph(inline(line[2:]), st["h1"]))
        elif line.startswith("## "):
            flush_para(); flush()
            story.append(Paragraph(inline(line[3:]), st["h2"]))
        elif line.startswith("### "):
            flush_para(); flush()
            story.append(Paragraph(inline(line[4:]), st["h3"]))
        elif line.strip() in ("---", "***", "___"):
            flush_para(); flush()
            story.append(HRFlowable(width="100%", thickness=0.7, color=RULE,
                                    spaceBefore=10, spaceAfter=4))
        elif line.startswith("- "):
            flush_para()
            bullets.append(inline(line[2:]))
        elif line.startswith("  ") and bullets:
            bullets[-1] += " " + inline(line.strip())   # wrapped bullet
        elif not line.strip():
            flush_para(); flush()
        else:
            flush_para() if bullets else None
            flush()
            para.append(line)
    flush_para(); flush()

    doc = SimpleDocTemplate(
        str(out), pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=title, author="Colton Goodrich")

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 0.5 * inch, title)
        canvas.drawRightString(letter[0] - MARGIN, 0.5 * inch,
                               str(canvas.getPageNumber()))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return doc.page


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    title = sys.argv[3] if len(sys.argv) > 3 else src.stem.replace("_", " ")
    pages = build(src.read_text(encoding="utf-8"), out, title)
    print(f"  {pages} pages, {out.stat().st_size / 1e3:.0f} KB")
    print(f"  {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
