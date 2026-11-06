"""S3 of framework 4.8. Georegistration offset of each optical source at road intersections from the lidar roads.

Purpose. Two modes.
  --template  Find road intersections in the annotated roads layer (true junctions where three or more road
              arms meet. End-to-end joints of one road are dropped), keep the ones inside 9t, draw n_intersections (10) at random with the master seed, and
              write a measurement sheet per source. A person fills image_x and image_y in QGIS by clicking the
              intersection centre on the photo, blind to everything but the photo and the lidar road line.
  default     Read the filled sheet and report per source the median, maximum and RMSE of the offset in metres,
              the mean shift, and whether the source is registered within max_offset_m (5 m).
Inputs.
  qgis/annotations/annotations_proj_v2.gpkg layer roads (held)
  expansions/4_modalities/4_8_leafoff_optical/results/tables/leafoff_offsets_measured_9t.csv (filled sheet, assumed)
Outputs.
  expansions/4_modalities/4_8_leafoff_optical/results/tables/leafoff_offsets_measured_9t.csv  (template mode)
  expansions/4_modalities/4_8_leafoff_optical/results/tables/leafoff_offsets_summary_9t.csv   (default mode)
Run.
  python expansions/4_modalities/4_8_leafoff_optical/src/_leafoff_georeg_offset_9t.py --template --sources pema_venango_2020 naip
  python expansions/4_modalities/4_8_leafoff_optical/src/_leafoff_georeg_offset_9t.py [--measured CSV]
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

import _leafoff_kit_4_8 as lk


def intersections(lines, bbox, snap: float = 0.5) -> np.ndarray:
    """True road junctions. A node's degree is the number of road arms that leave it. A line contributes one arm
    at its own endpoint and two where the node lies inside it. Only nodes of degree three or more are kept
    (T, X and star junctions). Two lines that simply meet end to end (degree two) are pass-through joints of
    one road, not intersections, and are dropped (4.8-01 minor). Nodes are deduplicated at snap metres."""
    from shapely import get_coordinates
    from shapely.geometry import Point
    from shapely.strtree import STRtree
    lines = list(lines)
    cand = {}
    for g in lines:
        c = get_coordinates(g)
        for p in (c[0], c[-1]):
            cand.setdefault((round(p[0] / snap), round(p[1] / snap)), (float(p[0]), float(p[1])))
    tree = STRtree(lines)
    for i, g in enumerate(lines):
        for j in tree.query(g):
            if j <= i:
                continue
            for p in get_coordinates(g.intersection(lines[j])):
                cand.setdefault((round(p[0] / snap), round(p[1] / snap)), (float(p[0]), float(p[1])))
    keep = []
    for x, y in cand.values():
        pt = Point(x, y)
        deg = 0
        for j in tree.query(pt.buffer(snap)):
            g = lines[j]
            if g.distance(pt) > snap:
                continue
            c = get_coordinates(g)
            closed = np.hypot(*(c[0] - c[-1])) <= snap
            at_end = min(np.hypot(c[0][0] - x, c[0][1] - y), np.hypot(c[-1][0] - x, c[-1][1] - y)) <= snap
            deg += 1 if (at_end and not closed) else 2
        if deg >= 3:
            keep.append((x, y))
    xy = np.array(keep, float).reshape(-1, 2)
    x0, y0, x1, y1 = bbox
    return xy[(xy[:, 0] >= x0) & (xy[:, 0] <= x1) & (xy[:, 1] >= y0) & (xy[:, 1] <= y1)]


def summary(m: pd.DataFrame, max_off: float) -> pd.DataFrame:
    m = m.dropna(subset=["image_x", "image_y"]).copy()
    m["dx"], m["dy"] = m.image_x - m.lidar_x, m.image_y - m.lidar_y
    m["off_m"] = np.hypot(m.dx, m.dy)
    rows = []
    for sid, g in m.groupby("source_id"):
        rows.append({"source_id": sid, "n_points": len(g), "median_m": g.off_m.median(), "max_m": g.off_m.max(),
                     "rmse_m": float(np.sqrt((g.off_m ** 2).mean())), "mean_dx_m": g.dx.mean(), "mean_dy_m": g.dy.mean(),
                     "registered": bool(g.off_m.median() <= max_off)})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    import geopandas as gpd
    cfg = lk.load_cfg()
    pr = cfg["prereg"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--template", action="store_true")
    ap.add_argument("--sources", nargs="*", default=[])
    ap.add_argument("--annotations", default=None)
    ap.add_argument("--measured", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else lk.resolve(cfg["outputs"]["tables"])
    out.mkdir(parents=True, exist_ok=True)
    spec = cfg["inputs"]["offsets"]
    if a.template:
        if not a.sources:
            raise ValueError("--template needs --sources")
        ann = lk.need(Path(a.annotations) if a.annotations else lk.resolve(cfg["inputs"]["annotations"]), "annotations")
        roads = gpd.read_file(ann, layer="roads")
        lk.ek.assert_crs(roads, cfg["crs"])
        xy = intersections(list(roads.geometry), cfg["areas"]["9t"])
        if len(xy) < pr["n_intersections"]:
            raise ValueError(f"only {len(xy)} road intersections in 9t, need {pr['n_intersections']}")
        pick = xy[np.random.default_rng(pr["master_seed"]).choice(len(xy), pr["n_intersections"], replace=False)]
        t = pd.DataFrame([{"source_id": s, "point_id": i, "lidar_x": p[0], "lidar_y": p[1], "image_x": np.nan, "image_y": np.nan}
                          for s in a.sources for i, p in enumerate(pick)])
        f = out / "leafoff_offsets_measured_9t.csv"
        if f.exists():
            raise FileExistsError(f"{f} exists and may hold measurements. Move it before writing a new template")
        t.to_csv(f, index=False)
        lk.prov(out, "leafoff_georeg_template_9t", inputs=[ann], outputs=[f], seeds={"master": pr["master_seed"]})
        print(f"{f}  {len(pick)} intersections x {len(a.sources)} sources (of {len(xy)} found)")
        return 0
    mp = lk.need(Path(a.measured) if a.measured else lk.resolve(spec), "filled offset sheet", spec)
    m = pd.read_csv(mp)
    miss = [c for c in spec["schema"] if c not in m.columns]
    if miss:
        raise ValueError(f"{mp} lacks {miss}")
    s = summary(m, pr["max_offset_m"])
    f = out / "leafoff_offsets_summary_9t.csv"
    s.to_csv(f, index=False)
    lk.prov(out, "leafoff_georeg_summary_9t", inputs=[mp], outputs=[f], params={"max_offset_m": pr["max_offset_m"]})
    print(s.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
