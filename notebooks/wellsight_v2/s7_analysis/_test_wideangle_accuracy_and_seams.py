"""Tests 2 and 3 on the wide-angle ground returns we put back.

TEST 2 -- IS THE ACCURACY CHECK AS GOOD AS WE SAID?
---------------------------------------------------
`_are_excluded_returns_accurate.py` reported 0.065 m RMSE for the excluded
wide-angle returns and we quoted it as proof the vendor's cut was
over-conservative. Two problems with leaning on that number:

  a. It is computed by fitting a plane through ground from OTHER flight lines,
     so it can only be computed WHERE TWO LINES OVERLAP. That is the one place
     the ground is not missing. It says nothing about the stripes where we
     actually rely on the recovered points.
  b. It was never stratified by slope. Off-nadir, horizontal error maps into
     vertical error as dz = dx * tan(slope). On a 30 degree Appalachian
     hillside a 20 cm horizontal error is 12 cm vertical, and pits sit on
     slopes. A flat-ground RMSE is the least informative place to measure it.

So this run repeats the comparison, and additionally reports:
  - what FRACTION of the excluded returns can be validated at all
  - RMSE broken out by the local ground slope, taken from the fitted plane
    itself rather than from a raster
  - the narrow-angle control, which came back n=0 last time and therefore left
    the headline number with no baseline

TEST 3 -- DOES PUTTING THEM BACK LEAVE A SEAM?
-----------------------------------------------
Mixing swath edges into a DTM can leave a step where two lines meet. The
earlier run measured |dz| only where the vendor already had ground, which is
exactly where the recovery changes nothing, so it could not have seen a seam.
This one measures dz as a function of distance to the recovered patches: if
there is a step, the disagreement grows as you approach one.

Run:
    python notebooks/wellsight_v2/s7_analysis/_test_wideangle_accuracy_and_seams.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import laspy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
SMRF = ROOT / "data/9t/results/smrf_ground"
OUT = ROOT / "data/9t/results/nonground_classification"
CUT, RADIUS, MIN_N = 18.0, 3.0, 8
SLOPE_BINS = [0, 5, 10, 15, 20, 25, 30, 90]


def find(code):
    hits = [h for h in sorted(SRC.rglob(f"*{code}*.la[sz]"))
            if not h.name.startswith("_merged")]
    if not hits:
        raise SystemExit(f"no source tile for {code}")
    return hits[0]


def plane_residuals(xyz_q, line_q, ground_by_line, rng, sample):
    """Residual of each query point against a plane fitted from OTHER lines.

    Returns (residual, slope_deg, pairable_mask). A point is 'pairable' only if
    another line put at least MIN_N ground points within RADIUS of it -- which
    is the coverage limit the headline number never reported.
    """
    from scipy.spatial import cKDTree
    n = len(xyz_q)
    take = rng.choice(n, size=min(sample, n), replace=False) if n > sample \
        else np.arange(n)
    q = xyz_q[take]
    ql = line_q[take]
    res = np.full(len(q), np.nan, np.float64)
    slp = np.full(len(q), np.nan, np.float64)

    trees = {l: cKDTree(g[:, :2]) for l, g in ground_by_line.items()}
    for l in np.unique(ql):
        others = [o for o in ground_by_line if o != l]
        if not others:
            continue
        sel = np.where(ql == l)[0]
        pts = q[sel]
        # gather neighbours from every OTHER line
        cand = [[] for _ in range(len(sel))]
        for o in others:
            idx = trees[o].query_ball_point(pts[:, :2], RADIUS)
            g = ground_by_line[o]
            for k, ii in enumerate(idx):
                if ii:
                    cand[k].append(g[ii])
        for k, parts in enumerate(cand):
            if not parts:
                continue
            nb = np.vstack(parts)
            if len(nb) < MIN_N:
                continue
            A = np.c_[nb[:, 0] - pts[k, 0], nb[:, 1] - pts[k, 1],
                      np.ones(len(nb))]
            try:
                coef, *_ = np.linalg.lstsq(A, nb[:, 2], rcond=None)
            except np.linalg.LinAlgError:
                continue
            res[sel[k]] = pts[k, 2] - coef[2]
            slp[sel[k]] = np.degrees(np.arctan(np.hypot(coef[0], coef[1])))
    return res, slp, np.isfinite(res)


def stats(r):
    r = r[np.isfinite(r)]
    if r.size < 30:
        return dict(n=int(r.size))
    return dict(n=int(r.size), median=float(np.median(r)),
                rmse=float(np.sqrt(np.mean(r ** 2))),
                p95=float(np.percentile(np.abs(r), 95)))


def test2(code, sample, seed):
    las = laspy.read(find(code))
    x, y, z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
    cls = np.asarray(las.classification).astype(np.int16)
    psid = np.asarray(las.point_source_id).astype(np.int32)
    ang = np.asarray(las.scan_angle).astype(np.float32) * 0.006
    aa = np.abs(ang)
    ground = cls == 2

    ground_by_line = {int(l): np.c_[x[ground & (psid == l)],
                                    y[ground & (psid == l)],
                                    z[ground & (psid == l)]]
                      for l in np.unique(psid[ground])}
    print(f"\n=== TEST 2  {code}   {len(np.unique(psid))} flight lines, "
          f"ground points per line: "
          f"{ {k: len(v) for k, v in ground_by_line.items()} }")

    rng = np.random.default_rng(seed)
    # "at ground level", the same 0.15 m rule the original used -- but height
    # is taken from the VENDOR DEM here, which lets us also report how many of
    # these points sit over a cell where the vendor had no ground at all and
    # the DEM is therefore an interpolation across the hole.
    import rasterio
    hag = np.full(len(x), np.nan, np.float32)
    over_void = np.zeros(len(x), bool)
    vp = SMRF / f"dem_vendorground_{code}_0p5m.tif"
    stp = SMRF / f"ground_cell_status_{code}_0p5m.tif"
    if vp.exists():
        with rasterio.open(vp) as r:
            # rasterio.index() is scalar-only; do the affine by hand
            inv = ~r.transform
            cf, rf = inv * (x, y)
            rows = np.clip(rf.astype(np.int64), 0, r.height - 1)
            colz = np.clip(cf.astype(np.int64), 0, r.width - 1)
            dem = r.read(1).astype("float32")
        hag = z - dem[rows, colz]
        if stp.exists():
            with rasterio.open(stp) as r:
                stat = r.read(1)
            over_void = stat[rows, colz] != 0
    at = np.isfinite(hag) & (np.abs(hag) < 0.15)
    print(f"  at-ground rule |z - vendor DEM| < 0.15 m: {at.sum():,} points")

    groups = {
        "excluded, wide angle": at & (~ground) & (cls != 7) & (aa > CUT),
        "accepted, wide angle": ground & (aa > CUT),
        "accepted, 10-18 deg": ground & (aa >= 10) & (aa <= CUT),
        "accepted, narrow <10 deg": ground & (aa < 10),
    }
    out = {}
    for name, m in groups.items():
        idx = np.where(m)[0]
        if idx.size == 0:
            print(f"  {name:26s} none in tile")
            continue
        res, slp, ok = plane_residuals(np.c_[x[idx], y[idx], z[idx]],
                                       psid[idx], ground_by_line, rng, sample)
        cov = 100.0 * ok.mean()
        s = stats(res)
        print(f"  {name:26s} {idx.size:>9,} points, "
              f"{cov:5.1f}% validatable   " +
              (f"n={s['n']:>6,}  rmse {s['rmse']:.3f} m  "
               f"p95 {s['p95']:.3f} m" if s.get("rmse") else "too few pairs"))
        by = {}
        for lo, hi in zip(SLOPE_BINS[:-1], SLOPE_BINS[1:]):
            mm = ok & (slp >= lo) & (slp < hi)
            st = stats(res[mm])
            by[f"{lo}-{hi}"] = st
            if st.get("rmse"):
                print(f"        slope {lo:>2}-{hi:<2} deg   n={st['n']:>6,}  "
                      f"rmse {st['rmse']:.3f} m   p95 {st['p95']:.3f} m")
        frac_void = float(100 * over_void[idx].mean()) if over_void.any() else 0.0
        if name.startswith("excluded"):
            print(f"        of these, {frac_void:.1f}% sit over a cell where "
                  f"the vendor had NO ground, so their height above ground "
                  f"came from interpolation across the hole")
        out[name] = dict(points=int(idx.size), validatable_pct=cov,
                         over_void_pct=frac_void, overall=s, by_slope=by)
    return out


def test3(code):
    """Does the recovered ground leave a step where it meets vendor ground?"""
    import rasterio
    from scipy import ndimage
    vp = SMRF / f"dem_vendorground_{code}_0p5m.tif"
    sp = SMRF / f"dem_smrfground_slope0p35_{code}_0p5m.tif"
    st = SMRF / f"ground_cell_status_{code}_0p5m.tif"
    if not (vp.exists() and sp.exists() and st.exists()):
        print(f"\n=== TEST 3  {code}: DEMs absent (gitignored); "
              f"re-run _smrf_reclassify_ground.py to regenerate")
        return None
    with rasterio.open(vp) as r:
        v = r.read(1).astype("float32")
    with rasterio.open(sp) as r:
        s = r.read(1).astype("float32")
    with rasterio.open(st) as r:
        c = r.read(1)
    dz = s - v
    vendor = (c == 0) & np.isfinite(dz)
    rec = (c == 1)
    # distance, in cells, from each vendor cell to the nearest recovered cell
    d = ndimage.distance_transform_edt(~rec) * 0.5
    print(f"\n=== TEST 3  {code}   seam check on {vendor.sum():,} cells where "
          f"the vendor already had ground")
    print(f"  {'distance to recovered ground':32s} {'n':>10s} "
          f"{'median dz':>10s} {'p95 |dz|':>10s}")
    rows = {}
    for lo, hi in ((0, 1), (1, 2), (2, 5), (5, 10), (10, 25), (25, 1e9)):
        m = vendor & (d >= lo) & (d < hi)
        if m.sum() < 100:
            continue
        q = dz[m]
        lab = f"{lo}-{hi:g} m" if hi < 1e9 else f"{lo}+ m"
        rows[lab] = dict(n=int(m.sum()), median=float(np.median(q)),
                         p95=float(np.percentile(np.abs(q), 95)))
        print(f"  {lab:32s} {m.sum():>10,} {np.median(q):>10.4f} "
              f"{np.percentile(np.abs(q), 95):>10.4f}")
    print("  a seam would show as p95 |dz| climbing toward the 0-1 m row")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", nargs="+", default=["621594"])
    ap.add_argument("--sample", type=int, default=40000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    res = {}
    for t in a.tiles:
        res[t] = dict(test2=test2(t, a.sample, a.seed), test3=test3(t))
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "wideangle_accuracy_and_seam_tests.json"
    p.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
