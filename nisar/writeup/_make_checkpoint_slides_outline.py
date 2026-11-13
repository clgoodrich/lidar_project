"""Outline version of the NISAR methods checkpoint deck for tile 9t.

Same layout and the same two figures as nisar_checkpoint_slides_methods_9t.pptx, but every text slot holds a
bracketed stand-in such as [sources here]. Use it as a blank to fill in. The template checkpoint-template.pptx
and the methods deck are never edited.

Input   nisar/writeup/checkpoint-template.pptx, nisar/writeup/figures/nisar_site_map_9t.png,
        nisar/writeup/figures/nisar_scene_calendar_9t.png
Output  nisar/writeup/nisar_checkpoint_slides_outline_9t.pptx

Run
    python nisar/writeup/_make_checkpoint_slides_outline.py
"""
from __future__ import annotations

from pptx import Presentation

from _make_checkpoint_slides_methods import HERE, SRC, drop_eg, header, notes, picture_in, set_para, shape

OUT = HERE / "nisar_checkpoint_slides_outline_9t.pptx"


def slide1(s) -> None:
    header(s, 1, "[Research question in one sentence]")
    picture_in(s, "Rectangle 7", HERE / "figures/nisar_site_map_9t.png")
    tf = shape(s, "TextBox 8").text_frame
    drop_eg(tf)
    ps = tf.paragraphs
    set_para(ps[1], "[Study site: where, how big, what is there]")
    set_para(ps[3], "[Expected signal: what should change at pads and pits]")
    set_para(ps[5], "[Why radar can see it: the physics in one or two lines]")
    notes(s, "[Speaker notes for slide 1, about 1 minute 40 seconds]")


def slide2(s) -> None:
    header(s, 2, "[Data headline: sensor, number of dates, time span, coverage]")
    rows = ["[Sensor and band, and why]",
            "[Product level and grid spacing]",
            "[Tracks, look direction and incidence angles]",
            "[Date range, repeat interval, number of dates, exclusions]",
            "[Sources here: archive and access method]",
            "[Reference data: lidar maps, well records, other sensors]"]
    tbl = shape(s, "Table 7").table
    for i, t in enumerate(rows):
        set_para(tbl.cell(i, 1).text_frame.paragraphs[0], t)
    picture_in(s, "Rectangle 8", HERE / "figures/nisar_scene_calendar_9t.png",
               caption="[Figure caption: what the calendar shows and why the gap exists]")
    notes(s, "[Speaker notes for slide 2, about 1 minute 40 seconds]")


def slide3(s) -> None:
    header(s, 3, "[Method headline: the test and the pass mark]")
    for k in range(5):
        ps = shape(s, f"Rounded Rectangle {7 + k}").text_frame.paragraphs
        set_para(ps[0], f"{k + 1}   [Step {k + 1} name]")
        set_para(ps[1], "Tool: [tool]     Key choice: [key choice]")
    tbl = shape(s, "Table 13").table
    for i in range(1, 4):
        for j, t in enumerate(["[Risk %d]", "[How you would notice %d]", "[Fix %d]"]):
            tf = tbl.cell(i, j).text_frame
            drop_eg(tf)
            set_para(tf.paragraphs[0], t % i)
    notes(s, "[Speaker notes for slide 3, about 1 minute 40 seconds]")


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
