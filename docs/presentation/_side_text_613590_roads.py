# -*- coding: utf-8 -*-
"""Side text for the three 613590 road slides. Imported by the builder.

The captions used to be baked into the top of each PNG. They are back as slide
text in the left column, which is where they were asked for: re-wrappable,
readable at size, and not printing through the figure the way the road-network
one did.

Wording is the figures' own, from _build_613590_outcomes.py lines 196, 212 and
246, so nothing is reworded on its way out of the image.
"""
from __future__ import annotations

BULLET = "•  "

#: title -> (kicker, [bullets])
ROAD_SIDE_TEXT = {
    "Second tile, 613590 – The Road Network It Drew": (
        "A tile no road model ever trained on",
        ["3,693 segments drawn, 231.4 km of road",
         "Threshold 0.30",
         "Faithful vectorisation — strip and trace, nothing invented"],
    ),
    "Second tile, 613590 – Generated Roads vs TIGER": (
        "What the public road layer knows about",
        # Read off the original figure's own caption band rather than
        # recomputed, so the slide cannot drift from the image beside it.
        ["Model 231.4 km against TIGER 40.0 km",
         "5.8x more road than the public layer carries"],
    ),
    "Second tile, 613590 – Roads Found and Missed": (
        "Scored on the hard half of the truth",
        ["613590_added_r2 only, at threshold 0.50",
         "1,162 of 1,496 chunks found — 0.777",
         "The other 4,004 chunks are a previous model's output that a human "
         "vetted. Every model scores 0.96+ on those, so they rank nothing and "
         "are excluded."],
    ),
}
