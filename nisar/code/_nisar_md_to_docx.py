"""Convert a NISAR markdown write-up to a plain Word file (made 2026-11-23).

Why: the user wanted the write-up in .docx, plain academic style. Times New Roman everywhere, one size
(11 pt), black text, bold headings, black table rules, figures in grayscale. No other fonts or colours.

Handles what the write-ups use: # and ## headings, paragraphs, pipe tables, - bullets, 1. numbered items,
![alt](path) images (the next paragraph is its caption), and a leading <style> block (skipped).
**bold** and *italic* markers are kept as bold and italic runs.

Run from the repository root:
  python nisar/code/_nisar_md_to_docx.py path/to/doc.md [out.docx]
"""
import re
import sys
import tempfile
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

FONT, SIZE = "Times New Roman", Pt(11)
BLACK = RGBColor(0, 0, 0)


def style_all(doc):
    for st in doc.styles:
        try:
            f = st.font
        except AttributeError:
            continue
        f.name, f.size, f.color.rgb = FONT, SIZE, BLACK
        rpr = st.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = rpr.makeelement(qn("w:rFonts"), {})
            rpr.append(rfonts)
        for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rfonts.set(qn(a), FONT)
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rfonts.get(qn(a)) is not None:
                del rfonts.attrib[qn(a)]
    for h in ("Title", "Heading 1", "Heading 2", "Heading 3"):
        st = doc.styles[h]
        st.font.bold, st.font.italic = True, False
        st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(10), Pt(3)
        st.paragraph_format.keep_with_next = True
        pPr = st.element.get_or_add_pPr()
        for b in pPr.findall(qn("w:pBdr")):
            pPr.remove(b)
    n = doc.styles["Normal"].paragraph_format
    n.space_before, n.space_after, n.line_spacing = Pt(0), Pt(4), 1.1


def add_runs(par, text):
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", text):
        if not part:
            continue
        if part.startswith("**"):
            r = par.add_run(part[2:-2]); r.bold = True
        elif part.startswith("*"):
            r = par.add_run(part[1:-1]); r.italic = True
        else:
            r = par.add_run(part)
        r.font.name, r.font.size, r.font.color.rgb = FONT, SIZE, BLACK


def add_table(doc, rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    t = doc.add_table(rows=len(cells), cols=len(cells[0]))
    t.style = doc.styles["Table Grid"]
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, r in enumerate(cells):
        for j, c in enumerate(r):
            p = t.cell(i, j).paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            add_runs(p, f"**{c}**" if i == 0 and c else c)
    doc.add_paragraph()


def add_image(doc, src, tmp):
    g = Path(tmp) / (Path(src).stem + "_gray.png")
    Image.open(src).convert("L").save(g)
    doc.add_picture(str(g), width=Inches(5.0))
    doc.paragraphs[-1].alignment = 1


def convert(md_path, out):
    md = Path(md_path)
    text = re.sub(r"(?s)^\s*<style>.*?</style>\s*", "", md.read_text(encoding="utf-8"))
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(1))
    style_all(doc)
    lines = text.splitlines()
    i = 0
    with tempfile.TemporaryDirectory() as tmp:
        while i < len(lines):
            ln = lines[i].rstrip()
            if not ln:
                i += 1
                continue
            if ln.startswith("# "):
                doc.add_paragraph(ln[2:], style="Title")
            elif ln.startswith("## "):
                doc.add_paragraph(ln[3:], style="Heading 1")
            elif ln.startswith("### "):
                doc.add_paragraph(ln[4:], style="Heading 2")
            elif ln.startswith("|"):
                rows = []
                while i < len(lines) and lines[i].startswith("|"):
                    rows.append(lines[i]); i += 1
                add_table(doc, rows)
                continue
            elif m := re.match(r"!\[[^\]]*\]\(([^)]+)\)", ln):
                add_image(doc, md.parent / m.group(1), tmp)
            elif re.match(r"- ", ln):
                add_runs(doc.add_paragraph(style="List Bullet"), ln[2:])
            elif re.match(r"\d+\. ", ln):
                add_runs(doc.add_paragraph(style="List Number"), re.sub(r"^\d+\. ", "", ln))
            else:
                add_runs(doc.add_paragraph(), ln)
            i += 1
        doc.save(out)
    print(out)


if __name__ == "__main__":
    src = Path(sys.argv[1])
    convert(src, sys.argv[2] if len(sys.argv) > 2 else src.with_suffix(".docx"))
