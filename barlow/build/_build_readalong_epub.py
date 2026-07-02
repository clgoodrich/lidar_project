"""Build an EPUB read-along of the Barlow dissertation.

EPUB is reflowable, so instead of the PDF's side-by-side panes each chapter
alternates: dissertation page image, then that page's ELI16 note from
barlow_dissertation_pagenotes.md. Chapters follow the dissertation's chapters.

Usage:  python barlow/build/_build_readalong_epub.py
Output: barlow/docs/BARLOW-DISSERTATION-2026_readalong.epub
        (gitignored: contains the full copyrighted dissertation as images)
"""
from __future__ import annotations

import html
import importlib.util
import sys
import zipfile
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "BARLOW-DISSERTATION-2026.pdf"
OUT = ROOT / "docs" / "BARLOW-DISSERTATION-2026_readalong.epub"
DPI = 130
JPG_QUALITY = 78

# Reuse the PDF builder's guide parser and markdown converter.
_spec = importlib.util.spec_from_file_location(
    "rb", Path(__file__).parent / "_build_readalong_pdf.py")
_rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rb)

CSS = """
body { font-family: sans-serif; line-height: 1.5; }
h1 { color: #123c5a; }
h2 { color: #123c5a; margin-top: 1.6em; }
h3.pg { color: #123c5a; border-top: 2px solid #d0d8e0; padding-top: 1em; margin-top: 1.4em; }
img.page { width: 100%; height: auto; border: 1px solid #ccc; }
div.note { background: #f4f7fa; padding: 0.6em 0.9em; border-radius: 6px; }
"""

XHTML_HEAD = ('<?xml version="1.0" encoding="utf-8"?>\n'
              '<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n'
              '<title>{title}</title>\n'
              '<link rel="stylesheet" type="text/css" href="style.css"/>\n'
              "</head>\n<body>\n")


def xhtmlize(s: str) -> str:
    """md_to_html output -> XHTML-safe (self-close nothing needed; escape stray &)."""
    return s.replace("&", "&amp;").replace("&amp;amp;", "&amp;") \
            .replace("&amp;lt;", "&lt;").replace("&amp;gt;", "&gt;")


def main() -> int:
    blocks, front = _rb.parse_guide()
    chapters = [b for b in blocks if b["level"] == 2]
    pages = [b for b in blocks if b["level"] >= 3]
    page_of = {}
    for b in pages:
        for p in range(b["a"], b["b"] + 1):
            page_of.setdefault(p, b)

    src = fitz.open(SRC)
    n = src.page_count

    # Chapter spans: cover every page 1..n; pages before the first chapter and
    # after the last go into synthetic front/back groups.
    spans = []
    first_ch = min(c["a"] for c in chapters)
    if first_ch > 1:
        spans.append({"title": "Front matter & Abstract", "a": 1, "b": first_ch - 1})
    for c in sorted(chapters, key=lambda c: c["a"]):
        spans.append({"title": c["title"], "a": c["a"], "b": c["b"],
                      "body": "\n".join(c["body"])})
    last = max(s["b"] for s in spans)
    if last < n:
        spans.append({"title": "References & Appendices", "a": last + 1, "b": n})

    files: list[tuple[str, bytes]] = []  # (zip path, data)
    manifest, spine, navpts = [], [], []

    # Intro page from the guide's front matter (cover text).
    intro = XHTML_HEAD.format(title="How to use this book")
    intro += xhtmlize(_rb.md_to_html(front)) + "</body></html>"
    files.append(("OEBPS/intro.xhtml", intro.encode("utf-8")))
    manifest.append('<item id="intro" href="intro.xhtml" media-type="application/xhtml+xml"/>')
    spine.append('<itemref idref="intro"/>')
    navpts.append('<li><a href="intro.xhtml">How to use this book</a></li>')

    for ci, ch in enumerate(spans):
        title = ch["title"]
        parts = [XHTML_HEAD.format(title=html.escape(title)), f"<h1>{html.escape(title)}</h1>"]
        if ch.get("body"):
            parts.append(xhtmlize(_rb.md_to_html(ch["body"])))
        done = set()
        for p in range(ch["a"], min(ch["b"], n) + 1):
            pix = src[p - 1].get_pixmap(dpi=DPI, colorspace=fitz.csRGB)
            img_name = f"img/p{p:03d}.jpg"
            files.append((f"OEBPS/{img_name}", pix.tobytes("jpeg", jpg_quality=JPG_QUALITY)))
            manifest.append(f'<item id="i{p}" href="{img_name}" media-type="image/jpeg"/>')
            b = page_of.get(p)
            hdr = b["title"] if b else f"Page {p}"
            parts.append(f'<h3 class="pg">{html.escape(hdr)}</h3>')
            parts.append(f'<img class="page" src="{img_name}" alt="dissertation page {p}"/>')
            if b and id(b) not in done:
                done.add(id(b))
                parts.append('<div class="note">' +
                             xhtmlize(_rb.md_to_html("\n".join(b["body"]))) + "</div>")
        parts.append("</body></html>")
        fname = f"ch{ci:02d}.xhtml"
        files.append((f"OEBPS/{fname}", "\n".join(parts).encode("utf-8")))
        manifest.append(f'<item id="c{ci}" href="{fname}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{ci}"/>')
        navpts.append(f'<li><a href="{fname}">{html.escape(title)}</a></li>')
        print(f"  chapter {ci+1}/{len(spans)}: {title} (pp. {ch['a']}-{ch['b']})")

    nav = (XHTML_HEAD.format(title="Contents").replace("<html ",
           '<html xmlns:epub="http://www.idpf.org/2007/ops" ') +
           '<nav epub:type="toc"><h1>Contents</h1><ol>' + "\n".join(navpts) +
           "</ol></nav></body></html>")
    files.append(("OEBPS/nav.xhtml", nav.encode("utf-8")))
    manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
    files.append(("OEBPS/style.css", CSS.encode("utf-8")))
    manifest.append('<item id="css" href="style.css" media-type="text/css"/>')

    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="uid">urn:barlow-dissertation-readalong-2026</dc:identifier>
<dc:title>Barlow Dissertation Read-Along (ELI16 companion)</dc:title>
<dc:language>en</dc:language>
<dc:creator>Companion notes; dissertation by Mary C. Barlow (2026)</dc:creator>
<meta property="dcterms:modified">2026-07-02T00:00:00Z</meta>
</metadata>
<manifest>{"".join(manifest)}</manifest>
<spine>{"".join(spine)}</spine>
</package>'''
    files.append(("OEBPS/content.opf", opf.encode("utf-8")))
    files.append(("META-INF/container.xml", b'''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''))

    with zipfile.ZipFile(OUT, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        for path, data in files:
            z.writestr(path, data, compress_type=zipfile.ZIP_DEFLATED)
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
