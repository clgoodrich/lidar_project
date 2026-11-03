"""Remove the flight-line vertical offsets from the 2006-2008 lidar, rebuild the old surface, and re-difference with 2019 (9t).

Why. The straight seams in the 2019 minus 2006-2008 change field are the older survey's flight lines. Each pass sits a few
centimetres high or low (tile 003111: +0.032, -0.025, +0.062, -0.043 m on four lines). That is the same size as the noise floor
and it makes the east-west bands that fooled the patch finder (docs/iterations/icp_change_9t.md, Part 4, finding 3).
Every point carries its flight-line id (point_source_id), so the offset can be measured and removed at the source.

Method.
  1. Read ground-class points (class 2) of the four 2006-2008 tiles as EPSG:2271 US survey feet, convert to EPSG:6346 metres.
  2. Split each point_source_id into passes wherever gps_time jumps by more than 60 s.
  3. Per pass, offset = median of (2006 z minus 2019 DEM z) over gentle ground (slope under 5 deg) and |dz| under 0.5 m.
  4. Subtract the offset. Build two 2 m surfaces from the same points with the same TIN code, one with only a single global offset
     and one with per-pass offsets, so the only difference between them is the correction.
  5. Difference both against the 2019 DEM. Compare noise, band structure and straight seams.

Outputs
  data/9t/derived/lidar_2006_2008/dem_2006_global_9t_2m.tif, dem_2006_lineadj_9t_2m.tif, dod_lineadj_9t_2m.tif   (git-ignored)
  data/9t/results/change/change_line_offsets_9t.csv, change_lineadj_summary_9t.json

Run:
  python notebooks/wellsight_v2/s7_analysis/_change_lineadj_9t.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import laspy
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _icp_change_classify_9t import destripe, highpass  # noqa: E402
from _change_seams_9t import seams  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data/9t/derived/lidar_2006_2008"
OUT = ROOT / "data/9t/results/change"
BB = (619500.0, 4593000.0, 624000.0, 4597500.0)
RES, N = 2.0, 2250
PAD = 80.0
FT = 1200 / 3937


def robust(v):
    v = v[np.isfinite(v)]
    m = np.median(v)
    return float(m), float(1.4826 * np.median(np.abs(v - m)))


def load_points():
    T = Transformer.from_crs(2271, 6346, always_xy=True)
    X, Y, Z, P, G = [], [], [], [], []
    for f in sorted(RAW.glob("*.laz")):
        if f.stat().st_size < 1_000_000:
            continue
        las = laspy.read(f)
        g = np.asarray(las.classification) == 2
        x, y = T.transform(np.asarray(las.x)[g], np.asarray(las.y)[g])
        z = np.asarray(las.z)[g] * FT
        ok = (x > BB[0] - PAD) & (x < BB[2] + PAD) & (y > BB[1] - PAD) & (y < BB[3] + PAD)
        X.append(x[ok]); Y.append(y[ok]); Z.append(z[ok])
        P.append(np.asarray(las.point_source_id)[g][ok]); G.append(np.asarray(las.gps_time)[g][ok])
        print(f.name[-10:], "ground in range", int(ok.sum()), flush=True)
    return [np.concatenate(a) for a in (X, Y, Z, P, G)]


def passes(psid, gps):
    """Label each point with its pass: point_source_id plus a counter that steps at every 60 s gap in gps_time."""
    lab = np.zeros(len(psid), dtype=np.int64)
    for p in np.unique(psid):
        i = np.where(psid == p)[0]
        o = i[np.argsort(gps[i])]
        step = np.r_[0, np.cumsum(np.diff(gps[o]) > 60.0)]
        lab[o] = int(p) * 100 + step
    return lab


def dem2019():
    dst = np.full((N, N), np.nan, np.float32)
    with rasterio.open(ROOT / "data/9t/derived/05/dem_9t_05.tif") as s:
        from rasterio.warp import reproject
        reproject(rasterio.band(s, 1), dst, src_transform=s.transform, src_crs=s.crs, dst_transform=from_origin(BB[0], BB[3], RES, RES),
                  dst_crs="EPSG:6346", resampling=Resampling.average, src_nodata=s.nodata, dst_nodata=np.nan)
    return dst.astype(float)


def build_dem(x, y, z):
    """2 m TIN surface in 500 m blocks with an 80 m buffer. Cells farther than 8 m from any ground point stay empty."""
    dem = np.full((N, N), np.nan, np.float32)
    cs = np.arange(BB[0] + RES / 2, BB[2], RES)
    rs = np.arange(BB[3] - RES / 2, BB[1], -RES)
    tree = cKDTree(np.c_[x, y])
    nb = 9
    for bi in range(nb):
        for bj in range(nb):
            c0, c1 = bj * 250, (bj + 1) * 250
            r0, r1 = bi * 250, (bi + 1) * 250
            x0, x1 = cs[c0] - PAD, cs[c1 - 1] + PAD
            y1, y0 = rs[r0] + PAD, rs[r1 - 1] - PAD
            m = (x > x0) & (x < x1) & (y > y0) & (y < y1)
            if m.sum() < 50:
                continue
            f = LinearNDInterpolator(np.c_[x[m], y[m]], z[m])
            gx, gy = np.meshgrid(cs[c0:c1], rs[r0:r1])
            v = f(gx, gy)
            d, _ = tree.query(np.c_[gx.ravel(), gy.ravel()], distance_upper_bound=8.0)
            v = np.where(np.isfinite(d).reshape(v.shape), v, np.nan)
            dem[r0:r1, c0:c1] = v
        print("  dem row block", bi + 1, "of", nb, flush=True)
    return dem


def write(path, a):
    with rasterio.open(path, "w", driver="GTiff", height=N, width=N, count=1, dtype="float32", crs="EPSG:6346",
                       transform=from_origin(BB[0], BB[3], RES, RES), nodata=np.nan, compress="deflate", tiled=True) as d:
        d.write(a.astype(np.float32), 1)


def judge(name, dod):
    med, sig = robust(dod)
    ds = destripe(dod)
    hp = highpass(ds)
    sm, _ = seams(hp)
    rm = np.nanmedian(dod, axis=1)
    cm = np.nanmedian(dod, axis=0)
    thr = 3 * robust(hp)[1]
    n_big = int((np.abs(hp) > thr).sum())
    out = dict(median=round(med, 4), sigma=round(sig, 4), row_median_std=round(float(np.nanstd(rm)), 4), col_median_std=round(float(np.nanstd(cm)), 4),
               sigma_destriped=round(robust(ds)[1], 4), sigma_highpassed=round(robust(hp)[1], 4), seam_cells_row=int((sm == 1).sum()),
               seam_cells_col=int((sm == 2).sum()), cells_over_3sigma=n_big)
    print(name, out, flush=True)
    return out, hp


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    x, y, z, psid, gps = load_points()
    lab = passes(psid, gps)
    ref = dem2019()
    inb = (x >= BB[0]) & (x < BB[2]) & (y > BB[1]) & (y <= BB[3])
    c = ((x[inb] - BB[0]) / RES).astype(int).clip(0, N - 1)
    r = ((BB[3] - y[inb]) / RES).astype(int).clip(0, N - 1)
    gy, gx = np.gradient(np.nan_to_num(ref, nan=np.nanmean(ref)), RES)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    d = z[inb] - ref[r, c]
    use = (slope[r, c] < 5.0) & (np.abs(d) < 0.5) & np.isfinite(d)
    gl = float(np.median(d[use]))
    rows = []
    off = {}
    for p in np.unique(lab[inb]):
        m = use & (lab[inb] == p)
        if m.sum() >= 1500:
            off[p] = float(np.median(d[m]))
            rows.append(dict(pass_id=int(p), point_source_id=int(p) // 100, n_gentle=int(m.sum()), offset_m=round(off[p], 4), mad_m=round(robust(d[m])[1], 4)))
    T = pd.DataFrame(rows)
    T.to_csv(OUT / "change_line_offsets_9t.csv", index=False)
    print(T.to_string(index=False))
    print("global offset", round(gl, 4), "spread of pass offsets (std)", round(float(T.offset_m.std()), 4))
    z_glob = z - gl
    z_line = z - np.array([off.get(p, gl) for p in lab])
    print("building DEM, global offset only")
    dg = build_dem(x, y, z_glob)
    write(RAW / "dem_2006_global_9t_2m.tif", dg)
    print("building DEM, per-pass offsets")
    dl = build_dem(x, y, z_line)
    write(RAW / "dem_2006_lineadj_9t_2m.tif", dl)
    res = {"global_offset_m": round(gl, 4), "passes": int(len(T)), "pass_offset_std_m": round(float(T.offset_m.std()), 4)}
    for name, dm in (("global", dg), ("lineadj", dl)):
        dod = ref - dm
        res[name], hp = judge(name, dod)
        if name == "lineadj":
            write(RAW / "dod_lineadj_9t_2m.tif", dod)
            write(RAW / "dod_lineadj_highpass_9t_2m.tif", hp)
    (OUT / "change_lineadj_summary_9t.json").write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
