# -*- coding: utf-8 -*-
"""Build the 15-minute talk (v20) from v19 by keeping a subset of slides.

v19 IS NOT EDITED. It is copied, and slides outside KEEP are dropped. Order
follows v19. Structure: setup (4) -> methodology (6) -> results (5) -> close (1)
plus references. Data QA (v19 9-21), the eleven-derivative tour (22-31), the
corn-row slides (39-44), annotation inventory (46-54), and backups are cut.

Run (system Python, python-pptx lives there):
    python docs/presentation/v20_15min/_build_v20_15min_from_v19.py
Writes: docs/presentation/v20_15min/WellSight_Presentation v20 15min.pptx
"""
from pathlib import Path
from pptx import Presentation

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "v19_maps_and_plain_results" / "WellSight_Presentation v19.pptx"
DST = HERE / "WellSight_Presentation v20 15min.pptx"

# v19 slide numbers (1-based)
KEEP = [
    1,   # title
    2,   # the problem
    5,   # why lidar
    6,   # study area
    8,   # pipeline overview
    33,  # RRIM
    45,  # why we drew our own labels
    55,  # spatial block split
    58,  # the network
    61,  # how we score
    62,  # pits
    66,  # three detectors side by side
    69,  # unseen tile
    73,  # what it does not say
    74,  # what would move it next
    78,  # references
]

prs = Presentation(str(SRC))
lst = prs.slides._sldIdLst
ids = list(lst)
for i, sld in enumerate(ids, 1):
    if i not in KEEP:
        prs.part.drop_rel(sld.rId)
        lst.remove(sld)
prs.save(str(DST))
print("kept", len(KEEP), "->", DST)
