"""Build nisar_secondary_writeup_9t.docx from the .md beside it (the .md is the source).

Handles '# ', '## ', '### ' headings, pipe tables and plain paragraphs.
Run: python nisar/writeup/_make_secondary_writeup_docx.py
"""
from pathlib import Path

import docx
from docx.shared import Pt, Inches

HERE = Path(__file__).resolve().parent
MD = HERE / "nisar_secondary_writeup_9t.md"
OUT = HERE / "nisar_secondary_writeup_9t.docx"

d = docx.Document()
for s in d.sections:
    s.left_margin = s.right_margin = Inches(1)
    s.top_margin = s.bottom_margin = Inches(0.8)
st = d.styles["Normal"]
st.font.name, st.font.size = "Calibri", Pt(11)
st.paragraph_format.space_after = Pt(3)
for name, size in (("Heading 1", 13), ("Heading 2", 12), ("Heading 3", 11)):
    d.styles[name].font.size = Pt(size)
    d.styles[name].paragraph_format.space_before = Pt(6)
    d.styles[name].paragraph_format.space_after = Pt(2)

lines = MD.read_text(encoding="utf-8").splitlines()
i = 0
refs = False
while i < len(lines):
    ln = lines[i]
    if ln.startswith("### "):
        d.add_heading(ln[4:], level=3)
    elif ln.startswith("## "):
        d.add_heading(ln[3:], level=2)
    elif ln.startswith("# "):
        d.add_heading(ln[2:], level=1)
    elif ln.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            cells = [c.strip() for c in lines[i].strip("|").split("|")]
            if not set("".join(cells)) <= set("-: "):
                rows.append(cells)
            i += 1
        t = d.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Light Grid Accent 1"
        for r, row in enumerate(rows):
            for c, txt in enumerate(row):
                cell = t.cell(r, c)
                cell.text = txt
                for p in cell.paragraphs:
                    p.paragraph_format.space_after = Pt(0)
                    for run in p.runs:
                        run.font.size = Pt(9)
                        run.bold = r == 0
        d.add_paragraph().paragraph_format.space_after = Pt(0)
        continue
    elif ln.strip():
        p = d.add_paragraph(ln)
        if ln.startswith("Table "):
            p.runs[0].italic = True
        if refs:
            p.runs[0].font.size = Pt(9)
            p.paragraph_format.space_after = Pt(1)
    if ln.startswith("## References"):
        refs = True
    i += 1
d.save(OUT)
print("->", OUT)
