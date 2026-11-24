"""Build nisar_checkpoint_slide_notes_9t.pdf from the .md beside it, laid out for easy reading.

Each slide starts a new page. Paragraph lead-ins ("What the slide says.", "Step 2. ...", "Risk 1. ...")
are set in bold. Rendering is done by nisar/code/_nisar_doc_to_pdf.py.
Run from the repository root: python nisar/writeup/_make_slide_notes_pdf.py
"""
import re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MD = HERE / "nisar_checkpoint_slide_notes_9t.md"
PDF = MD.with_suffix(".pdf")
LEAD = re.compile(r"^((?:Step|Risk) \d\.[^.]*\.|(?!These )[A-Z][\w ,'-]{2,40}\.)( |$)")

s = re.sub(r"<!-- pagebreak -->\n?", "", MD.read_text(encoding="utf-8"))
s = s.replace("\n# ", '\n<div style="page-break-before:always"></div>\n\n# ')
lines = []
for ln in s.split("\n"):
    m = LEAD.match(ln)
    if m and not ln.startswith(("#", "-", "|")):
        ln = f"**{m.group(1)}**" + ln[len(m.group(1)):]
    if ln.startswith("- ") and lines and lines[-1].strip() and not lines[-1].startswith("- "):
        lines.append("")  # markdown needs a blank line before a list
    lines.append(ln)
tmp = Path(tempfile.mkdtemp()) / MD.name
tmp.write_text("\n".join(lines), encoding="utf-8")
subprocess.run([sys.executable, str(HERE.parent / "code" / "_nisar_doc_to_pdf.py"), str(tmp), str(PDF)], check=True)
