"""Is the vendor's ground classifier bridging over our pits, and what does it cost?

THE CLAIM UNDER TEST
--------------------
The sniff test found that points below the interpolated ground surface are 2.6x
more common inside annotated pit floors than elsewhere. The suspicion: the
vendor's ground classifier -- an Axelsson-style progressive TIN densification,
which is what TerraScan, LAStools and PDAL's SMRF/PMF all implement variants of
-- seeds itself on local low points in a coarse grid, then only ever adds points
that sit close to the growing TIN. A pit a few metres across and a metre or two
deep never earns a seed of its own, the TIN spans straight over it from rim to
rim, and the real floor returns fail the iteration-distance test from below. They
end up in class 1.

Every terrain product in this project is built from class 2. If that is what
happened, our DEM pit floors are shallower than the real ones and every
depth-derived channel is damped.

WHY THIS IS NOT A CIRCULAR TEST
-------------------------------
Reclassifying points because they sit below the TIN and then showing the DEM gets
deeper proves nothing -- it is true by construction. So the script runs three
independent lines of evidence, in order of how much they can be argued with:

  PART 1  Ground-point density inside pit floors vs the ring around them.
          Pure counting. No height model, no reclassification, no threshold.
          If the classifier treated a pit like ordinary terrain, the density
          ratio is ~1. A ratio well under 1 means class 2 thins out exactly
          where the pit is, which is the bridging signature.

  PART 2  Are the withheld points physically ground-like? Measured against
          genuine class-2 ground in the same neighbourhood: local planarity,
          intensity, scan angle, and the vendor's own noise flag. Real ground
          returns look like ground. Noise does not.

  PART 3  Only then, rebuild the DEM both ways and measure what the pit depth
          actually changes by. With a negative control: the identical rule run
          on non-pit ground in the same crop. If the rule reclaims as much
          elsewhere as it does inside pits, it is just eating low vegetation
          and the whole thing is void.

THE RECLAMATION RULE
--------------------
Deliberately conservative, and modelled on the low-point filter it is meant to
undo. TerraScan's "low points" routine rejects a point if it sits more than some
distance below its neighbours, in either "single point" or "group of points"
mode. Run that backwards: a candidate is only accepted as ground if it is NOT an
isolated low outlier.

    class 1, and not withheld/overlap                 # vendor left it undecided
    HAG < -0.05 m                                     # below the current TIN
    ReturnNumber == NumberOfReturns                   # terminal return
    >= MIN_NBRS of its neighbours within NBR_R are    # coherent, not a stray
        also candidates
    vertical spread of those neighbours < SPREAD_M    # a surface, not a plume

METHOD
------
PDAL CLI via subprocess with a pipeline JSON -- the Python bindings do not
function in this environment (CLAUDE.md). One pass per tile computes height
above the vendor's ground surface for every point; everything after that is
numpy. The DEM is rebuilt the way phase 1 builds it, Delaunay TIN with linear
interpolation across facets, so the comparison is against the real product and
not a proxy.

Run:
    python notebooks/wellsight_v2/s7_analysis/_reclaim_ground_pit_depth_experiment.py
    ... --tiles 621594 616591 --figures
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import Delaunay, cKDTree
from shapely.geometry import box

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "_source" / "lidar" / "westernpa"
ANN = ROOT / "qgis" / "annotations" / "annotations_proj.gpkg"
OUT = ROOT / "data" / "9t" / "results" / "ground_reclassification"
FIGDIR = OUT / "figures"
PDAL = "pdal"

RES = 0.5           # DEM cell size, matching the project's 0.5 m products
PAD_M = 40.0        # margin around each pit cluster, so the TIN has real rim
RING_IN = 2.0       # the control annulus around a floor: 2 m ...
RING_OUT = 8.0      # ... out to 8 m. Rim and shoulder, not floor.
FAR_M = 20.0        # "far field" = further than this from any annotated floor

#: reclamation rule
HAG_BELOW = -0.05
NBR_R = 2.0
MIN_NBRS = 3
SPREAD_M = 0.50


def run_pipeline(stages, label, timeout=3600):
    """Write the pipeline to a temp file and shell out. See CLAUDE.md."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f, indent=2)
        tmp = f.name
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True,
                       timeout=timeout)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stdout[-1500:])
        print(r.stderr[-1500:])
        raise SystemExit(f"{label} failed, exit {r.returncode}")
    return r


def find_tile(code):
    """Resolve a tile code like 621594 to its source file."""
    hits = sorted(SRC.glob(f"*_17T??{code}.laz")) + \
        sorted(SRC.glob(f"*_17T??{code}.copc.laz"))
    if not hits:
        raise SystemExit(f"no source file for tile {code} in {SRC}")
    return hits[0]


def load_tile(laz):
    """One PDAL pass: height of every point above the vendor's ground surface.

    hag_nn measures each point against the nearest CLASS 2 returns, so it is
    unaffected by how the non-ground points are classified. Inside a bridged pit
    the nearest ground is the rim, so a floor return reads strongly negative --
    which is the whole point.
    """
    tmp = Path(tempfile.gettempdir()) / f"_reclaim_{laz.stem}.las"
    t0 = time.time()
    run_pipeline([
        str(laz),
        {"type": "filters.hag_nn", "count": 8, "allow_extrapolation": True},
        {"type": "writers.las", "filename": str(tmp),
         "extra_dims": "HeightAboveGround=float32", "compression": "false"},
    ], "hag")
    print(f"    hag_nn {time.time() - t0:.0f}s")

    import laspy
    las = laspy.read(str(tmp))
    d = {
        "x": np.asarray(las.x), "y": np.asarray(las.y), "z": np.asarray(las.z),
        "cls": np.asarray(las.classification).astype("int16"),
        "hag": np.asarray(las.HeightAboveGround, dtype="float64"),
        "rn": np.asarray(las.return_number).astype("int16"),
        "nr": np.asarray(las.number_of_returns).astype("int16"),
        "inten": np.asarray(las.intensity).astype("float64"),
    }
    # point format 6+ stores a scaled scan angle; older formats a rank
    for attr in ("scan_angle", "scan_angle_rank"):
        if hasattr(las, attr):
            a = np.asarray(getattr(las, attr), dtype="float64")
            d["ang"] = a * 0.006 if attr == "scan_angle" else a
            break
    else:
        d["ang"] = np.zeros_like(d["z"])
    for flag in ("withheld", "overlap"):
        try:
            d[flag] = np.asarray(getattr(las, flag)).astype(bool)
        except Exception:
            d[flag] = np.zeros(d["z"].size, dtype=bool)
    tmp.unlink(missing_ok=True)
    return d


def subset(d, i):
    return {k: v[i] for k, v in d.items()}


def reclaim(d, permissive=False):
    """Apply the rule. Returns the keep mask and a per-stage attrition count.

    ``permissive`` drops the coherence and planarity tests and accepts every
    terminal class-1 return below the TIN. It exists so the conclusion cannot be
    dismissed as an artefact of a strict rule -- it is the most generous
    reclamation the data allows, noise included.
    """
    steps = {}
    m = (d["cls"] == 1) & ~d["withheld"] & ~d["overlap"]
    steps["class 1, not withheld/overlap"] = int(m.sum())
    m &= np.isfinite(d["hag"]) & (d["hag"] < HAG_BELOW)
    steps[f"below the TIN (HAG < {HAG_BELOW} m)"] = int(m.sum())
    m &= d["rn"] == d["nr"]
    steps["terminal return"] = int(m.sum())

    out = np.zeros_like(m)
    if permissive:
        steps["PERMISSIVE: coherence and spread tests skipped"] = int(m.sum())
        return m, steps
    if m.sum() < 4:
        steps[f">= {MIN_NBRS} candidate neighbours within {NBR_R} m"] = 0
        steps[f"and vertical spread < {SPREAD_M} m"] = 0
        return out, steps
    # coherence: a real missed floor is a patch of them, an outlier is alone
    idx = np.flatnonzero(m)
    xy = np.c_[d["x"][idx], d["y"][idx]]
    nbrs = cKDTree(xy).query_ball_point(xy, r=NBR_R)
    zc = d["z"][idx]
    nnb = np.fromiter((len(p) - 1 for p in nbrs), int, len(nbrs))
    spread = np.fromiter(
        ((zc[p].max() - zc[p].min()) if len(p) > 1 else 9e9 for p in nbrs),
        float, len(nbrs))
    steps[f">= {MIN_NBRS} candidate neighbours within {NBR_R} m"] = \
        int((nnb >= MIN_NBRS).sum())
    keep = (nnb >= MIN_NBRS) & (spread < SPREAD_M)
    steps[f"and vertical spread < {SPREAD_M} m"] = int(keep.sum())
    out[idx[keep]] = True
    return out, steps


def planarity(x, y, z, sel, nbr_mask, r=2.0, min_pts=6, cap=1500, seed=42):
    """Median residual to a plane fitted through the point's OWN cohort.

    The cohort matters. Fitting a class-2 point's plane through whatever happens
    to be within 2 m pulls in tree returns and reports metres of residual for
    perfectly flat ground. Ground is compared against ground, reclaimed against
    reclaimed-plus-ground -- the surface each one would actually belong to.
    """
    ii = np.flatnonzero(sel)
    if ii.size == 0:
        return np.nan, 0
    if ii.size > cap:
        ii = np.random.default_rng(seed).choice(ii, cap, replace=False)
    nb_idx = np.flatnonzero(nbr_mask)
    if nb_idx.size < min_pts:
        return np.nan, 0
    tree = cKDTree(np.c_[x[nb_idx], y[nb_idx]])
    res = []
    for i in ii:
        nb = nb_idx[tree.query_ball_point([x[i], y[i]], r=r)]
        nb = nb[nb != i]
        if nb.size < min_pts:
            continue
        A = np.c_[x[nb] - x[i], y[nb] - y[i], np.ones(nb.size)]
        try:
            c, *_ = np.linalg.lstsq(A, z[nb], rcond=None)
        except np.linalg.LinAlgError:
            continue
        res.append(abs(z[i] - c[2]))
    return (float(np.median(res)) if res else np.nan), len(res)


def tin(x, y, z, gx, gy):
    """DEM by Delaunay TIN + linear interpolation -- phase 1's method."""
    if x.size < 3:
        return np.full((gy.size, gx.size), np.nan)
    f = LinearNDInterpolator(Delaunay(np.c_[x, y]), z)
    X, Y = np.meshgrid(gx, gy)
    return f(X, Y)


def cell_of(x, y, bb, shape):
    """Map point coordinates to row/col in the cluster grid."""
    c = ((x - bb[0]) / RES).astype(int)
    r = ((bb[3] - y) / RES).astype(int)
    ok = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
    return r, c, ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", nargs="+",
                    default=["621594", "616591", "615591", "613591"])
    ap.add_argument("--max-clusters", type=int, default=0,
                    help="0 = all; otherwise cap per tile, for a quick look")
    ap.add_argument("--permissive", action="store_true",
                    help="accept every terminal class-1 return below the TIN")
    ap.add_argument("--figures", type=int, default=0,
                    help="write before/after figures for the N deepest changes")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    pits_all = gpd.read_file(ANN, layer="pit_inside")
    print(f"{len(pits_all)} annotated pit floors project-wide\n")

    per_pit, per_zone, attrition, cache = [], [], {}, []

    for code in args.tiles:
        laz = find_tile(code)
        import laspy
        with laspy.open(laz) as fh:
            h = fh.header
            tb = (h.mins[0], h.mins[1], h.maxs[0], h.maxs[1])
        pits = pits_all[pits_all.centroid.within(box(*tb))].reset_index(drop=True)
        print(f"=== tile {code}  ({laz.name})")
        print(f"    {h.point_count:,} pts, {len(pits)} pit floors in extent")
        if pits.empty:
            continue

        T = load_tile(laz)
        print(f"    loaded {T['z'].size:,} points")
        clusters = list(pits.buffer(PAD_M).union_all().geoms)
        if args.max_clusters:
            clusters = clusters[:args.max_clusters]
        print(f"    {len(clusters)} crop clusters")

        for ci, cl in enumerate(clusters):
            bb = tuple(np.round(cl.bounds, 2))
            sub = pits[pits.centroid.within(cl)]
            sel = ((T["x"] >= bb[0]) & (T["x"] <= bb[2]) &
                   (T["y"] >= bb[1]) & (T["y"] <= bb[3]))
            if sel.sum() < 500:
                continue
            d = subset(T, sel)
            keep, steps = reclaim(d, permissive=args.permissive)
            for k, v in steps.items():
                attrition[k] = attrition.get(k, 0) + v

            g2 = d["cls"] == 2
            gb = g2 | keep

            # ---- zone masks, rasterised then looked up per point ----------
            gx = np.arange(bb[0] + RES / 2, bb[2], RES)
            gy = np.arange(bb[3] - RES / 2, bb[1], -RES)
            shape = (gy.size, gx.size)
            tf = from_origin(bb[0], bb[3], RES, RES)
            floors = sub.union_all()
            ring = floors.buffer(RING_OUT).difference(floors.buffer(RING_IN))
            far = cl.difference(floors.buffer(FAR_M))

            def raster(geom):
                if geom.is_empty:
                    return np.zeros(shape, bool)
                return rasterize([(geom, 1)], out_shape=shape, transform=tf,
                                 dtype="uint8").astype(bool)

            m_floor, m_ring, m_far = raster(floors), raster(ring), raster(far)
            r, c, ok = cell_of(d["x"], d["y"], bb, shape)
            r, c = np.clip(r, 0, shape[0] - 1), np.clip(c, 0, shape[1] - 1)
            in_floor = m_floor[r, c] & ok
            in_ring = m_ring[r, c] & ok
            in_far = m_far[r, c] & ok

            for zname, zm, za in (("floor", in_floor, m_floor.sum() * RES ** 2),
                                  ("ring", in_ring, m_ring.sum() * RES ** 2),
                                  ("far", in_far, m_far.sum() * RES ** 2)):
                if za <= 0:
                    continue
                pg, ng = planarity(d["x"], d["y"], d["z"], zm & g2, g2)
                pr, nr_ = planarity(d["x"], d["y"], d["z"], zm & keep, gb)
                per_zone.append({
                    "tile": code, "cluster": ci, "zone": zname, "area_m2": za,
                    "n_pts": int(zm.sum()),
                    "n_ground": int((zm & g2).sum()),
                    "n_class1": int((zm & (d["cls"] == 1)).sum()),
                    "n_reclaim": int((zm & keep).sum()),
                    "ground_per_m2": (zm & g2).sum() / za,
                    "class1_per_m2": (zm & (d["cls"] == 1)).sum() / za,
                    "reclaim_per_m2": (zm & keep).sum() / za,
                    "med_inten_ground": float(np.median(d["inten"][zm & g2]))
                        if (zm & g2).any() else np.nan,
                    "med_inten_reclaim": float(np.median(d["inten"][zm & keep]))
                        if (zm & keep).any() else np.nan,
                    "med_absang_ground": float(np.median(np.abs(d["ang"][zm & g2])))
                        if (zm & g2).any() else np.nan,
                    "med_absang_reclaim": float(np.median(np.abs(d["ang"][zm & keep])))
                        if (zm & keep).any() else np.nan,
                    "planar_ground": pg, "planar_ground_n": ng,
                    "planar_reclaim": pr, "planar_reclaim_n": nr_,
                })

            # ---- rebuild the DEM both ways --------------------------------
            A = tin(d["x"][g2], d["y"][g2], d["z"][g2], gx, gy)
            B = tin(d["x"][gb], d["y"][gb], d["z"][gb], gx, gy)
            dz = B - A

            for pi, p in sub.iterrows():
                fm = raster(p.geometry)
                rg = p.geometry.buffer(RING_OUT).difference(
                    p.geometry.buffer(RING_IN))
                rm = raster(rg)
                if fm.sum() < 4 or rm.sum() < 4:
                    continue
                pr_, pc, pok = cell_of(d["x"], d["y"], bb, shape)
                here = fm[np.clip(pr_, 0, shape[0] - 1),
                          np.clip(pc, 0, shape[1] - 1)] & pok
                rimA, rimB = np.nanmedian(A[rm]), np.nanmedian(B[rm])
                floA, floB = np.nanpercentile(A[fm], 5), np.nanpercentile(B[fm], 5)
                per_pit.append({
                    "tile": code, "cluster": ci, "pit": int(pi),
                    "area_m2": p.geometry.area, "floor_px": int(fm.sum()),
                    "n_ground_in_floor": int((here & g2).sum()),
                    "n_reclaim_in_floor": int((here & keep).sum()),
                    "depth_A_m": rimA - floA, "depth_B_m": rimB - floB,
                    "d_depth_m": (rimB - floB) - (rimA - floA),
                    "dz_floor_med": float(np.nanmedian(dz[fm])),
                    "dz_floor_min": float(np.nanmin(dz[fm])),
                    "dz_ring_med": float(np.nanmedian(dz[rm])),
                })

            if args.figures:
                cache.append((code, ci, bb, A, B, dz, sub, int(keep.sum()),
                              float(np.nanmin(dz[m_floor])) if m_floor.any()
                              else 0.0))
            if ci % 10 == 0 or ci == len(clusters) - 1:
                print(f"    cluster {ci:>3}/{len(clusters)}  {len(sub):>3} pits"
                      f"  {d['z'].size:>8,} pts  reclaimed {int(keep.sum()):>6,}")
        del T

    pp = pd.DataFrame(per_pit)
    pz = pd.DataFrame(per_zone)
    tag = "permissive" if args.permissive else "strict"
    pp.to_csv(OUT / f"pit_depth_reclaim_{tag}_per_pit.csv", index=False)
    pz.to_csv(OUT / f"ground_reclaim_{tag}_per_zone.csv", index=False)

    if args.figures and cache:
        cache.sort(key=lambda t: t[-1])
        for item in cache[:args.figures]:
            _figure(*item[:8])

    _report(pp, pz, attrition)
    print("\nwrote " + str(OUT / f"pit_depth_reclaim_{tag}_per_pit.csv"))
    print("wrote " + str(OUT / f"ground_reclaim_{tag}_per_zone.csv"))
    return 0


def _report(pp, pz, attrition):
    line = "=" * 78
    print(f"\n{line}\nRECLAMATION RULE, WHAT EACH TEST REMOVES\n{line}")
    for k, v in attrition.items():
        print(f"  {k:52s} {v:>10,}")

    print(f"\n{line}\nPART 1  GROUND-POINT DENSITY BY ZONE  (no model, just counts)"
          f"\n{line}")
    g = pz.groupby("zone").agg(area=("area_m2", "sum"),
                               ground=("n_ground", "sum"),
                               cls1=("n_class1", "sum"),
                               reclaim=("n_reclaim", "sum"))
    g["ground_per_m2"] = g.ground / g.area
    g["class1_per_m2"] = g.cls1 / g.area
    g["reclaim_per_m2"] = g.reclaim / g.area
    print(f"  {'zone':8s} {'area m2':>11s} {'class2':>10s} {'gnd/m2':>8s} "
          f"{'class1':>10s} {'cls1/m2':>8s} {'reclaimed':>10s} {'rec/m2':>8s}")
    for z in ("floor", "ring", "far"):
        if z not in g.index:
            continue
        r = g.loc[z]
        print(f"  {z:8s} {r.area:11,.0f} {r.ground:10,.0f} {r.ground_per_m2:8.3f} "
              f"{r.cls1:10,.0f} {r.class1_per_m2:8.3f} {r.reclaim:10,.0f} "
              f"{r.reclaim_per_m2:8.3f}")
    if {"floor", "ring"} <= set(g.index):
        print(f"\n  ground density, floor / ring    : "
              f"{g.loc['floor','ground_per_m2'] / g.loc['ring','ground_per_m2']:.3f}"
              "   <- ~1.0 = treated like ordinary terrain")
        print(f"  reclaim density, floor / ring   : "
              f"{g.loc['floor','reclaim_per_m2'] / max(g.loc['ring','reclaim_per_m2'],1e-9):.2f}"
              "   <- the rule's pit specificity")
        print(f"  reclaim density, floor / far    : "
              f"{g.loc['floor','reclaim_per_m2'] / max(g.loc['far','reclaim_per_m2'],1e-9):.2f}")

    print(f"\n{line}\nPART 2  ARE THE WITHHELD POINTS GROUND-LIKE?\n{line}")
    print(f"  {'zone':8s} {'planar residual m':>26s} {'median intensity':>26s} "
          f"{'median |scan angle|':>22s}")
    print(f"  {'':8s} {'class 2':>12s} {'reclaimed':>13s} "
          f"{'class 2':>12s} {'reclaimed':>13s} {'class 2':>10s} {'reclaimed':>11s}")
    for z in ("floor", "ring", "far"):
        s = pz[pz.zone == z]
        if s.empty:
            continue
        print(f"  {z:8s} {s.planar_ground.median():12.3f} "
              f"{s.planar_reclaim.median():13.3f} "
              f"{s.med_inten_ground.median():12.0f} "
              f"{s.med_inten_reclaim.median():13.0f} "
              f"{s.med_absang_ground.median():10.1f} "
              f"{s.med_absang_reclaim.median():11.1f}")
    print("\n  A reclaimed set whose planar residual matches class 2 is a "
          "surface.\n  Scattered noise fits a plane far worse.")

    if pp.empty:
        print("\nno pits measured")
        return
    print(f"\n{line}\nPART 3  WHAT THE DEM DOES  ({len(pp)} pits)\n{line}")
    print(f"  depth as delivered (class 2 only) : median "
          f"{pp.depth_A_m.median():.2f} m")
    print(f"  depth with reclaimed ground       : median "
          f"{pp.depth_B_m.median():.2f} m")
    print(f"  change in depth                   : median "
          f"{pp.d_depth_m.median():+.3f} m, mean {pp.d_depth_m.mean():+.3f} m")
    q = pp.d_depth_m.quantile([0.5, 0.75, 0.9, 0.95, 1.0])
    print(f"  deepened by (m): p50 {q[0.5]:+.2f}  p75 {q[0.75]:+.2f}  "
          f"p90 {q[0.9]:+.2f}  p95 {q[0.95]:+.2f}  max {q[1.0]:+.2f}")
    for t in (0.10, 0.25, 0.50):
        print(f"  pits deepened by >= {t:.2f} m          : "
              f"{int((pp.d_depth_m >= t).sum()):>4} of {len(pp)} "
              f"({100*(pp.d_depth_m >= t).mean():.0f}%)")
    print(f"\n  surface change inside floors : median "
          f"{pp.dz_floor_med.median():+.3f} m, deepest cell "
          f"{pp.dz_floor_min.min():+.2f} m")
    print(f"  surface change in the rings  : median "
          f"{pp.dz_ring_med.median():+.3f} m   <- the negative control")
    print(f"\n  pit floors with ZERO class-2 points : "
          f"{int((pp.n_ground_in_floor == 0).sum())} of {len(pp)}")
    print("\n  The ring is the control. If the floor drops and the ring does "
          "not,\n  the rule is finding something specific to pits, not shaving "
          "ground\n  everywhere.")


def _figure(code, ci, bb, A, B, dz, sub, nkeep):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource, TwoSlopeNorm

    FIGDIR.mkdir(parents=True, exist_ok=True)
    ext = [bb[0], bb[2], bb[1], bb[3]]
    ls = LightSource(azdeg=315, altdeg=45)
    fig, ax = plt.subplots(1, 3, figsize=(16.5, 6.2), facecolor="#fcfcfb")
    for a, arr, t in (
            (ax[0], A, "DEM as delivered\nclass 2 only"),
            (ax[1], B, "DEM with reclaimed ground\nclass 2 + withheld floor returns")):
        f = np.nan_to_num(arr, nan=float(np.nanmedian(arr)))
        a.imshow(ls.hillshade(f, vert_exag=2.0, dx=RES, dy=RES), extent=ext,
                 cmap="gray", origin="upper")
        a.set_title(t, fontsize=12, fontweight="bold", loc="left")
    fin = np.isfinite(dz)
    m = float(np.nanpercentile(np.abs(dz[fin]), 99)) if fin.any() else 0.5
    m = max(m, 0.05)
    im = ax[2].imshow(dz, extent=ext, origin="upper", cmap="RdBu_r",
                      norm=TwoSlopeNorm(vcenter=0, vmin=-m, vmax=m))
    ax[2].set_title("change in surface elevation\nblue = the ground moved down",
                    fontsize=12, fontweight="bold", loc="left")
    fig.colorbar(im, ax=ax[2], fraction=0.04, pad=0.02, label="metres")
    for a in ax:
        sub.boundary.plot(ax=a, color="#eb6834", linewidth=1.4)
        a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
        a.set_xticks([]); a.set_yticks([]); a.set_aspect("equal")
    fig.text(0.01, 0.02, f"tile {code}, cluster {ci}  ·  {RES} m  ·  "
             f"EPSG:6346  ·  {nkeep:,} points reclaimed in this crop  "
             f"·  orange = annotated pit floors",
             fontsize=9, color="#52514e")
    fig.subplots_adjust(left=0.01, right=0.97, top=0.9, bottom=0.07, wspace=0.05)
    p = FIGDIR / f"dem_before_after_reclaim_{code}_c{ci}_{str(RES).replace('.','p')}m.png"
    fig.savefig(p, dpi=190)
    plt.close(fig)
    print(f"  figure {p}")


if __name__ == "__main__":
    sys.exit(main())
