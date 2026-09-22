# -*- coding: utf-8 -*-
"""Speaker-note additions, appended to whatever note a slide already has.

Imported by _build_v17_from_v15.py. Each entry is (slide title, text). The
builder appends and never replaces, so the user's own note edits survive, and
it skips any slide whose note already contains the entry's marker phrase so
re-running is safe.

WHY THESE FOUR
--------------
Each one is a question that was asked out loud and could not be answered from
the slide:

  * the height bins  -- "is this just random?"  No. They are the ASPRS classes
    from the USGS 3DEP Lidar Base Specification, so the answer is a citation,
    not a judgement call. Bin edges read from
    notebooks/wellsight_v2/s7_analysis/_classify_nonground_returns_9t.py,
    BANDS at line 82.
  * train / val / test -- three words used throughout the deck and defined
    nowhere in it.
  * burn order -- the slide says "burn order decides" without saying what burn
    order is, so the sentence explains nothing to anyone who does not already
    know. Order read from _build_labels_pit_pad_9t_1m.py line 32: wall first,
    floor on top.
  * the plan view -- new figure on slide 46 needs a note that says what a
    listener is looking at.
"""
from __future__ import annotations

BINS = (
    "If asked how the height bins were chosen — they are not ours and "
    "they are not arbitrary.\n\n"
    "They are the standard vegetation classes in the USGS 3DEP Lidar Base "
    "Specification, which is the specification this survey was flown to. Low "
    "vegetation is 0.15 to 2 m. Medium is 2 to 5 m. High is 5 to 60 m. Below "
    "−0.15 m and above 60 m are the two noise classes.\n\n"
    "The 0.15 m either side of the ground is the tolerance band. A return "
    "inside it is close enough to the ground that nobody can say from height "
    "alone whether it hit the dirt or something lying on it, so we do not "
    "guess — that band is reported on its own.\n\n"
    "The point of using the published edges is that anyone can check the "
    "chart against another survey and get a like-for-like comparison. If we "
    "had picked our own cut-offs, the shape of this chart would be our choice "
    "rather than a measurement."
)

TRAIN_VAL_TEST = (
    "If asked what train, validation and test mean — three piles of "
    "ground, and the model is allowed to see less of each one in turn.\n\n"
    "TRAIN, 70%. The model looks at these and adjusts itself. This is the only "
    "data it ever learns from.\n\n"
    "VALIDATION, 15%. The model never learns from these, but we look at them "
    "while training to make decisions — when to stop, and what probability "
    "cut-off to use. So the model does not see them, but we do, and that "
    "still leaks a little.\n\n"
    "TEST, 15%. Nobody looks until the end. Not the model, not us. It is "
    "scored once, and that score is the one we report.\n\n"
    "The reason for three rather than two: if you tune the cut-off on the same "
    "data you report, you have tuned to that data and the number flatters you. "
    "The validation set absorbs the tuning so the test set stays clean.\n\n"
    "One thing that matters more than the ratio: the split is by BLOCK of "
    "ground, not by pit. Neighbouring pits go into the same pile together. "
    "Split at random instead and a pit's own neighbour lands in training, the "
    "model effectively sees the answer through the window next door, and the "
    "score comes out too good."
)

BURN_ORDER = (
    "What this slide is actually saying, plainly.\n\n"
    "The hand-drawn labels are shapes — outlines on a map. The model "
    "cannot read shapes, it reads a grid of pixels. So every shape has to be "
    "painted onto that grid, and the word for painting a shape onto a grid is "
    "burning.\n\n"
    "The problem: a pixel can only hold one label, and the shapes overlap. A "
    "pit sits inside a well pad, so the pixels in the middle are covered by "
    "both. Something has to decide which label that pixel gets.\n\n"
    "The rule is painting order. Whatever is painted last is what stays, the "
    "way a second coat of paint covers the first. We paint the bigger, more "
    "general thing first and the smaller, more specific thing on top — "
    "the pit wall goes down, then the pit floor over it.\n\n"
    "Why it is worth a slide: the order is fixed in one place and every script "
    "uses it. If two scripts painted in different orders, the same pit would "
    "be labelled floor in one dataset and wall in another, and every score "
    "after that would be measuring the disagreement rather than the model."
)

PLAN_VIEW = (
    "An average pit, seen from directly above.\n\n"
    "This is a real pit, not a drawing. Of the 501 pits inside 9t that have "
    "both an outline and a floor drawn, this is the one closest to the middle "
    "on both at once.\n\n"
    "Left is shaded relief — roughly what the eye would get from a normal "
    "relief map. You can find the pit, but only because it is circled.\n\n"
    "Middle is local relief, which is the same ground with the hillside "
    "subtracted. Now the dish is obvious. That is the layer that does the work "
    "in this project.\n\n"
    "Right is the same two outlines with the numbers on them. Blue is the "
    "outer rim, orange is the flat floor inside it. About 15 m across the rim, "
    "about 6 m across the floor, and roughly half a metre deep.\n\n"
    "The shape to hold on to: it is a wide, shallow dish with a small flat "
    "bottom. The floor is only about a seventh of the area inside the rim. "
    "That is why the model is taught rim and floor as two separate things "
    "rather than one blob."
)

HOW_BLOCKS_ARE_PICKED = (
    "If asked why THESE blocks and not others — the grid is deliberate, "
    "the assignment is a draw, and the draw is constrained.\n\n"
    "First the tile is cut into a 12 by 12 grid of squares. The grid is "
    "regular, not drawn around the features, so nobody can accuse us of "
    "arranging the boundaries to flatter the result.\n\n"
    "Then each whole square is dealt into one of the three piles. Whole "
    "squares, never split — that is the entire point. If a square could be "
    "split, a pit could end up in training while the pit ten metres away "
    "ended up in test, and the model would effectively have seen the answer.\n"
    "\n"
    "The deal itself is random, from a fixed seed so it reproduces exactly. "
    "But it is not a plain shuffle: it balances on the NUMBER OF FEATURES, "
    "not on area. Pits are not spread evenly — some squares hold a dozen "
    "and some hold none — so splitting by area would be a lottery on how "
    "many pits each pile happened to get. Dealing until each pile holds about "
    "70, 15 and 15 percent of the pits gives three piles that are comparable "
    "to each other.\n\n"
    "So: regular grid so the boundaries are not chosen, whole squares so "
    "neighbours stay together, random draw so we are not choosing either, and "
    "balanced on feature count so the three piles are worth comparing.\n\n"
    "The honest limitation: it is one draw. A different seed gives a "
    "different map. What protects the result is not the seed, it is that the "
    "pieces are blocks of ground rather than individual pits."
)

#: (slide title, marker phrase that means it is already there, text)
NOTE_APPENDS = [
    ("Preprocessing — the spatial block split",
     "the grid is deliberate", HOW_BLOCKS_ARE_PICKED),
    ("Data QA — where this started", "height bins were chosen", BINS),
    ("Preprocessing – Annotations – Standard Values",
     "three piles of ground", TRAIN_VAL_TEST),
    ("Preprocessing — resolving overlaps",
     "the word for painting a shape", BURN_ORDER),
    ("Measured pit morphology", "seen from directly above", PLAN_VIEW),
]
