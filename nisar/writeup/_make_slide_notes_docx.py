"""Build nisar_checkpoint_slide_notes_9t.docx from the .md beside it (the .md is the source).

Keeps the styles of the existing .docx (Title, Normal, List Bullet, table style).
Handles '# ' headings, '- ' bullets, pipe tables and '<!-- pagebreak -->'.
"""
from pathlib import Path
import docx
from docx.enum.text import WD_BREAK

HERE = Path(__file__).resolve().parent
MD = HERE / "nisar_checkpoint_slide_notes_9t.md"
OUT = HERE / "nisar_checkpoint_slide_notes_9t.docx"

d = docx.Document(OUT)
tstyle = d.tables[0].style if d.tables else None
body = d.element.body
for el in list(body):
    if not el.tag.endswith("sectPr"):
        body.remove(el)

lines = MD.read_text(encoding="utf-8").splitlines()
i = 0
while i < len(lines):
    ln = lines[i]
    if ln.startswith("<!-- pagebreak"):
        if not (i and lines[i - 1].startswith("<!-- pagebreak")):
            d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    elif ln.startswith("# "):
        d.add_paragraph(ln[2:], style="Title")
    elif ln.startswith("- "):
        d.add_paragraph(ln[2:], style="List Bullet")
    elif ln.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            cells = [c.strip() for c in lines[i].strip("|").split("|")]
            if not set("".join(cells)) <= set("-: "):
                rows.append(cells)
            i += 1
        t = d.add_table(rows=len(rows), cols=len(rows[0]))
        if tstyle is not None:
            t.style = tstyle
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                t.cell(r, c).text = v
                if r == 0:
                    for run in t.cell(r, c).paragraphs[0].runs:
                        run.bold = True
        continue
    elif ln.strip():
        d.add_paragraph(ln, style="Normal")
    i += 1
d.save(OUT)
print(OUT)
