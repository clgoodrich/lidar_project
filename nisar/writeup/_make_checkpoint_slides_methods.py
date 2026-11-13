"""Methods version of the CIVE 6359 checkpoint deck for the NISAR work on tile 9t.

Copy of _make_checkpoint_slides.py (2026-11-09). It describes the method only and assumes no result has
been seen. The design follows the 2026-11-09 review: a frozen input manifest, fixed spatial folds, radar
scored on the lidar detector's own candidates, and recall at a fixed inspection budget on a reserved area
with independent labels. The template checkpoint-template.pptx and the original deck are never edited.

Input   nisar/writeup/checkpoint-template.pptx, nisar/writeup/figures/nisar_site_map_9t.png,
        nisar/writeup/figures/nisar_scene_calendar_9t.png
Output  nisar/writeup/nisar_checkpoint_slides_methods_9t.pptx

Run
    python nisar/writeup/_make_checkpoint_slides_methods.py
"""
from __future__ import annotations

import copy
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
SRC = HERE / "checkpoint-template.pptx"
OUT = HERE / "nisar_checkpoint_slides_methods_9t.pptx"
NAME = "Colton Goodrich"
INK = RGBColor(0x22, 0x22, 0x22)


def set_para(p, text: str, color=INK) -> None:
    """Replace a paragraph's text and keep the first run's formatting."""
    runs = p.runs
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    runs[0].text = text
    if color is not None:
        runs[0].font.color.rgb = color


def drop_para(p) -> None:
    p._p.getparent().remove(p._p)


def drop_eg(tf) -> None:
    for p in list(tf.paragraphs):
        if p.text.strip().startswith("e.g."):
            drop_para(p)


def shape(slide, name):
    return next(s for s in slide.shapes if s.name == name)


def header(slide, n: int, headline: str) -> None:
    set_para(shape(slide, "TextBox 3").text_frame.paragraphs[0], f"{NAME} · {n} of 3", color=None)
    tf = shape(slide, "TextBox 5").text_frame
    set_para(tf.paragraphs[0], headline)
    drop_eg(tf)


def picture_in(slide, rect_name: str, img: Path, caption: str | None = None) -> None:
    """Put an image where a placeholder rectangle sits, fitted inside it, then remove the rectangle."""
    from PIL import Image
    r = shape(slide, rect_name)
    w, h = Image.open(img).size
    cap_h = Inches(0.5) if caption else 0
    box_w, box_h = r.width, r.height - cap_h
    scale = min(box_w / w, box_h / h)
    pw, ph = int(w * scale), int(h * scale)
    left, top = r.left + (box_w - pw) // 2, r.top
    pic = slide.shapes.add_picture(str(img), left, top, pw, ph)
    pic.name = rect_name.replace("Rectangle", "Picture")
    if caption:
        tb = slide.shapes.add_textbox(r.left, top + ph + Inches(0.08), r.width, Inches(0.45))
        tb.name = "Caption"
        tb.text_frame.word_wrap = True
        run = tb.text_frame.paragraphs[0].add_run()
        run.text = caption
        run.font.size, run.font.italic, run.font.name = Pt(11), True, "Calibri"
        run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    r._element.getparent().remove(r._element)


def notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def slide1(s) -> None:
    header(s, 1, "Can NISAR L-band radar help find oil-well pads and pits under forest beyond what lidar finds?")
    picture_in(s, "Rectangle 7", HERE / "figures/nisar_site_map_9t.png")
    tf = shape(s, "TextBox 8").text_frame
    drop_eg(tf)
    ps = tf.paragraphs
    set_para(ps[1], "Tile 9t in Venango County, PA. 20 km² of hardwood forest with 650 mapped well pads and "
                    "506 pits from 150 years of oil drilling.")
    set_para(ps[3], "Any rise or fall in HH or HV backscatter, or a drop in coherence, at pads and pits compared "
                    "with nearby forest. Size and sign are not assumed. Speckle is large on one date, so the signal is "
                    "measured over many repeat dates.")
    set_para(ps[5], "The 24 cm L-band wave passes through much of the canopy. Clearings, water and metal change "
                    "the echo, and 12-day repeats let speckle be averaged out.")
    notes(s, "About 1 minute 40 seconds. Read the question. The site is tile 9t in Venango County, 4.5 by 4.5 km of "
             "forest with 650 pads and 506 pits mapped from lidar. I am not assuming a size or a sign. I am looking "
             "for any rise or fall in backscatter, or a drop in coherence, at pads and pits compared with matched "
             "forest nearby, measured over many dates rather than one. "
             "L-band is the band most likely to reach the ground through leaves. The practical question is narrower. Does radar raise the number of real pads a field crew finds for the same number of site visits?")


def slide2(s) -> None:
    header(s, 2, "37 NISAR L-band dates on three tracks, October 2025 to October 2026, cover the whole tile.")
    rows = ["NISAR L-band (24 cm), HH and HV. The longest wavelength in orbit, so the best chance under canopy.",
            "Level-2 GSLC on a 5 m grid (amplitude and phase), plus RSLC to geocode again on lidar heights.",
            "Tracks 90 and 162 ascending, looking west. Track 26 descending, looking east. Incidence 39°, 47° "
            "and 41°.",
            "2025-10-28 to 2026-10-14. 12-day repeat. 37 dates (11 beta, 26 provisional). 35 pass the coverage "
            "screen. Nothing released for February to May.",
            "NASA Earthdata and the Alaska Satellite Facility (search.asf.alaska.edu). Read in 9 MB windows by "
            "HTTP range requests.",
            "Lidar-mapped pads and pits (2019, 1 m), PA DEP well records, Sentinel-1 C-band and Sentinel-2."]
    tbl = shape(s, "Table 7").table
    for i, t in enumerate(rows):
        set_para(tbl.cell(i, 1).text_frame.paragraphs[0], t)
    picture_in(s, "Rectangle 8", HERE / "figures/nisar_scene_calendar_9t.png",
               caption="NISAR dates over tile 9t by track. The gap from February to May is release timing, "
                       "not missed collection.")
    notes(s, "About 1 minute 40 seconds. L-band because it is the band that best sees under leaves, and NISAR is "
             "the first free L-band mission with this revisit. I use the GSLC product, and the raw RSLC so I can "
             "place the image on lidar heights myself. Three tracks cover the tile, two ascending and one "
             "descending, at 39 to 47 degrees incidence. 37 dates delivered from October 2025 to October 2026. Every date, its processing level and any exclusion go into one input manifest that every step reads. I "
             "check everything against our lidar maps of pads and pits, the state well records, and Sentinel-1 and "
             "Sentinel-2.")


def slide3(s) -> None:
    header(s, 3, "Verified pads found at a fixed inspection budget, lidar alone against lidar plus radar, "
                 "answer the question. The bar is +0.05 recall.")
    steps = [("1   Build one input manifest for every date and layer",
              "Tool: Python, h5py     Key choice: dates, masks, bands and exclusions listed; runs stop on a mismatch"),
             ("2   Geocode again on lidar heights",
              "Tool: own geocoder     Key choice: lidar DEM in place of Copernicus DEM, offsets fit on reference targets"),
             ("3   Stack dates into a small fixed radar feature set",
              "Tool: numpy, rasterio     Key choice: HH and HV level, local contrast and texture only"),
             ("4   Score the lidar detector's candidates with and without radar",
              "Tool: scikit-learn     Key choice: same candidates and spatial folds, fixed once"),
             ("5   Recall at a fixed budget on a reserved area",
              "Tool: cluster bootstrap     Key choice: budget, bar and labels fixed before scoring")]
    for k, (a, b) in enumerate(steps):
        ps = shape(s, f"Rounded Rectangle {7 + k}").text_frame.paragraphs
        set_para(ps[0], a)
        set_para(ps[1], b)
    risks = [("Image placed off the ground, because the Copernicus DEM sits on the canopy",
              "Lidar simulation or surveyed reflectors sit offset from the image",
              "Geocode on lidar heights. Check on reflectors not used to fit"),
             ("Score learns location, not the target",
              "Map x and y alone score as high as the radar",
              "Fixed spatial folds. Coordinate-only and placebo controls"),
             ("Labels favour what lidar already sees",
              "Radar can only confirm features lidar drew",
              "Independent labels on a reserved area, plus a sample outside the candidates")]
    tbl = shape(s, "Table 13").table
    for i, row in enumerate(risks, start=1):
        for j, t in enumerate(row):
            tf = tbl.cell(i, j).text_frame
            drop_eg(tf)
            set_para(tf.paragraphs[0], t)
    notes(s, "About 1 minute 40 seconds. Five steps. First, one input manifest. It lists every date, mask, band and "
             "exclusion, and every later step reads it, so no step can quietly use a different set of files. "
             "Second, geocode again on lidar heights, because NASA's elevation model sits on the treetops and can "
             "shift the image. The offsets are fit on reference targets and checked on others. Third, a small "
             "fixed set of radar layers, chosen before any scoring. Fourth, the lidar detector proposes candidate "
             "sites, and the same candidates and the same spatial folds are scored with and without radar. Fifth, "
             "on an area held back from all choices, count how many verified pads each version finds for the "
             "same number of site visits. The budget, the +0.05 recall bar and the labels are fixed first. Three "
             "risks. Misplacement, checked on reflectors not used for fitting. A score that learns location, "
             "checked with map coordinates alone and a placebo. Labels that only contain what lidar can see, "
             "handled with independent labels and a sample outside the candidates.")


def main() -> None:
    prs = Presentation(str(SRC))
    s1, s2, s3 = prs.slides
    slide1(s1)
    slide2(s2)
    slide3(s3)
    prs.save(str(OUT))
    print(OUT)


if __name__ == "__main__":
    main()
