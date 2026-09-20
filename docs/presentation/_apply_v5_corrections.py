"""Apply the 2026-09-20 review corrections to the deck. v4 -> v5.

v4 is the user's file and is never modified. This writes a new v5 beside it.

WHAT IT CHANGES
---------------
1. ONE BACKGROUND EVERYWHERE. v4 is visibly two decks stitched together: 22
   slides carry an explicit dark navy `p:bg` (#1A1A2E) and 46 inherit the light
   layout. Every generated figure is light paper (#f7f8f6), so light wins --
   dark slides with light figures read as white rectangles pasted onto navy.
   The `p:bg` override is removed from those 22.

   That alone would leave white text on a white slide, because the colour is not
   on the runs. It sits in `a:pPr/a:defRPr/a:solidFill/a:srgbClr`, inherited by
   every run in the paragraph. So each light ink colour is remapped:

       FFFFFF -> 141A1F   body and title ink, matching the figures
       CCCCCC -> 545C63   secondary text
       AAAAAA -> 6B7278   muted text
       0096C7    kept     already the title colour on all 46 light slides
       FF5722    kept     accent, and orange/cyan is a safe pair
       777777    kept     readable on white as is

   Contrast on white: 545C63 about 7:1, 6B7278 about 4.8:1, 0096C7 about 3.1:1
   but only ever used at title size. No red/green pair exists anywhere in the
   deck, so the CLAUDE.md colourblind rule is not engaged by this remap.

2. SLIDE 8, pipeline. New figure: the in-figure title, the subtitle, the
   derivative list, the annotation-layer list and the SMRF footnote are gone.
   Three rows of boxes.

3. SLIDE 9, Data QA. Split in two. The scan-angle diagram stays on slide 9; the
   stat cards move to a new slide 10. The old title, the three-line paragraph
   and the bottom footnote are gone from both.

The project name does not appear on any slide this script touches.

Run:
    python docs/presentation/_apply_v5_corrections.py
    python docs/presentation/_apply_v5_corrections.py --dry-run
"""
from __future__ import annotations

import argparse
import copy
import re
import shutil
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[2]
PRES = ROOT / "docs/presentation"
SRC = PRES / "WellSight_Presentation v4.pptx"
DST = PRES / "WellSight_Presentation v5.pptx"
FIG = PRES / "figures_30to45min"

NSP = "{http://schemas.openxmlformats.org/presentationml/2006/main}"

#: Fills and text need OPPOSITE treatment, so they cannot share one map. A
#: blanket swap turns the appendix tables into dark text on dark navy rows.
#:
#: FILLS (a:tcPr, p:spPr, a:ln): dark row banding becomes light row banding.
FILL_MAP = {
    "16162A": "FFFFFF",   # table row, dark
    "22223A": "F2F3F6",   # table row, dark alternate -> light banding
    "18182A": "FFFFFF",   # table row, dark variant
    "2A1A0A": "FDF3E6",   # amber highlight row on dark -> amber tint on light
}
#: Fills that STAY dark. Any text sitting on one of these must stay white.
DARK_FILL_KEEP = {"0096C7", "00648C"}

#: TEXT (a:rPr, a:defRPr, a:endParaRPr): light ink becomes dark ink.
TEXT_MAP = {"FFFFFF": "141A1F", "CCCCCC": "545C63", "AAAAAA": "6B7278"}

#: Text colours already dark enough to leave alone: 333333, 0096C7, FF5722,
#: 777777. They sit on light-filled cells in v4 and read fine on white.

_FILL_CTX = {"tcPr", "spPr", "ln", "gridCol"}
_TEXT_CTX = {"rPr", "defRPr", "endParaRPr"}

PIPELINE_PNG = FIG / "4_model_building/pipeline_diagram_9t.png"
QA_DIAGRAM_PNG = FIG / "1_data_qa/data_qa_scan_angle_cut_diagram_9t.png"
QA_NUMBERS_PNG = FIG / "1_data_qa/data_qa_scan_angle_cut_numbers_9t.png"

SLIDE_W, SLIDE_H = 13.3333, 7.5


#: One background for the whole deck, matching the figures' own paper so an
#: embedded PNG blends into the slide instead of sitting on a visible panel.
#: Every figure builder in figures_30to45min uses this exact value.
PAPER = "F7F8F6"

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def set_uniform_background(slide) -> bool:
    """Force this slide's background to PAPER. Returns True if it was dark."""
    from lxml import etree
    csld = slide._element.find(NSP + "cSld")
    old = csld.find(NSP + "bg")
    was_dark = False
    if old is not None:
        vals = [c.get("val", "").upper() for c in old.iter()
                if c.tag.endswith("}srgbClr")]
        was_dark = any(v == "1A1A2E" for v in vals)
        csld.remove(old)
    bg = etree.SubElement(csld, NSP + "bg")
    pr = etree.SubElement(bg, NSP + "bgPr")
    fill = etree.SubElement(pr, _A + "solidFill")
    etree.SubElement(fill, _A + "srgbClr").set("val", PAPER)
    etree.SubElement(pr, _A + "effectLst")
    csld.insert(0, bg)
    return was_dark


def _context(el):
    """Which kind of colour is this: a fill, some text, or neither?"""
    q = el.getparent()
    while q is not None:
        t = q.tag.split("}")[-1]
        if t in _FILL_CTX or t in _TEXT_CTX:
            return t
        q = q.getparent()
    return ""


def _cell_stays_dark(el) -> bool:
    """True if this text sits in a table cell whose fill remains dark."""
    q = el.getparent()
    while q is not None:
        if q.tag.endswith("}tc"):
            for c in q.iter():
                if c.tag.endswith("}srgbClr") and _context(c) in _FILL_CTX:
                    if (c.get("val") or "").upper() in DARK_FILL_KEEP:
                        return True
            return False
        q = q.getparent()
    return False


def recolour(slide) -> tuple[int, int, int]:
    """Dark deck -> light deck. Returns (fills, text, kept-white) counts."""
    nf = nt = nk = 0
    for el in slide._element.iter():
        if not el.tag.endswith("}srgbClr"):
            continue
        val = (el.get("val") or "").upper()
        ctx = _context(el)
        if ctx in _FILL_CTX:
            if val in FILL_MAP:
                el.set("val", FILL_MAP[val])
                nf += 1
        elif ctx in _TEXT_CTX and val in TEXT_MAP:
            if _cell_stays_dark(el):
                nk += 1          # white text on a header that is still dark
                continue
            el.set("val", TEXT_MAP[val])
            nt += 1
    return nf, nt, nk


def fit(png_w_in, png_h_in, box):
    """Centre an image inside a box, preserving aspect. box = (l, t, w, h)."""
    bl, bt, bw, bh = box
    ar = png_w_in / png_h_in
    w = bw
    h = w / ar
    if h > bh:
        h = bh
        w = h * ar
    return bl + (bw - w) / 2.0, bt + (bh - h) / 2.0, w, h


def replace_picture(slide, png: Path, box):
    """Swap the slide's single picture for `png`, centred in `box`."""
    from PIL import Image
    with Image.open(png) as im:
        pw, ph = im.size
        dpi = im.info.get("dpi", (150, 150))[0] or 150
    pics = [sh for sh in slide.shapes if sh.__class__.__name__ == "Picture"]
    for sh in pics:
        sh._element.getparent().remove(sh._element)
    l, t, w, h = fit(pw / dpi, ph / dpi, box)
    slide.shapes.add_picture(str(png), Inches(l), Inches(t),
                             Inches(w), Inches(h))
    return l, t, w, h


def clone_slide_after(prs, src_slide, after_index):
    """Duplicate a slide and move the copy to sit right after `after_index`."""
    blank = src_slide.slide_layout
    new = prs.slides.add_slide(blank)
    for shp in list(new.shapes):
        shp._element.getparent().remove(shp._element)
    for shp in src_slide.shapes:
        new.shapes._spTree.append(copy.deepcopy(shp._element))
    csld = src_slide._element.find(NSP + "cSld")
    bg = csld.find(NSP + "bg") if csld is not None else None
    if bg is not None:
        new._element.find(NSP + "cSld").insert(0, copy.deepcopy(bg))
    # move it into position: add_slide appends, so re-seat the sldId
    lst = prs.slides._sldIdLst
    ids = list(lst)
    lst.remove(ids[-1])
    lst.insert(after_index + 1, ids[-1])
    return new


def set_title(slide, text):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            para = sh.text_frame.paragraphs[0]
            if para.runs:
                para.runs[0].text = text
                for extra in para.runs[1:]:
                    extra.text = ""
            return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    for p in (PIPELINE_PNG, QA_DIAGRAM_PNG, QA_NUMBERS_PNG):
        if not p.exists():
            print(f"MISSING figure: {p}")
            return 1
    if not a.dry_run:
        shutil.copy2(SRC, DST)
    prs = Presentation(str(DST if not a.dry_run else SRC))
    print(f"source {SRC.name}: {len(prs.slides)} slides")

    # ---- 3: split slide 9 BEFORE renumbering anything else ----------
    s9 = prs.slides[8]
    box = (0.40, 1.35, SLIDE_W - 0.80, SLIDE_H - 1.35 - 0.35)
    print(f"\nslide 9  diagram   {replace_picture(s9, QA_DIAGRAM_PNG, box)}")
    s10 = clone_slide_after(prs, s9, 8)
    set_title(s10, "Data QA – What the Cut Cost")
    print(f"slide 10 numbers   {replace_picture(s10, QA_NUMBERS_PNG, box)}"
          "   (new slide)")

    # ---- 2: slide 8 pipeline ----------------------------------------
    s8 = prs.slides[7]
    box8 = (0.35, 1.05, SLIDE_W - 0.70, SLIDE_H - 1.05 - 0.30)
    print(f"slide 8  pipeline  {replace_picture(s8, PIPELINE_PNG, box8)}")

    # ---- 1: one background ------------------------------------------
    stripped = f_n = t_n = k_n = 0
    for s in prs.slides:
        if set_uniform_background(s):
            stripped += 1
            a1, a2, a3 = recolour(s)
            f_n += a1; t_n += a2; k_n += a3
    print(f"\nbackgrounds: every slide set to #{PAPER}; "
          f"{stripped} were dark and had their ink relit")
    print(f"  fills relit      {f_n}")
    print(f"  text darkened    {t_n}")
    print(f"  left white       {k_n}  (on fills that stay dark)")

    import re as _re
    from lxml import etree as _et
    bad = []
    for i, s in enumerate(prs.slides, 1):
        bg = s._element.find(".//" + NSP + "bg")
        if bg is None:
            bad.append((i, "no background"))
            continue
        vals = _re.findall(r'srgbClr val="([0-9A-Fa-f]{6})"',
                           _et.tostring(bg).decode())
        if vals != [PAPER]:
            bad.append((i, str(vals)))
    print(f"slides not on #{PAPER}: {len(bad)}  (expect 0)"
          + ("" if not bad else f"  {bad[:8]}"))

    if a.dry_run:
        print("\n--dry-run, nothing written")
        return 0
    prs.save(str(DST))
    print(f"\n{len(prs.slides)} slides  ->  {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
