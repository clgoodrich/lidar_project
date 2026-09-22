# -*- coding: utf-8 -*-
"""Every number in the deck checked against its source, and the ones that lost.

Run on 2026-09-21. Each entry below names the file the number was measured
from, so the next person can re-check it without re-deriving anything.

WHAT WAS WRONG
--------------
1.  Slide 66 and slide 72 report two different road models on the same tile
    and the same subset, and neither says so.
      slide 66  completeness 0.811, correctness 0.816, 1,239 of 1,496
                = `sweep_orient` at threshold 0.40
      slide 72  1,162 of 1,496, 0.777
                = `recall_relabeled20260806` at threshold 0.50
    Both rows are real and both sit in
    `data/613590/results/road/thresholds/road_score_vs_roads_shp_613590_1m.csv`.
    Slide 66 now quotes the same model and threshold as slide 72, so slide 72
    reads as the breakdown of slide 66 rather than as a contradiction of it.
    The cost is honest: completeness 0.759 rather than 0.811.

2.  Slide 69's "42 pit and 161 pad candidates" comes from
    `data/613590/derived/inference_05/*.gpkg`, written 2026-06-12 by the
    retired pre-U-Net pipeline. The same slide quotes the U-Net's recall of
    0.911, and the U-Net transfer found about 139 of the 153 drawn pits with
    363 to 1,162 predictions per fold. 42 against 139 on one slide. The map on
    the slide IS the 2026-06 candidate set, so the counts stay and are
    attributed instead of being silently swapped.

3.  Slide 47's body says six layers were drawn by hand and its notes say
    seven. Six is right: plat, pit_inside, pit_outside, roads, not_roads,
    drainage, per `pyogrio.list_layers` on
    `qgis/annotations/annotations_proj.gpkg`. pit_wall is derived, which the
    note itself goes on to say.

4.  Slide 17's notes still said "about a quarter of the holes close" after the
    body was corrected to two in five. 2,857,002 of 7,097,720 is 40.2%.

5.  Slides 9 and 15 notes said "13.8% of the training area". The denominator
    is the 51,470,048 cells a return reached, not the 81,000,000 cells of the
    9t box at 0.5 m -- against that it would be 8.8%. Slide 15's body already
    said it correctly.

6.  A pit is not a 0.7 m dish. Measured over the 503 paired pits in 9t by
    `_median_pit_plan_view_9t.py`: median depth 0.54 m (10-90% 0.26-0.91),
    15.3 m across the rim, 5.8 m across the floor. Slide 46's body already
    said "about half a meter"; slides 34, 36 and 46's notes still said 0.7 m
    and 13 m.

7.  Slide 46's notes still walked through three panels after the local-relief
    panel was removed from the figure.

8.  Slide 20's body describes a left and a right panel. The figure has three
    (`_dem_with_and_without_deleted_returns_9t.py` line 136), and what the
    body calls "right" is the middle one.

9.  Slide 75's "63% of it is unswept" is the wrong statistic off the right
    file. `data/613590/results/annotation_coverage_613590_vs_9t.json` gives
    `largest_blank_region_frac` 0.632 -- the largest single unswept region,
    not the unswept share. The drawn extent covers 70.3% of the tile and only
    33.3% of its blocks hold a drawn pit.

WHAT CHECKED OUT, so nobody re-does it
--------------------------------------
    pits 506 outlines / 96,643 m2 / mean 191 / median 183 / p10-p90 121-267
    pits 503 floors  / 14,659 m2 / mean 29 / median 26 / p10-p90 14-47
    floor is 15.2% of outline by area; 503 pairs give 81,532 m2 of wall
    586 pairs, 126 floors with no rim, 138 rims with no floor (one rim took
        two floors, which is why it is 138 and not 723-586)
    pads 650 in 9t, 1.151 km2, mean 1,771, median 1,645, p10-p90 1,029-2,614
    roads 1,358 lines / 206.1 km in 9t; 3,690 / 535.9 km all areas
    drainage 1,791 segments / 45.0 km; short 1.9, stream 27.5, rest 15.6
    pit CV5 F2 micro 467/503 = 0.928, 467/738 = 0.633   data/9t/models/pit/unet_cv5
    pad CV5 F2 micro 593/650 = 0.912, 593/1010 = 0.587  data/9t/models/pad/unet_cv5
    road 9t at thr 0.20: 735 clean / 722 found / 0.982, 1,220 / 1,207 / 0.989,
        42.56 of 43.07 km = 98.8%, 101.65 ha = 5.02%
    613590 pits: 153 drawn, F2 0.911 (sd 0.045) vs 0.928, containment 0.906,
        folds 127/137/142/145/146, F1 0.792 vs 0.861
    613590 roads at 0.50: added 1,162/1,496 = 0.777, review 4,004 at 0.966
    613590 network 3,693 features / 231.4 km against TIGER 40.0 km = 5.79x
    7 model channels: lrm_25 lrm_5 slope tpi_05 openness_pos openness_neg
        roughness_11        data/9t/derived/05/feature_stats.json
    113,556,364 returns over 10 squares, 43.678% class 1; 5,615,796 at-ground
        over 4 squares; 18.6 deg against 9.4
    51,470,048 reached / 13.79% void / 8.24% after / 2,857,002 closed /
        13,746,698 discarded / 44,371,436 with ground / section 32% to 2%
    corn rows 79.31 deg (sd 0.36) against 78 geometry and 79 FFT, 3.35 m
    discarded returns 6.5-6.7 cm RMSE against 7.0-9.9 cm for the kept ones
    architectures pits 0.559 to 0.561, pads 0.555 to 0.608
    8,054 of 20,108 Venango wells on a placeholder spud date, 1,553 with none
    18 deg cut in 6 of 7 Venango tiles, 0 of 7 McKean
    NISAR autumn pair coherence 0.50 with 94% usable, mid-winter 0.14

STILL UNRESOLVED, flagged rather than edited
--------------------------------------------
Slides 5 and 6 say the DEM is gridded at 1 m. Everything from slide 20 onward
is 0.5 m. That is the open 1 m / 0.5 m question, not a typo, so it is left
alone.
"""
from __future__ import annotations

BULLET = "•  "

AUDIT_EDITS = [
    # -- 4. slide 17 notes, to match the body ------------------------------
    ("The void drops from 13.8% of the area to 8.2%. That is 2.9 million cells",
     "The void drops from 13.8% of the ground the laser reached to 8.2%. "
     "That is 2.9 million cells",
     "notes"),
    ("About a quarter of the holes close.",
     "Two holes in five close.",
     "notes"),
    # -- 5. slides 9 and 15 notes, the denominator -------------------------
    ("13.8% of the training area. Wherever it is red, the surface shown is an",
     "13.8% of the ground the laser reached. Wherever it is red, the surface "
     "shown is an",
     "notes"),
    # -- 6. the pit is half a metre deep, not 0.7 --------------------------
    (BULLET + "They stand under a centimetre tall. A pit is a 0.7 m dish.",
     BULLET + "They stand under a centimetre tall. A pit is a dish about "
     "half a metre deep.",
     "body"),
    ("A collapse pit is a dish about 0.7 m deep, so the rows are far "
     "shallower.",
     "A collapse pit is a dish about half a metre deep, so the rows are far "
     "shallower.",
     "notes"),
    ("A shallow bowl. About 0.7 m deep and 13 m across.",
     "A shallow bowl. Measured over the 503 paired pits in 9t: 0.54 m deep "
     "at the median, 15.3 m across the rim, 5.8 m across the floor.",
     "notes"),
    ("Worth pausing on the proportions: seventy centimetres of depth spread "
     "over",
     "Worth pausing on the proportions: half a metre of depth spread over",
     "notes"),
    ("thirteen metres of width. It is a dish, not a hole.",
     "fifteen metres of width. It is a dish, not a hole.",
     "notes"),
    # 6/7 continued: the "501 paired pits", the dropped local-relief
    # paragraph and the panel numbers are fixed at source in
    # _speaker_note_additions.PLAN_VIEW, because that note is appended
    # by a later build step and is not in v15 to be edited here.
    # -- 8. slide 20 has three panels, and the body only named two ---------
    (BULLET + "Right: the same ground rebuilt with the deleted returns put "
     "back",
     BULLET + "Middle: the same ground rebuilt with the deleted returns put "
     "back. Right: what changed — a median of 3 cm where a void was "
     "filled",
     "body"),
    # -- 3. six layers were drawn, not seven -------------------------------
    ("Seven layers were drawn by hand. Everything else in the project was "
     "computed",
     "Six layers were drawn by hand. Everything else in the project was "
     "computed",
     "notes"),
    ("from those seven.", "from those six.", "notes"),
    # -- 1. slide 66 onto the same road model as slide 72 ------------------
    ("completeness 0.811  ·  correctness 0.816",
     "hand-drawn subset at 0.50  ·  completeness 0.759  ·  "
     "correctness 0.828",
     "body"),
    ("Completeness 0.811: it found 81.1% of the real road.",
     "Completeness 0.759: it covered 75.9% of the length of the hand-drawn "
     "road.",
     "notes"),
    ("Correctness 0.816: 81.6% of the road it drew is real road.",
     "Correctness 0.828: 82.8% of the road it drew is real road.",
     "notes"),
    ("Quality 0.686: a single score combining both, so you cannot win by "
     "sacrificing",
     "Quality 0.655: a single score combining both, so you cannot win by "
     "sacrificing",
     "notes"),
    # The "1,162 of 1,496" note itself is retargeted at source in
    # _port_v17_user_edits.V17_NOTE_APPENDS, same reason.
    # -- 2. slide 69's counts belong to the retired pipeline ---------------
    ("42 pit and 161 pad candidates, no retraining",
     "42 pit and 161 pad candidates, from the earlier pipeline",
     "body"),
    (BULLET + "Pits are scorable here: 153 drawn, recall 0.911",
     BULLET + "Those two counts are the pre-U-Net detector's. The U-Net is "
     "scored separately: 153 pits drawn, recall 0.911",
     "body"),
    ("42 pit candidates and 161 pad candidates, with no retraining of any "
     "kind.",
     "42 pit candidates and 161 pad candidates, with no retraining of any "
     "kind. Those two counts and this map are the earlier pipeline's, from "
     "June. They are not the U-Net's, which found about 139 of the 153 "
     "drawn pits on this tile.",
     "notes"),
    # -- 9. slide 75, the right statistic off the right file ---------------
    (BULLET + "Finish annotating 613590 — 63% of it is unswept, which "
     "is why precision is missing",
     BULLET + "Finish annotating 613590 — its largest unswept region is "
     "63% of the tile, which is why precision is missing",
     "body"),
    ("Finish annotating 613590. 63% of it is unswept, which is exactly why "
     "there is",
     "Finish annotating 613590. Its largest unswept region is 63% of the "
     "tile and only a third of its blocks hold a drawn pit, which is exactly "
     "why there is",
     "notes"),
]

#: strings that must not survive the build
AUDIT_STALE = [
    "a quarter of the holes close",
    "13.8% of the training area",
    "A pit is a 0.7 m dish",
    "0.7 m deep and 13 m across",
    "Seven layers were drawn by hand",
    "completeness 0.811",
    "1,239 of 1,496",
    "63% of it is unswept",
    "501 pair with a floor",
]
