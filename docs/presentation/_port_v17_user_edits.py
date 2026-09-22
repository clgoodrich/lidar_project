# -*- coding: utf-8 -*-
"""The edits the user made by hand in v17, carried into the v15 -> v18 build.

Imported by _build_v18_from_v15.py.

HOW THESE WERE FOUND
--------------------
v17 on disk was saved at 20:57, after the last build of it. Diffing it against
the copy committed at dfd48fd, aligned on slide TITLE rather than index --
index alignment was useless because a deleted slide shifted everything after
it and made 30 slides look changed when 8 were.

STRUCTURE THE USER CHANGED
--------------------------
    deleted   "Preprocessing - resolving overlaps"
    retitled  "...pit and pad candidates" -> "...stuff to investigate"
    dropped   "quality 0.686" from the second-tile roads footer
    dropped   two Permian bullets from "Further research - more ground"
    dropped   the geomorphon bullet from "Further research - a better model"

Deleting the overlaps slide also retires the burn-order speaker note written
for it earlier today; there is no longer a slide to attach it to.

THE ONE CONFLICT, AND HOW IT IS RESOLVED
----------------------------------------
The user replaced the "What the numbers say" notes with Codex's FIRST draft --
the wording Codex itself then corrected, and which the user afterwards asked to
have fixed. Keeping the paste verbatim would undo the correction pass.

So the register is kept and the numbers are not. The user's phrasing is plainer
than what was there before -- "Catch 93%", and the closing line about guiding
human review rather than being accepted automatically is better than anything
in the old note -- and all of that survives. What does not survive is
"very efficient" / "less efficient" (ranks area, not review effort),
"roughly one-third" (it is 37% and 41%), and quoting recall beside flagged area
as though they came from one measurement.

THE ROAD FIGURE IN THAT PASTE
-----------------------------
The paste carried "1,162 of 1,496 road segments, about 78%". That is real:
model recall_relabeled20260806, threshold 0.50, subset 613590_added_r2, from
road_score_vs_roads_shp_613590_1m.csv. But it is a different model from the one
the second-tile roads slide shows, and it is not a 9t number at all, so it does
not belong in a 9t summary.

The slide's own numbers are sweep_orient at 0.40 on the same subset:
completeness 0.811, correctness 0.816, 1,239 of 1,496 chunks found, 0.828. So
the count the user wanted goes onto that slide, taken from the model the slide
is actually about.

TYPOS
-----
Two in the pasted notes, fixed here rather than carried: "models shape" ->
"model's shape", "drawnb" -> "drawn".
"""
from __future__ import annotations

BULLET = "•  "

#: Slides the user deleted. The builder removes them by title.
V17_DELETED_SLIDES = [
    "Preprocessing — resolving overlaps",
]

#: Notes the builder must NOT append, because their slide is gone.
V17_RETIRED_NOTES = [
    "Preprocessing — resolving overlaps",
]

#: (old, new, "body" | "notes"); None deletes the paragraph.
V17_EDITS = [
    # ---- retitle the candidates slide ------------------------------------
    ("Second tile, 613590 — pit and pad candidates",
     "Second tile, 613590 — stuff to investigate", "body"),

    # ---- second-tile roads footer: quality dropped -----------------------
    ("completeness 0.811  ·  correctness 0.816  ·  quality 0.686",
     "completeness 0.811  ·  correctness 0.816", "body"),

    # ---- Permian bullets dropped -----------------------------------------
    (BULLET + "A second basin — Permian QL1 at 12–15 pts/m², "
     "with Texas RRC orphan records as independent ground truth", None, "body"),
    (BULLET + "One Permian cell holds 136 confirmed orphans in 5 km, a denser "
     "test than anywhere in Venango", None, "body"),

    # ---- geomorphon bullet dropped ---------------------------------------
    (BULLET + "Geomorphon enclosure as an extra channel; the old +31% was "
     "measured on the retired ensemble, so it needs re-testing", None, "body"),

    # ---- 146 of 153 is the BEST of five folds, not the average -----------
    # pit_transfer_recall_per_fold_613590_05.csv, objective f2: the five folds
    # score 0.830, 0.895, 0.928, 0.948, 0.954 on 613590, which is 127, 137,
    # 142, 145 and 146 of 153. The slide quoted 146 beside an average of
    # 0.911, so the count and the rate came from different models and the
    # count was the best one.
    ("146 of 153 found, by a model that never saw this tile",
     "139 of 153 found on average, by five models that never saw this tile "
     "— the folds range from 127 to 146",
     "body"),

    # ---- roads: do not pair a clean-subset recall with a full-set length --
    # Codex proposed "735 withheld segments spanning 25.02 km". That is not
    # reproducible: road_chunks_9t.gpkg has been regenerated since the sweep
    # ran and now holds 1,578 held-out chunks against the sweep's 1,220, so no
    # current file gives the clean subset's length. The two statements are
    # separated instead, each with the set it belongs to.
    (BULLET + "Roads — 722 of 735 fully-withheld segments, 98.2%, and "
     "98.8% of the road length, flagging 5.0%",
     BULLET + "Roads — 722 of 735 fully-withheld segments, 98.2%. Across "
     "the full withheld set, 43.07 km, 98.8% of length recovered. Flags 5.0%.",
     "body"),
    ("735 fully-withheld segments  ·  recall 0.982  ·  98.8% of road "
     "length recovered  ·  flags 5.02%",
     "735 fully-withheld segments  ·  recall 0.982  ·  flags 5.02%  "
     "·  length recovery 98.8% is over the full 43.07 km set",
     "body"),
]

#: (slide title, marker, text) appended to the existing note, as the user wrote
#: it. Typos corrected, wording otherwise untouched.
V17_NOTE_APPENDS = [
    ("Manual Annotation – Pits (Outside)", "Conservative",
     "Conservative"),
    ("Model building — does a bigger network help?",
     "matches the drawn shape",
     "How closely the model's shape matches the drawn shape. Higher is good."),
    ("Second tile, 613590 - the pits it found",
     "cutoff chosen to care about",
     "On the balanced rule: cutoff chosen to care about real pits and "
     "avoiding false alarms."),
    # the count the user wanted, from the model this slide actually shows
    ("Second tile, 613590 – Roads",
     "1,239 of 1,496",
     "In plain terms: on the roads added during the second annotation pass, "
     "48.87 km of them, the model found 1,239 of 1,496 segments — about "
     "83%. Completeness 0.811 is the share of road LENGTH it covered, which "
     "is the stricter of the two."),
]

#: Notes replaced outright rather than appended to.
V17_NOTE_REPLACE = {
    "What the numbers say": (
        "The five numbers, in plain terms.\n\n"
        "Pits: found 467 of the 503 drawn pits, 93%. The 0.21% of the map "
        "figure people remember is a DIFFERENT test on a different held-out "
        "set, so do not say the two in one breath.\n\n"
        "Roads: found 722 of 735 segments whose whole parent road was held "
        "back, 98%, and 98.8% of the road length, while flagging 5% of the "
        "map.\n\n"
        "Pads: found 593 of 650, 91%. A separate sweep holds that same recall "
        "while flagging 9.8% of the map, not 11.6% — so do not present "
        "11.6% as the price.\n\n"
        "New tile: pit recall drops 1.7 points, 92.8% to 91.1%, which "
        "suggests the model transfers to this tile. One tile, not a region.\n"
        "\n"
        "Precision: 37% of pit flags and 41% of pad flags do not match the "
        "single annotator's labels. Not proven wrong on the ground — an "
        "unmatched flag may be a real pit nobody drew. So predictions guide "
        "human review, they are not accepted automatically.\n\n"
        "Resist ranking the three by flagged area. Pit floors are small, "
        "roads run everywhere and pads are broad, so area says more about "
        "what the target is than about how efficient the model is. The pit "
        "sweep still produces 1,041 polygons to look at."
    ),
}
