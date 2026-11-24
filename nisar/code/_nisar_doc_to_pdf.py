"""Render a NISAR markdown doc to PDF via markdown + headless Edge/Chrome.
Reads  nisar/docs/NISAR_PROCESS_AND_OUTCOMES.md, or the markdown file given as the first argument
Writes the same name with .pdf. Images are resolved relative to the markdown file.
Run from the repository root: python nisar/code/_nisar_doc_to_pdf.py [path/to/doc.md]
"""
import subprocess, sys, tempfile
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parents[2]
SRC = (Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "nisar" / "docs" / "NISAR_PROCESS_AND_OUTCOMES.md")
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else SRC.with_suffix(".pdf")
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
CSS = """
@page { size: Letter; margin: 0.8in; }
body { font-family: Segoe UI, Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1d2329; }
h1 { font-size: 22pt; border-bottom: 2px solid #1F5FA8; padding-bottom: 4px; }
h2 { font-size: 15pt; color: #1F5FA8; margin-top: 22px; break-after: avoid; }
h3 { font-size: 12pt; break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9.5pt; break-inside: avoid; }
th { background: #E8EEF6; text-align: left; }
th, td { border: 1px solid #b8c0c8; padding: 4px 6px; vertical-align: top; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f1f3f5; padding: 0 2px; word-break: break-all; }
li { margin: 2px 0; }
img { max-width: 100%; display: block; margin: 6px auto 2px; }
img + em, p > em:only-child { font-size: 9pt; color: #4b5360; }
"""
body = markdown.markdown(SRC.read_text(encoding="utf-8"), extensions=["tables", "sane_lists"])
html = f"<!doctype html><meta charset='utf-8'><base href='{SRC.parent.as_uri()}/'><title>{SRC.stem}</title><style>{CSS}</style>{body}"
import time
start = time.time()
with tempfile.TemporaryDirectory() as d:
    h = Path(d) / "doc.html"
    h.write_text(html, encoding="utf-8")
    exe = next(b for b in BROWSERS if Path(b).exists())
    subprocess.run([exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={OUT}", h.as_uri()], check=True, timeout=120)
if not OUT.exists() or OUT.stat().st_mtime < start:
    sys.exit(f"PDF was NOT updated (is it open in a viewer?): {OUT}")
print(OUT, OUT.stat().st_size)
