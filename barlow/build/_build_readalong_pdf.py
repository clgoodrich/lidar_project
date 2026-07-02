"""Build a side-by-side read-along PDF for the Barlow dissertation.

Each output page is landscape: the original dissertation page on the left,
the matching section of barlow_dissertation_readalong.md on the right (the
guide block whose PDF-page range contains the current page; deepest match
wins). Pages sharing a section repeat that section's notes, so wherever you
are, the relevant notes are beside you.

Usage:
  python barlow/build/_build_readalong_pdf.py            # vector left pane
  python barlow/build/_build_readalong_pdf.py --raster   # rasterized left pane (smaller file)

Output: barlow/docs/BARLOW-DISSERTATION-2026_sidebyside.pdf (gitignored; the
source dissertation PDF is 413 MB and copyrighted -- keep both local-only).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "BARLOW-DISSERTATION-2026.pdf"
GUIDE = ROOT / "docs" / "barlow_dissertation_readalong.md"
OUT = ROOT / "docs" / "BARLOW-DISSERTATION-2026_sidebyside.pdf"

NOTES_W = 560.0  # right-pane width (pt)
MARGIN = 14.0
RANGE_RE = re.compile(r"\(PDF pp?\.\s*~?(\d+)\s*[–\-]\s*~?(\d+)\)|\(pp?\.\s*~?(\d+)\s*[–\-]\s*~?(\d+)\)|\(pp?\.\s*~?(\d+)\)")


def md_to_html(md: str) -> str:
    """Minimal markdown -> HTML for insert_htmlbox (bold, bullets, paragraphs)."""
    # Join wrapped paragraph lines so inline **bold** spanning a line break converts.
    joined, buf = [], []
    for line in md.splitlines() + [""]:
        s = line.strip()
        plain = s and not re.match(r"^(#{1,4}\s|[-*]\s|\||---$)", s)
        if plain:
            buf.append(s)
        else:
            if buf:
                joined.append(" ".join(buf)); buf = []
            joined.append(line)
    md = "\n".join(joined)
    out, in_ul = [], False
    for line in md.splitlines():
        s = line.strip()
        if not s:
            if in_ul:
                out.append("</ul>"); in_ul = False
            continue
        hm = re.match(r"^(#{1,4})\s+(.*)$", s)
        if hm:
            if in_ul:
                out.append("</ul>"); in_ul = False
            lvl = min(len(hm.group(1)), 2)
            out.append(f"<h{lvl}>{hm.group(2)}</h{lvl}>")
            continue
        if s == "---":
            continue
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
        s = re.sub(r"`(.+?)`", r"<tt>\1</tt>", s)
        if s.startswith(("- ", "* ")):
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{s[2:]}</li>")
        elif s.startswith("|"):  # tables -> plain rows
            cells = [c.strip() for c in s.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            out.append("<p><tt>" + " · ".join(c for c in cells if c) + "</tt></p>")
        else:
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<p>{s}</p>")
    if in_ul:
        out.append("</ul>")
    return "\n".join(out)


def parse_guide() -> tuple[list[dict], str]:
    """Return (blocks with page ranges, front-matter markdown before first ##)."""
    text = GUIDE.read_text(encoding="utf-8")
    lines = text.splitlines()
    blocks, front, cur = [], [], None
    for line in lines:
        m = re.match(r"^(#{2,4})\s+(.*)$", line)
        rm = RANGE_RE.search(m.group(2)) if m else None
        if m and rm:
            title = m.group(2).strip()
            if cur:
                blocks.append(cur)
            nums = [g for g in rm.groups() if g]
            a, b = (int(nums[0]), int(nums[-1])) if len(nums) > 1 else (int(nums[0]),) * 2
            cur = {"level": len(m.group(1)), "title": title, "a": a, "b": b, "body": []}
            continue
        # unranged headings and ordinary lines: front matter until the first
        # ranged heading, body of the current block afterwards
        if cur is None:
            front.append(line)
        else:
            cur["body"].append(line)
    if cur:
        blocks.append(cur)
    # fill chapter context: for each ranged block remember nearest level-2 ancestor title
    chap = None
    for b in blocks:
        if b["level"] == 2:
            chap = b["title"]
        b["chapter"] = chap
    blocks = [b for b in blocks if b["a"] is not None]
    return blocks, "\n".join(front)


def block_for_page(blocks: list[dict], page: int) -> dict | None:
    """Deepest (narrowest-range, then highest level) block containing page."""
    hits = [b for b in blocks if b["a"] <= page <= b["b"]]
    if not hits:
        return None
    return min(hits, key=lambda b: (b["b"] - b["a"], -b["level"]))


CSS = """
* { font-family: sans-serif; }
body { font-size: 10.5px; line-height: 1.35; }
h1 { font-size: 15px; margin: 0 0 4px 0; }
h2 { font-size: 12px; color: #444; margin: 0 0 10px 0; font-weight: normal; }
p { margin: 0 0 6px 0; }
ul { margin: 0 0 6px 16px; padding: 0; }
li { margin: 0 0 3px 0; }
tt { font-size: 9.5px; }
"""


def main() -> int:
    raster = "--raster" in sys.argv
    global OUT
    if raster:
        OUT = OUT.with_name(OUT.stem + "_compact.pdf")
    blocks, front = parse_guide()
    src = fitz.open(SRC)
    out = fitz.open()

    # Cover page: guide front matter (how to use + big picture) full width.
    r0 = src[0].rect
    sheet_w = r0.width + NOTES_W
    cover = out.new_page(width=sheet_w, height=r0.height)
    cx = (sheet_w - 720) / 2
    cover.insert_htmlbox(fitz.Rect(cx, MARGIN * 2, cx + 720, r0.height - MARGIN * 2),
                         md_to_html(front), css=CSS, scale_low=0)

    for i in range(src.page_count):
        pno = i + 1
        srect = src[i].rect
        page = out.new_page(width=srect.width + NOTES_W, height=srect.height)
        left = fitz.Rect(0, 0, srect.width, srect.height)
        if raster:
            pix = src[i].get_pixmap(dpi=170, colorspace=fitz.csRGB)
            page.insert_image(left, stream=pix.tobytes("jpeg", jpg_quality=82))
        else:
            page.show_pdf_page(left, src, i)
        page.draw_line(fitz.Point(srect.width, 0), fitz.Point(srect.width, srect.height),
                       color=(0.6, 0.6, 0.6), width=0.7)

        b = block_for_page(blocks, pno)
        rect = fitz.Rect(srect.width + MARGIN, MARGIN,
                         srect.width + NOTES_W - MARGIN, srect.height - MARGIN)
        if b:
            hdr = f"<h1>{b['title']}</h1>"
            if b["chapter"] and b["chapter"] != b["title"]:
                hdr = f"<h2>{b['chapter']}</h2>" + hdr
            hdr += f"<h2>you are on PDF page {pno} (section spans pp. {b['a']}–{b['b']})</h2>"
            html = hdr + md_to_html("\n".join(b["body"]))
        else:
            html = f"<h1>PDF page {pno}</h1><p>No guide notes for this page (references/appendix lookup material).</p>"
        page.insert_htmlbox(rect, html, css=CSS, scale_low=0)

        if pno % 40 == 0:
            print(f"  {pno}/{src.page_count}")

    out.save(OUT, deflate=True, garbage=3)
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.0f} MB, {out.page_count} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
