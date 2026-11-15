"""Render a NISAR markdown doc to PDF via markdown + headless Edge/Chrome.
Reads  nisar/docs/NISAR_PROCESS_AND_OUTCOMES.md
Writes nisar/docs/NISAR_PROCESS_AND_OUTCOMES.pdf
Run from the repository root: python nisar/code/_nisar_doc_to_pdf.py
"""
import subprocess, sys, tempfile
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "nisar" / "docs" / "NISAR_PROCESS_AND_OUTCOMES.md"
OUT = SRC.with_suffix(".pdf")
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
"""
body = markdown.markdown(SRC.read_text(encoding="utf-8"), extensions=["tables", "sane_lists"])
html = f"<!doctype html><meta charset='utf-8'><title>NISAR process and outcomes</title><style>{CSS}</style>{body}"
with tempfile.TemporaryDirectory() as d:
    h = Path(d) / "doc.html"
    h.write_text(html, encoding="utf-8")
    exe = next(b for b in BROWSERS if Path(b).exists())
    subprocess.run([exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={OUT}", h.as_uri()], check=True, timeout=120)
print(OUT, OUT.stat().st_size)
