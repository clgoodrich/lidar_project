"""Render a Markdown file to .docx with python-docx (no pandoc needed).

Same Markdown subset as _md_to_pdf.py: ATX headings, paragraphs with
***bolditalic***/**bold**/*italic*/`code`/[links], pipe tables, ![images]
(paths relative to the md file), > blockquotes, horizontal rules, - bullets,
and *figure captions*. The .md stays the single source of truth.

Run:  python barlow/build/_md_to_docx.py barlow/docs/finesst_proposal.md
      (output -> same name with .docx)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

NAVY = RGBColor(0x1F, 0x38, 0x64)
ACCENT = RGBColor(0x2E, 0x54, 0x96)
GREY = RGBColor(0x66, 0x66, 0x66)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

# bolditalic | code | bold | link | italic   (order = precedence)
TOKEN = re.compile(
    r"\*\*\*(?P<bi>[^*]+)\*\*\*"
    r"|`(?P<code>[^`]+)`"
    r"|\*\*(?P<bold>[^*]+)\*\*"
    r"|\[(?P<ltext>[^\]]+)\]\((?P<lurl>[^)]+)\)"
    r"|\*(?P<ital>[^*]+)\*")


def add_runs(par, text, base_size=None, base_color=None):
    """Append formatted runs to a paragraph from inline markdown."""
    pos = 0
    for m in TOKEN.finditer(text):
        if m.start() > pos:
            _run(par, text[pos:m.start()], base_size, base_color)
        if m.group("bi") is not None:
            _run(par, m.group("bi"), base_size, base_color, italic=True)  # no bold
        elif m.group("code") is not None:
            _run(par, m.group("code"), base_size, base_color, mono=True)
        elif m.group("bold") is not None:
            _run(par, m.group("bold"), base_size, base_color)  # bold dropped -> plain
        elif m.group("ltext") is not None:
            _run(par, m.group("ltext"), base_size, base_color)  # link -> text
        elif m.group("ital") is not None:
            _run(par, m.group("ital"), base_size, base_color, italic=True)
        pos = m.end()
    if pos < len(text):
        _run(par, text[pos:], base_size, base_color)


def _run(par, txt, size, color, bold=False, italic=False, mono=False):
    r = par.add_run(txt)
    r.bold = bold
    r.italic = italic
    r.font.name = "Consolas" if mono else "Calibri"
    if mono:
        r.font.size = Pt((size or 10.5) - 1.5)
    elif size:
        r.font.size = Pt(size)
    if color:
        r.font.color.rgb = color


def _shade(cell, hex_fill):
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), hex_fill)
    cell._tc.get_or_add_tcPr().append(sh)


def _img_size(path):
    from PIL import Image as PImg
    with PImg.open(path) as im:
        return im.size  # (w, h) px


def build(md_path: Path):
    src = md_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    lines = src.split("\n")
    doc = Document()
    # base style
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    for sec in doc.sections:
        sec.top_margin = sec.bottom_margin = Inches(0.7)
        sec.left_margin = sec.right_margin = Inches(0.9)
    usable_in = (doc.sections[0].page_width - doc.sections[0].left_margin
                 - doc.sections[0].right_margin) / 914400  # EMU -> inches

    i, n = 0, len(lines)
    first_h1 = True
    while i < n:
        ln = lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue

        # horizontal rule -> thin bottom border paragraph
        if re.fullmatch(r"-{3,}", s):
            p = doc.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            pbdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:space"), "1"); bottom.set(qn("w:color"), "BBBBBB")
            pbdr.append(bottom); pPr.append(pbdr)
            i += 1
            continue

        # image
        m = re.fullmatch(r"!\[[^\]]*\]\(([^)]+)\)", s)
        if m:
            img = (md_path.parent / m.group(1)).resolve()
            if img.exists():
                pw, ph = _img_size(img)
                w = usable_in
                if w * ph / pw > 4.0:      # cap tall figures by height
                    w = 4.0 * pw / ph
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(str(img), width=Inches(min(w, usable_in)))
            i += 1
            continue

        # headings
        m = re.match(r"(#{1,3})\s+(.*)", s)
        if m:
            lvl, txt = len(m.group(1)), m.group(2)
            if lvl == 1 and first_h1:
                p = doc.add_paragraph(); p.space_after = Pt(8)
                add_runs(p, txt, base_size=18)
                for r in p.runs:
                    r.bold = True
                first_h1 = False
            else:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(10 if lvl == 1 else 7)
                p.paragraph_format.space_after = Pt(3)
                size = {1: 14, 2: 12, 3: 10.5}[lvl]
                add_runs(p, txt, base_size=size)
                for r in p.runs:
                    r.bold = True
            i += 1
            continue

        # blockquote
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]).strip())
                i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.space_after = Pt(8)
            add_runs(p, " ".join(buf), base_size=10)
            continue

        # table
        if s.startswith("|") and i + 1 < n and re.match(r"\s*\|?[\s:|-]+\|", lines[i + 1]):
            raw = []
            while i < n and lines[i].strip().startswith("|"):
                raw.append(lines[i].strip())
                i += 1
            rows = []
            for r_idx, r in enumerate(raw):
                if r_idx == 1:
                    continue
                rows.append([c.strip() for c in r.strip().strip("|").split("|")])
            ncol = max(len(r) for r in rows)
            tbl = doc.add_table(rows=len(rows), cols=ncol)
            tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            tbl.style = "Table Grid"
            tbl.autofit = True
            for ri, row in enumerate(rows):
                for ci in range(ncol):
                    cell = tbl.cell(ri, ci)
                    cell.paragraphs[0].text = ""
                    par = cell.paragraphs[0]
                    par.paragraph_format.space_after = Pt(1)
                    txt = row[ci] if ci < len(row) else ""
                    if ri == 0:
                        _shade(cell, "E8E8E8")
                        add_runs(par, txt, base_size=9)
                        for rr in par.runs:
                            rr.bold = True
                    else:
                        add_runs(par, txt, base_size=9)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            continue

        # bullet list
        if re.match(r"[-*]\s+", s):
            while i < n and re.match(r"\s*[-*]\s+", lines[i]):
                txt = re.sub(r"^\s*[-*]\s+", "", lines[i])
                p = doc.add_paragraph(style="List Bullet")
                p.paragraph_format.space_after = Pt(1)
                add_runs(p, txt)
                i += 1
            continue

        # figure caption: whole line wrapped in * ... *
        if s.startswith("*") and s.endswith("*"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(8)
            add_runs(p, s, base_size=9, base_color=GREY)
            for r in p.runs:
                r.italic = True
            i += 1
            continue

        # paragraph (gather lines until blank / block start)
        buf = [ln]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r"(#{1,3}\s|[-*]\s|>|\||!\[|-{3,}$)", lines[i].strip()):
            buf.append(lines[i])
            i += 1
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        add_runs(p, " ".join(b.strip() for b in buf))

    # footer with page numbers
    footer = doc.sections[0].footer
    fp = footer.paragraphs[0]
    fp.text = "FINESST S/T/M — MDV ephemeral-channel attribution (draft)\t\t"
    fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = fp.add_run()
    fld1 = OxmlElement("w:fldSimple"); fld1.set(qn("w:instr"), "PAGE")
    run._r.addprevious(fld1)
    for r in fp.runs:
        r.font.size = Pt(8); r.font.color.rgb = GREY

    out = md_path.with_suffix(".docx")
    doc.save(str(out))
    print(f"wrote {out}  ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).resolve().parents[1] / "docs" / "finesst_proposal.md"
    build(p)
