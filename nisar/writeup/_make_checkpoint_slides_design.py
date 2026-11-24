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
    header(s, 1, "Which of the 506 lidar-identified pits on tile 9t hold a NISAR persistent scatterer, a pixel "
                 "whose echo stays strong and steady over time?")
    picture_in(s, "Rectangle 7", HERE / "figures/nisar_site_map_9t.png")
    tf = shape(s, "TextBox 8").text_frame
    drop_eg(tf)
    ps = tf.paragraphs
    set_para(ps[1], "Tile 9t, Venango County, PA. 4.5 km square of hardwood forest. 506 pits and 650 pads mapped "
                    "from lidar (645 pads usable for tests), 1,068 DEP wells.")
    set_para(ps[3], "A pixel 6.5 to 7.2 dB brighter than the ground within 250 m whose amplitude varies by less than "
                    "25% of its mean over dates, inside or within 6 m of a pit outline.")
    set_para(ps[5], "Casing, pumpjacks and tanks are steel, a strong and steady reflector. Forest echoes change "
                    "between passes. A 24 cm L-band wave passes through leaves.")
    notes(s, "About 1 minute 40 seconds. A persistent scatterer is a pixel whose echo stays strong and steady over "
             "many dates, usually a hard object such as steel. The question is which of our lidar-identified pits hold "
             "one. Steadiness under 0.25 is the cutoff of Ferretti, Prati and Rocca 2001. The brightness rule is 3 robust "
             "standard deviations of the tile's own brightness, about 2.3 dB each, so 6.5 to 7.2 dB.")


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
             ("3   Amplitude statistics per track over all post-June dates",
              "Tool: numpy     Key choice: HH, mean power and amplitude dispersion (SD over mean)"),
             ("4   Persistent-scatterer screen for steel",
              "Tool: numpy, scipy     Key choice: dispersion < 0.25, 3 SD above 250 m median, 6 m radius"),
             ("5   Compare wells with control spots",
              "Tool: scipy     Key choice: Fisher's exact test by DEP status; never-drilled permits as negative control")]
    for k, (a, b) in enumerate(steps):
        ps = shape(s, f"Rounded Rectangle {7 + k}").text_frame.paragraphs
        set_para(ps[0], a)
        set_para(ps[1], b)
    risks = [("Images not on the lidar ground: NASA's elevation model sits in the canopy, so pixels shift 8 to 12 m",
              "Lidar-simulated brightness misaligned by over 2.5 m in a block, or a known building off its spot",
              "Re-solve offsets per track, set corner reflectors, widen the hit radius by the offset"),
             ("Too few dates: 8 to 12 per track, where the steadiness rule assumes about 30",
              "Steady pixels exceed the 0.13% expected by chance, or flood open fields",
              "Require two tracks, raise the cutoff, add dates as released"),
             ("No steel left to see: casings on plugged wells are often cut or buried",
              "A known building passes, but wells match the control-spot rate",
              "Compare by DEP status; active wells keep pumpjacks and tanks")]
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
             "and combined per site. Placement is the first risk because a pit is only a few pixels wide. It is checked by simulating radar brightness from the lidar and matching it block by block: 47 of 48 blocks agree within 2.5 m. That check shares the simulation used to fit the offsets, so a known building and, ideally, corner reflectors give the independent test.")


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
