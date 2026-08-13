"""Calibrate the drainage vectorizer on 9t, where hand-drawn drainage exists.

The 613590 drainage package is built by thresholding + skeletonizing
`drainage_prob` and pruning. Those prune settings were carried over from the
road pipeline and never checked against drainage ground truth. This sweeps them
on 9t and scores each config against `annotations_proj.gpkg` layer `drainage`
using the same Heipke/Wiedemann buffer matching `_road_optimize.py` uses for
roads, so the drainage number is comparable to the road F1.

Scored on the 9t HELD-OUT test blocks only (`pit_blocks_9t.gpkg` split == test),
matching the road harness — tuning on everything would just re-fit the model's
training ground.

Output: <9t>/drainage_extract_calib_9t_1m.json + a printed leaderboard.
"""
from __future__ import annotations

import itertools
import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from scipy import ndimage as ndi
from shapely.ops import unary_union

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, path_for  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "s5_eval"))
from _road_optimize import island_filter, lines_from_skel, prune_merge, skeleton  # noqa: E402

R9 = path_for("nine_t")
PROB = path_for("models") / "drainage" / "unet_1m" / "drainage_prob.tif"
TOL = 8.0   # buffer match tolerance (m) — same as the road harness


def extract(pdrain, tf, t, min_px, spur, island):
    from skimage.morphology import remove_small_objects
    m = pdrain >= t
    m = ndi.binary_closing(m, np.ones((3, 3)))
    m = ndi.binary_fill_holes(m)
    m = remove_small_objects(m, min_size=min_px)
    if not m.any():
        return []
    segs = prune_merge(lines_from_skel(skeleton(m, "zhang"), tf), spur)
    return island_filter(segs, island)


def score(pred, gt, region):
    """Heipke/Wiedemann completeness / correctness / quality / F1."""
    if not len(pred) or not len(gt):
        return dict(comp=0.0, corr=0.0, f1=0.0, qual=0.0, km=0.0, n=0)
    pg = gpd.GeoSeries(pred, crs=DST_CRS)
    pg = pg[pg.intersects(region)]
    if not len(pg):
        return dict(comp=0.0, corr=0.0, f1=0.0, qual=0.0, km=0.0, n=0)
    pu = pg.union_all()
    gu = gt.union_all()
    gt_in = gt.intersection(pu.buffer(TOL)).length.sum()
    pr_in = pg.intersection(gu.buffer(TOL)).length.sum()
    comp = gt_in / gt.length.sum() if gt.length.sum() else 0.0
    corr = pr_in / pg.length.sum() if pg.length.sum() else 0.0
    f1 = 2 * comp * corr / (comp + corr) if (comp + corr) else 0.0
    qual = f1 / (2 - f1) if f1 else 0.0
    return dict(comp=round(comp, 3), corr=round(corr, 3), f1=round(f1, 3),
                qual=round(qual, 3), km=round(pg.length.sum() / 1000, 2), n=len(pg))


def main() -> int:
    with rasterio.open(PROB) as r:
        pdrain = np.clip(r.read(1).astype(np.float32), 0, 1)
        tf = r.transform

    blocks = gpd.read_file(R9 / "pit_blocks_9t.gpkg")
    test = blocks[blocks.split == "test"]
    region = unary_union(test.geometry.values)
    gt = gpd.read_file(path_for("truth") / "annotations_proj.gpkg",
                       layer="drainage")
    if gt.crs is None:
        gt = gt.set_crs(DST_CRS)
    gt = gt.to_crs(DST_CRS)
    gt = gt[gt.intersects(region)].copy()
    gt["geometry"] = gt.geometry.intersection(region)
    gt = gt[~gt.is_empty]
    print(f"GT drainage on 9t test blocks: {len(gt)} lines, "
          f"{gt.length.sum()/1000:.2f} km over "
          f"{region.area/1e6:.2f} km2 ({gt.length.sum()/1000/(region.area/1e6):.2f} km/km2)")

    grid = list(itertools.product(
        (0.30, 0.40, 0.50, 0.60),   # threshold
        (20, 60),                   # min_px
        (10.0, 20.0),               # spur prune (m)
        (0.0, 40.0, 100.0),         # island filter (m)
    ))
    print(f"sweeping {len(grid)} configs...\n")
    rows = []
    for t, mp, sp, isl in grid:
        segs = extract(pdrain, tf, t, mp, sp, isl)
        s = score(segs, gt, region)
        s.update(t=t, min_px=mp, spur=sp, island=isl)
        rows.append(s)
        print(f"  t={t:.2f} min_px={mp:3d} spur={sp:4.0f} island={isl:5.0f}  "
              f"comp {s['comp']:.3f}  corr {s['corr']:.3f}  F1 {s['f1']:.3f}  "
              f"{s['km']:6.2f} km  n={s['n']}")

    rows.sort(key=lambda r: -r["f1"])
    best = rows[0]
    print("\n=== top 5 by F1 ===")
    for r in rows[:5]:
        print(f"  F1 {r['f1']:.3f}  comp {r['comp']:.3f} corr {r['corr']:.3f}  "
              f"t={r['t']} min_px={r['min_px']} spur={r['spur']} island={r['island']}")

    cur = [r for r in rows if (r["t"], r["min_px"], r["spur"], r["island"])
           == (0.50, 60, 20.0, 100.0)]
    if cur:
        c = cur[0]
        print(f"\ncurrent package settings (t=0.50 min_px=60 spur=20 island=100): "
              f"F1 {c['f1']:.3f}  comp {c['comp']:.3f}  corr {c['corr']:.3f}  "
              f"{c['km']:.2f} km")
        print(f"best  : F1 {best['f1']:.3f}  comp {best['comp']:.3f}  "
              f"corr {best['corr']:.3f}  {best['km']:.2f} km")

    out = R9 / "drainage_extract_calib_9t_1m.json"
    out.write_text(json.dumps(
        {"tol_m": TOL, "gt_km": round(gt.length.sum() / 1000, 2),
         "gt_lines": len(gt), "region_km2": round(region.area / 1e6, 2),
         "best": best, "current": cur[0] if cur else None, "all": rows},
        indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
