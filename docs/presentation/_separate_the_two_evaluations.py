# -*- coding: utf-8 -*-
"""Stop quoting recall and flagged-area as if they came from one measurement.

Imported by _build_v18_from_v15.py.

THE PROBLEM
-----------
Lines of the form "recall 0.928, flagging 0.21% to get it" read as one measured
trade-off. They are not. For pits and pads the two halves come from different
evaluations with different reference sets, different thresholds and different
matching rules:

    pits, recall 0.928   cross-validation, 467 of 503 annotated floors,
                         F2-selected thresholds 0.35-0.45 per fold, IoU >= 0.30
    pits, 0.21% flagged  a separate sweep, 126 of 127 held-out RIMS, fixed
                         threshold 0.20, matched by the predicted floor's
                         centre falling inside the rim

503 and 127 are not the same held-out set. That is the crux, and saying it once
is clearer than listing the three ways the evaluations differ.

WHAT IS ACTUALLY WRONG, NOT JUST IMPRECISE
-------------------------------------------
Pads. "Recall 0.912, but 11.6% of the tile flagged to reach it" describes an
operating point the sweep already beats:

    threshold 0.45   178 of 194 found   11.643% flagged   1049 polygons
    threshold 0.50   178 of 194 found    9.775% flagged   1005 polygons

Identical recall, 1.87 points less ground, and 44 fewer polygons to review. The
slide was not merely loose, it was quoting the worse of two measured options.

Pits have the same shape of result and it was never mentioned:

    threshold 0.20   126 of 127 rims   0.214% flagged   1041 polygons
    threshold 0.30   125 of 127 rims   0.139% flagged    827 polygons

ROADS
-----
0.982 belongs to the 735-segment subset whose parent roads were withheld
entirely, not to the full 1,220-segment set, which scores 0.989. The 43.07 km
describes the full set. And the length figure exists rather than having to be
disclaimed: 42.56 of 43.07 km, 98.8%, sits one column over in the same file.

PRECISION
---------
"0.59 to 0.69 across three runs" does not describe its source. There are two
targets and two threshold-selection rules, not three runs, and roads are not in
the range at all. Quoted micro, matching every other figure in the deck:

    pits F1 0.686   pits F2 0.633   pads F1 0.597   pads F2 0.587

The deck quotes F2 recall, so it should quote F2 precision beside it.

FALSE ALARMS
------------
"Roughly a third" understates it: 271 of 738 pit predictions and 417 of 1,010
pad predictions do not match, which is 37% and 41%. And an unmatched prediction
is not proven to be a false feature -- it may be a real pit nobody drew, or one
whose outline missed the overlap bar. The wording now says what was measured.

EFFICIENCY
----------
0.21% against 11.6% ranks area, not review effort. The pit sweep produces 1,041
polygons while flagging a fifth of one percent. Polygon count is the reviewable
quantity and it is in the same files, so the comparison is made on that.
"""
from __future__ import annotations

BULLET = "•  "

#: (old, new, "body" | "notes"); None deletes the paragraph.
EVAL_EDITS = [
    # ---- slide 59 roads: footer -----------------------------------------
    ("43.07 km withheld  ·  recall 0.982  ·  flags 5.02% of the tile",
     "735 fully-withheld segments  ·  recall 0.982  ·  98.8% of road "
     "length recovered  ·  flags 5.02%",
     "body"),
    ("Recall 0.982 means it found 98.2% of that road. Recall is: of the real "
     "things",
     "Recall 0.982 means it found 722 of the 735 segments whose whole parent "
     "road was withheld. Across the full withheld set of 1,220 segments, "
     "43.07 km, it is 0.989. Segment recall is not length: of the road length "
     "itself it recovered 42.56 of 43.07 km, 98.8%. Recall is: of the real "
     "things",
     "notes"),

    # ---- slide 61 pads: footer ------------------------------------------
    ("held-out blocks on 9t  ·  recall 0.912  ·  precision 0.587  "
     "·  flags 11.6%",
     "cross-validation on 9t  ·  recall 0.912  ·  precision 0.587  "
     "·  F2-selected, IoU ≥ 0.30",
     "body"),
    ("Flags 11.6% of the tile.",
     "Flagged area comes from a separate sweep, not from this number. In that "
     "sweep the model found 178 of 194 pads while flagging 11.64% of the "
     "tile — and found the same 178 at a higher cut-off while flagging "
     "only 9.78%, with 44 fewer polygons to review. The higher cut-off is the "
     "one to quote.",
     "notes"),
    ("Precision 0.587: of everything it flagged, 58.7% were real. So roughly "
     "four in",
     "Precision 0.587: 593 of 1,010 predictions matched an annotated pad. So "
     "about four in",
     "notes"),

    # ---- slide 62 pits: footer ------------------------------------------
    ("held-out blocks on 9t  ·  recall 0.928  ·  precision 0.633  "
     "·  flags 0.21%",
     "cross-validation on 9t  ·  recall 0.928  ·  precision 0.633  "
     "·  F2-selected, IoU ≥ 0.30",
     "body"),
    ("Flags 0.21% of the tile. That is a fifth of one percent of the ground.",
     "The 0.21% figure is NOT from this evaluation. It comes from a separate "
     "search-area test on 127 withheld pit rims, at a fixed cut-off of 0.20, "
     "matched by whether the predicted floor's centre lands inside the rim. "
     "There it found 126 of 127 while flagging a fifth of one percent of the "
     "ground. A slightly higher cut-off finds 125 of 127 for 0.14%. Two "
     "different held-out sets, so the two numbers cannot be spoken in one "
     "breath.",
     "notes"),
    ("Recall 0.928: it found 92.8% of the pits.",
     "Recall 0.928: it matched 467 of the 503 annotated pit floors.",
     "notes"),

    # ---- slide 73 the summary, where all of it lands ---------------------
    (BULLET + "Pits — recall 0.928, and only 0.21% of the tile flagged "
     "to get it",
     BULLET + "Pits — cross-validation recovered 467 of 503 annotated "
     "floors, 92.8%",
     "body"),
    (BULLET + "Roads — recall 0.982 on 43 km withheld, 5.0% of the tile "
     "flagged",
     BULLET + "Roads — 722 of 735 fully-withheld segments, 98.2%, and "
     "98.8% of the road length, flagging 5.0%",
     "body"),
    (BULLET + "Pads — recall 0.912, but 11.6% of the tile flagged to "
     "reach it",
     BULLET + "Pads — cross-validation recovered 593 of 650, 91.2%; a "
     "separate sweep held its recall while flagging 9.8%",
     "body"),
    (BULLET + "On a second tile, never trained on: pit recall 0.911, down "
     "0.017",
     BULLET + "On a second tile, never trained on: pit recall averages 0.911 "
     "across the five models, down 0.017",
     "body"),
    (BULLET + "Precision runs 0.59 to 0.69, measured against what one person "
     "drew",
     BULLET + "Precision 0.633 for pits and 0.587 for pads at the same "
     "recall-weighted setting, measured against what one person drew",
     "body"),
    # the same five, in the notes
    ("Pits: recall 0.928, flagging 0.21% of the tile.",
     "Pits: cross-validation matched 467 of 503 annotated floors, 92.8%. The "
     "0.21% flagged is a different test on a different held-out set, so do "
     "not say the two in one sentence.",
     "notes"),
    ("Roads: recall 0.982 on 43 km withheld, flagging 5.0%.",
     "Roads: 722 of 735 segments whose whole parent road was withheld, 98.2%, "
     "flagging 5.0%. The full withheld set is 43.07 km and 1,220 segments and "
     "scores 0.989. Of road length, 98.8% recovered.",
     "notes"),
    ("Pads: recall 0.912, but flagging 11.6% to get there.",
     "Pads: cross-validation matched 593 of 650, 91.2%. The sweep found 178 "
     "of 194 at 11.64% flagged and the same 178 at 9.78%, so 11.6% was never "
     "the price of that recall.",
     "notes"),
    ("On the second tile, never trained on, pit recall 0.911 -- down 0.017.",
     "On the second tile, never trained on, pit recall averages 0.911 across "
     "the five models, down 0.017. Under the balanced rule the drop is larger, "
     "0.861 to 0.792.",
     "notes"),
    # Both wrapped lines of the old sentence are replaced together, matched
    # across the newline, so no orphaned half is left behind.
    ("Precision across the three runs 0.59 to 0.69, which means roughly a "
     "third of\nwhat gets flagged is a false alarm. Measured against what one "
     "person drew.",
     "Precision is 0.633 for pits and 0.587 for pads, at the same "
     "recall-weighted setting the recall figures come from. There is no "
     "shared figure across three runs; roads are not in that range at all.\n"
     "\n"
     "That precision means 37% of pit predictions and 41% of pad predictions "
     "did not match an annotated shape. Not four in ten wrong on the ground "
     "— an unmatched prediction may be a real pit nobody drew, or one "
     "whose outline missed the overlap bar.\n"
     "\n"
     "And all of it is measured against what one person drew. These are "
     "agreement scores, not field-confirmed detection rates.",
     "notes"),

    # ---- slide 75: the pad recommendation now has a number ---------------
    ("Cut the pad model's flagged area. Its recall is fine; the 11.6% of "
     "ground it",
     "Cut the pad model's flagged area. Its recall is fine, and the sweep "
     "already shows 9.78% holds the same recall as 11.64%. The ground it",
     "notes"),
]

EVAL_STALE = [
    "0.21% of the tile flagged to get it",
    "recall 0.982 on 43 km withheld",
    "11.6% of the tile flagged to reach it",
    "Precision runs 0.59 to 0.69",
    "flags 0.21%",
    "flags 11.6%",
]
