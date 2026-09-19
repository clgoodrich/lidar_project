"""One place for the things every talk figure has to agree on.

Three builders were each carrying their own answer to the same two questions,
and all three answers were wrong in the same way:

HOW RRIM IS DRAWN
-----------------
`rrim_openness_*` is multibandcolor with NoEnhancement in `qgis/wellsight.qgz`,
which means the stored bytes reach the screen untouched. Every builder was
applying a 2-98 percentile stretch of its own on top of that, so the RRIM in
one figure did not match the RRIM in the next, and none of them matched QGIS.
`read_rrim` here is the single answer: raw bytes, divided by 255.

THE PROBABILITY RAMP
--------------------
The probability surfaces were drawn on an orange-to-dark-red ramp. Two things
wrong with it. It is the same family of colour RRIM itself is built from, so a
prediction laid beside or over terrain read as more terrain; and running a warm
ramp next to the classification figures, which use green for vegetation, puts a
red and a green in the same talk carrying different meanings, which is what the
colourblind rule in CLAUDE.md exists to stop.

`CM_PROB` is a single-hue blue sequential ramp built on the project's accent,
`#1F5FA8`, so it reads as "the model said so" wherever it appears and never
competes with the terrain underneath.

    stop        hex        relative luminance
    0.00        #eef3fa    0.891
    0.25        #9dbde0    0.503
    0.50        #4a87c8    0.234
    0.75        #1f5fa8    0.112
    1.00        #0d3057    0.029

Monotonically darkening, which is the check that matters for a sequential ramp
-- the validator's categorical checks do not apply to one. It stays legible in
greyscale and under every CVD simulation because the signal is lightness.
"""
from __future__ import annotations

import numpy as np
import rasterio
from matplotlib.colors import LinearSegmentedColormap
from rasterio.windows import from_bounds

#: Sequential, one hue, light to dark. See the table above.
PROB_STOPS = ["#eef3fa", "#9dbde0", "#4a87c8", "#1f5fa8", "#0d3057"]
CM_PROB = LinearSegmentedColormap.from_list("prob", PROB_STOPS)


def read_rrim(path, bounds):
    """RRIM exactly as QGIS shows it: multibandcolor, NoEnhancement.

    No stretch. The bytes in the file are the pixels on the screen.
    """
    with rasterio.open(path) as r:
        w = from_bounds(*bounds, transform=r.transform)
        a = r.read(window=w, boundless=True,
                   fill_value=np.nan).astype("float32")
    return np.clip(np.moveaxis(a[:3] / 255.0, 0, -1), 0, 1)
