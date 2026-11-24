"""Updated three-slide checkpoint deck (CIVE 6359 template) for the NISAR design on tile 9t. Made 2026-11-23.

Same template and layout as the 2026-11-09 methods deck (_make_checkpoint_slides_methods.py, kept unchanged),
rewritten for the design as it now stands:
  * question: a repeatable marker at known sites, not prediction (decided 2026-11-15)
  * data: NISAR dates from 2026-06-01 only (32 dates to 2026-11-16), tile 9t only
  * steps: lidar placement, per-track contrasts against ring and control spots, persistent-scatterer
    screen with sourced thresholds, coherence and motion; three risks, each with how it is noticed
Setup only. No results are stated.

Input   nisar/writeup/checkpoint-template.pptx, nisar/writeup/figures/nisar_site_map_9t.png,
        nisar/docs/figures/nisar_dates_postjune.png
Output  nisar/writeup/nisar_checkpoint_slides_design_9t.pptx

Run
    python nisar/writeup/_make_checkpoint_slides_design.py
"""
from __future__ import annotations

from pptx import Presentation

from _make_checkpoint_slides_methods import HERE, SRC, drop_eg, header, notes, picture_in, set_para, shape

OUT = HERE / "nisar_checkpoint_slides_design_9t.pptx"
DATES_FIG = HERE.parent / "docs" / "figures" / "nisar_dates_postjune.png"


def slide1(s) -> None:
    header(s, 1, "At known well sites on tile 9t, does NISAR show a repeatable contrast at pads, pits or steel "
                 "that differs from nearby ground with no well?")
    picture_in(s, "Rectangle 7", HERE / "figures/nisar_site_map_9t.png")
    tf = shape(s, "TextBox 8").text_frame
    drop_eg(tf)
    ps = tf.paragraphs
    set_para(ps[1], "Tile 9t, Venango County, PA. 4.5 km square of hardwood forest. 506 pits and 650 pads mapped "
                    "from lidar (645 pads usable for tests), 1,068 DEP wells.")
    set_para(ps[3], "Pits and pads 0.1 to 0.5 dB against their surroundings. Steel 6.5 to 7.2 dB above background. "
                    "A coherence drop past the 1% tail of control spots. Motion over 12 mm in 12 days.")
    set_para(ps[5], "A 24 cm L-band wave reaches the ground under leaves. Pits and pads change slope and roughness, "
                    "steel gives a steady echo, and work on a pad breaks coherence.")
    notes(s, "About 1 minute 40 seconds. The question is narrow on purpose. At sites we already know, does the radar "
             "show anything repeatable? A marker that does not show at a known well cannot find an unknown one, so "
             "prediction waits on this answer. A well pad is the cleared, graded ground around a well. A pit is the "
             "dug hollow beside it. The expected sizes set the design. A pit or pad contrast of a few tenths of a dB "
             "is far below one pixel's spread of about 2.3 dB, so hundreds of sites must be pooled.")


def slide2(s) -> None:
    header(s, 2, "32 NISAR L-band dates on three tracks, June to November 2026, cover all of tile 9t.")
    rows = ["NISAR L-band (24 cm), HH and HV. The longest wavelength in orbit, so the best reach under canopy.",
            "Level-2 GSLC on a 5 m grid (amplitude and phase), plus Level-1 RSLC to place each image on lidar "
            "heights.",
            "Track 26 descending, looking east, 41°. Tracks 90 and 162 ascending, looking west, 39° and 47°. "
            "Every track over 9t.",
            "2026-06-20 to 2026-11-16. 12-day repeat. 32 dates (8, 12, 12). Beta dates before June 2026 excluded: "
            "older calibration.",
            "NASA ASF DAAC via ASF Vertex (search.asf.alaska.edu). Read in small windows by HTTP range requests.",
            "USGS 3DEP lidar PA_WesternPA_2019_D20 (pads and pits), PA DEP well records (April 2026)."]
    tbl = shape(s, "Table 7").table
    for i, t in enumerate(rows):
        set_para(tbl.cell(i, 1).text_frame.paragraphs[0], t)
    picture_in(s, "Rectangle 8", DATES_FIG,
               caption="Dates used per track on 9t. Summer June to September, fall 21 October to 30 November, "
                       "both fixed before any test.")
    notes(s, "About 1 minute 40 seconds. L-band because the targets sit under deciduous canopy. The product keeps "
             "phase, so one download gives backscatter, coherence and interferograms. The tracks are set by the "
             "satellite. Both look directions matter, because a slope bright from one side is dark from the other. "
             "Only dates from June 2026 are used. The earlier beta images came from older software, and every fall "
             "date was beta, so season and processing could not be told apart. New dates moved to a standard "
             "collection on 23 October, and the download searches both.")


def slide3(s) -> None:
    header(s, 3, "Each site is measured against its ring and against control spots, per track, on images placed "
                 "on the lidar ground.")
    steps = [("1   Fetch windows over 9t and place them on the lidar ground",
              "Tool: h5py, own geocoder     Key choice: echo at lidar ground plus 10% of canopy height"),
             ("2   Tie dates and tracks to the lidar",
              "Tool: lidar backscatter simulation     Key choice: 2.5 m gate per block"),
             ("3   Feature minus ring, minus five control spots",
              "Tool: numpy, geopandas     Key choice: ring 10-30 m pits, 20-60 m pads; power averaged before dB"),
             ("4   Persistent-scatterer screen for steel",
              "Tool: numpy, scipy     Key choice: dispersion < 0.25, 3 SD above 250 m median, 6 m radius"),
             ("5   Coherence and motion, then pool sites",
              "Tool: interferograms, scipy     Key choice: 1% control-spot tail; Wilcoxon on the per-site excess")]
    for k, (a, b) in enumerate(steps):
        ps = shape(s, f"Rounded Rectangle {7 + k}").text_frame.paragraphs
        set_para(ps[0], a)
        set_para(ps[1], b)
    risks = [("Too few dates: 8 to 12 per track, where the steadiness rule assumes about 30",
              "Steady pixels flood open fields, past the 3 SD expectation",
              "Require two tracks, raise the cutoff, add dates as released"),
             ("Decorrelation under deciduous canopy and wet snow",
              "Coherence under 0.45 over most of a track",
              "Short pairs, coherence mask, lean on backscatter"),
             ("Signal smaller than the noise",
              "Intervals span zero, or shift with the control-spot draw",
              "40 control spots per site, matched on canopy and slope")]
    tbl = shape(s, "Table 13").table
    for i, row in enumerate(risks, start=1):
        for j, t in enumerate(row):
            tf = tbl.cell(i, j).text_frame
            drop_eg(tf)
            set_para(tf.paragraphs[0], t)
    notes(s, "About 1 minute 40 seconds. NASA's images sat 8 to 12 m off the lidar, which is two pixels at a pit, so "
             "every image is placed on the lidar ground first. The ring cancels slope, canopy and viewing angle. "
             "Control spots, copies of the outline 150 to 600 m away, show what chance gives. The steadiness cutoff "
             "is from Ferretti, Prati and Rocca 2001. The brightness rule is 3 robust standard deviations of the "
             "tile itself. The 6 m radius is half a pixel diagonal plus placement error. Tracks are measured apart "
             "and combined per site. Of the risks, too few dates is the one most likely to bite.")


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
