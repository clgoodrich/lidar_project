# -*- coding: utf-8 -*-
"""Broad capability statements for the NISAR slide. Imported by the builder.

WHAT WAS ALREADY RIGHT
----------------------
The slide already leads with the limitation and already carries the evidence
and the caveat, and all three check out against the records:

    cannot find a pit   10 m GCOV, 80 m GUNW, pits average 32 m2
    fall pair           2025-10-28 -> 11-09, coherence 0.50, 94% of pixels
                        above 0.3  (analysis_log line 4901)
    winter pair         2026-01-08 -> 01-20, coherence 0.14, 0% above 0.3
    caveat              beta pre-calibration, n = 1 pair

Only the January granules are still on disk; the fall pair was deleted after
measurement, which is why the claim looks unsupported from a directory listing.
It is not. BACKLOG line 201 already records that one pair is a hypothesis, not
a proof, and the slide's last bullet says so.

WHAT WAS MISSING
----------------
Everything on the slide is about whether the instrument WORKS. Nothing says
what it would be FOR. Two capabilities are missing and both are the reason a
reviewer would fund it:

  * it turns a long candidate list into a work order, by ranking on whether
    the ground is actually moving
  * it covers ground we have no LiDAR for, so it can say where flying is worth
    the money

The subtitle also described the instrument rather than the idea. It now says
the idea, and the instrument line moves into the first bullet where it belongs.
"""
from __future__ import annotations

BULLET = "•  "
NISAR_TITLE = "Further research — watching what we found"

#: (old, new, "body" | "notes") applied like every other edit
NISAR_EDITS = [
    ("NISAR: L-band radar, free, over the same ground every 12 days",
     "LiDAR says where the wells are. NISAR can say which ones are still "
     "moving.",
     "body"),
    (BULLET + "It cannot find a pit — 10 m backscatter, 80 m InSAR, "
     "against pits averaging 32 m²",
     BULLET + "L-band radar, free, same ground every 12 days — but it "
     "cannot find a pit. 10 m backscatter, 80 m InSAR, against pits "
     "averaging 29 m²",
     "body"),
    # Two evidence bullets merged into one. Adding capability statements took
    # the slide to eight bullets, which nobody reads off a projector; the
    # seasonal contrast is one idea and reads better as one line anyway.
    (BULLET + "Already tested here: a snow-free fall pair over 9t held "
     "coherence 0.50, 94% of pixels usable",
     BULLET + "Tested here: a snow-free autumn pair held coherence 0.50 with "
     "94% of pixels usable, mid-winter only 0.14 — pairs must be leaf-off "
     "but snow-free",
     "body"),
    (BULLET + "Mid-winter failed at 0.14 — snow and freeze-thaw, so "
     "pairs must be leaf-off but snow-free",
     None, "body"),
]

#: The new bullets go directly after this one, so the caveat stays last.
NISAR_ANCHOR = (BULLET + "It can measure whether the ground over them is "
                "moving, to the millimetre")

#: Appended as new bullets on the same slide, in this order, formatted from an
#: existing bullet so they cannot drift from the slide's own styling.
NISAR_NEW_BULLETS = [
    "It turns a long candidate list into a work order — the wells where "
    "the ground is measurably moving go to the top of the visit list",
    "It covers ground we have no LiDAR for, so it can say where flying is "
    "worth the money",
]

NISAR_NOTE = (
    "The broad version, if someone asks what this is actually for.\n\n"
    "What it cannot do: find pits. A pit is about 6 m across, one backscatter "
    "pixel is 10 m and one displacement pixel is 80 m. That is geometry. No "
    "amount of processing fixes it, so we do not claim it.\n\n"
    "What it can do, in four statements.\n\n"
    "One. Ask whether ground we have already found is moving. Settlement over "
    "a failing well is an 80 m question, and 80 m is exactly what the "
    "displacement product gives. The question changes from where is the pit "
    "to which one is still settling.\n\n"
    "Two. Do it repeatedly, for free, without flying anything. Every twelve "
    "days, indefinitely, over the whole state. The LiDAR is one snapshot that "
    "cost a survey contract. This is a time series.\n\n"
    "Three. Rank what we hand over. If a regulator gets four hundred probable "
    "wells, the ones where the ground is moving go first. That is the "
    "difference between a list and a work order.\n\n"
    "Four. Cover ground we have no LiDAR for. Our detection needs a tile "
    "flown. Radar covers everywhere, so it can tell us where flying is worth "
    "the money.\n\n"
    "And be honest about the limit: coherence is the whole game. Snow, "
    "freeze-thaw between passes and dense summer canopy all degrade it. "
    "L-band handles vegetation far better than the C-band alternatives, which "
    "is why this satellite and not Sentinel-1, but better is not immune. We "
    "have one good pair. That is a hypothesis, not a proof."
)
