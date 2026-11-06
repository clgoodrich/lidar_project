"""5.5 S3. Ingest surveyed pad outlines (GNSS or drone) and write reference areas under each boundary definition.

Purpose
    Reads the survey outlines in any CRS, transforms to EPSG:6346 and asserts the result. Builds three boundary
    definitions per pad, the same ones the model polygon is clipped to in S4.
        disturbed   the outline as surveyed minus annotated pits (when subtract_pits is set)
        graded      the outline where definition == graded, else NaN (needs a graded outline in the survey)
        with_road   disturbed plus annotated access road buffered by road_buffer_m within road_window_m of the edge
    Drone outlines digitised by two people give a digitiser IoU per pad. Survey accuracy (h_acc_m) is asserted to be at
    most 0.10 m, else the pad is flagged. Input hashes go to the provenance file.

Inputs (config_5_5.json)
    survey       assumed, @data/_source/pad_survey/pad_outlines_survey.gpkg (schema in config)
    annotations  @truth/annotations_proj.gpkg (pit_inside, roads)
Outputs
    expansions/5_tasks/5_5_polygon_area_cost/data/processed/pad_reference_area_9t.csv (+ _PROVENANCE.json beside it)
Run
    python expansions/5_tasks/5_5_polygon_area_cost/src/_padarea_survey_ingest_9t.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _padarea_geometry_tools as gt  # noqa: E402

th, ek = gt.th, gt.ek
MAX_ACC_M = 0.10


def reference_areas(sv, pits, roads, cfg) -> pd.DataFrame:
    th.require_columns(sv, ["pad_id", "definition"], "survey")
    sv = gt.clean(sv)
    pu = pits.geometry.union_all() if pits is not None and len(pits) else None
    ru = roads.geometry.buffer(cfg["road_buffer_m"]).union_all() if roads is not None and len(roads) else None
    rows = []
    for pid, g in sv.groupby("pad_id"):
        dig = g["digitiser"].dropna().unique() if "digitiser" in g else []
        main = g[g.definition != "graded"]
        outline = (main if len(main) else g).geometry.iloc[0]
        dig_iou = np.nan
        if len(dig) >= 2:
            a = g[g.digitiser == dig[0]].geometry.union_all()
            b = g[g.digitiser == dig[1]].geometry.union_all()
            dig_iou = a.intersection(b).area / a.union(b).area
        disturbed = outline.difference(pu) if (pu is not None and cfg.get("subtract_pits")) else outline
        graded = g[g.definition == "graded"].geometry.union_all() if (g.definition == "graded").any() else None
        with_road = disturbed
        if ru is not None:
            with_road = disturbed.union(ru.intersection(outline.buffer(cfg["road_window_m"])))
        acc = float(g["h_acc_m"].max()) if "h_acc_m" in g else np.nan
        rows.append(dict(pad_id=pid, A_ref_disturbed=disturbed.area, A_ref_graded=graded.area if graded else np.nan,
                         A_ref_with_road=with_road.area, digitiser_iou=dig_iou, h_acc_m=acc,
                         acc_flag=int(np.isfinite(acc) and acc > MAX_ACC_M),
                         method=g["method"].iloc[0] if "method" in g else "",
                         survey_date=g["survey_date"].iloc[0] if "survey_date" in g else ""))
    return th.tag(pd.DataFrame(rows), "a", "reference_survey")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    sp = th.inp(cfg, "survey")
    sv = th.read_vector(sp)                       # reprojects and asserts EPSG:6346
    ann = th.inp(cfg, "annotations")
    pits = gt.clean(th.read_vector(ann, layer="pit_inside"))
    roads = th.read_vector(ann, layer="roads")
    R = reference_areas(sv, pits, roads, cfg)
    ek.assert_unique(R, "pad_id")
    out = th.outp(cfg, "reference_area")
    R.to_csv(out, index=False)
    ek.write_provenance(out.parent, inputs=[sp, ann], outputs=[out], params={"stage": "5.5 S3"})
    print(f"{len(R)} surveyed pads, {int(R.acc_flag.sum())} above {MAX_ACC_M} m accuracy\nwrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
