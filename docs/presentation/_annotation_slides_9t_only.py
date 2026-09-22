# -*- coding: utf-8 -*-
"""The annotation slide edits, 9t only. Imported by _build_v17_from_v15.py.

WHY THIS EXISTS AS ITS OWN FILE
-------------------------------
The user asked for the annotation slides to talk about 9t and nothing else.
The deck had been quoting all-area totals in the headline and then splitting
only the AREA by region, never the count, so "723 pit outlines" read as a 9t
number when it is the total across 9t, 613590 and everything else.

    layer            all areas    inside 9t
    pads                   995          650
    pit outlines           723          506
    pit floors             712          503
    pit walls              586          503
    roads                3,690        1,358
    drainage             1,791        1,791   (9t only already)

Every number below was measured on 2026-09-21 by
_measure_annotations_9t.py against qgis/annotations/annotations_proj.gpkg,
selecting polygons whose CENTROID falls inside the 9t bounding box
(619500, 4593000, 624000, 4597500, EPSG:6346) and CLIPPING lines to it, which
is the right treatment for each: a pit belongs to whichever tile holds it, a
road runs across the boundary and only the part inside counts.

WHAT CHANGES, BEYOND THE SCOPE
------------------------------
Restricting to 9t moves the distributions, so the averages move with them and
cannot simply be carried over:

    pads     mean 1,451 -> 1,771 m2,  median 1,343 -> 1,645 m2
    outlines mean   205 ->   191 m2,  median   197 ->   183 m2
    floors   mean    32 ->    29 m2,  median    29 ->    26 m2

The floor-to-outline ratio recomputes to 15%, not 16%.

The per-region split lines go entirely. They exist to break a total into
regions, and there is no longer a total to break: the slide is one region.

Roads keep a separate count for the not-road lines, which inside 9t is 61
lines and 7.0 km, not the 112 lines and 18.0 km drawn across everywhere.
"""
from __future__ import annotations

BULLET = "•  "
EMDASH = "—"

#: (old, new, "body" | "notes"). A new value of None DELETES the paragraph.
ANNOTATION_EDITS = [
    # ---- slide 41, roads -------------------------------------------------
    ("535.9 km of road, drawn by hand",
     "206.1 km of road inside 9t, drawn by hand", "body"),
    (BULLET + "3,690 separate lines, joining into 1,747 connected networks",
     BULLET + "1,358 separate lines inside the tile", "body"),
    (BULLET + "Median line 104 m, mean 145 m",
     BULLET + "Median line 106 m, mean 152 m", "body"),
    (BULLET + "9t 206.1 km   |   613590 187.6 km   |   elsewhere 142.2 km",
     None, "body"),
    (BULLET + "Plus 112 lines, 18.0 km, drawn as not-road",
     BULLET + "Plus 61 lines, 7.0 km, drawn as not-road", "body"),

    # ---- slide 43, pads --------------------------------------------------
    ("995 well pads, 1.44 km² in total",
     "650 well pads in 9t, 1.15 km² in total", "body"),
    (BULLET + "Average pad 1,451 m2, median 1,343 m2",
     BULLET + "Average pad 1,771 m², median 1,645 m²", "body"),
    (BULLET + "Middle 80% between 667 and 2,357 m2",
     BULLET + "Middle 80% between 1,029 and 2,614 m²", "body"),
    (BULLET + "9t 1.15 km²   |   613590 none drawn   |   elsewhere "
     "0.29 km²", None, "body"),

    # ---- slide 44, pit outlines ------------------------------------------
    ("723 pit outlines, 148,400 m²",
     "506 pit outlines in 9t, 96,600 m²", "body"),
    (BULLET + "Average outline 205 m2, median 197 m2",
     BULLET + "Average outline 191 m², median 183 m²", "body"),
    (BULLET + "Middle 80% between 127 and 292 m2",
     BULLET + "Middle 80% between 121 and 267 m²", "body"),
    (BULLET + "9t 97,000 m²   |   613590 10,000 m²   |   elsewhere "
     "42,000 m²", None, "body"),
    (BULLET + "586 pair with a floor, giving 99,100 m² of measurable wall",
     BULLET + "501 pair with a floor, giving 81,500 m² of measurable wall",
     "body"),

    # ---- slide 45, pit floors --------------------------------------------
    ("712 pit floors, 22,900 m²",
     "503 pit floors in 9t, 14,700 m²", "body"),
    (BULLET + "Average floor 32 m2, median 29 m2",
     BULLET + "Average floor 29 m², median 26 m²", "body"),
    (BULLET + "Middle 80% between 15 and 51 m2",
     BULLET + "Middle 80% between 14 and 47 m²", "body"),
    (BULLET + "9t 15,000 m²   |   613590 6,000 m²   |   elsewhere "
     "3,000 m²", None, "body"),
    (BULLET + "A floor is 16% of its outline by area, the rest is wall",
     BULLET + "A floor is 15% of its outline by area, the rest is wall",
     "body"),

    # ---- slide 46, morphology headline -----------------------------------
    # The old line said 13 m across. The median outline inside 9t encloses
    # 183 m2, which is 15.3 m for an equivalent circle.
    # Depth is now measured rather than quoted: for all 501 paired pits in 9t,
    # median wall elevation minus median floor elevation gives 0.54 m
    # (10-90%: 0.26-0.91). The old 0.7 m was high. 15 m across is the
    # equivalent diameter of the median 183 m2 outline.
    ("A shallow bowl about 0.7 m deep and 13 m across.",
     "A shallow bowl about half a metre deep and 15 m across.", "body"),
]

#: phrases that must not survive a run, so a half-applied pass is caught
ANNOTATION_STALE = [
    "535.9 km", "3,690 separate lines", "995 well pads", "723 pit outlines",
    "712 pit floors", "613590 187.6 km", "613590 none drawn",
    "613590 10,000", "613590 6,000", "16% of its outline", "13 m across",
    "112 lines, 18.0 km",
]
