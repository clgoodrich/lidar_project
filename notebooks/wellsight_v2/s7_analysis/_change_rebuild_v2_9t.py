"""Rebuild the 2006-08 to 2019 lidar change surface from raw points with four fixes from the 2026-11-03 outside review (9t).

What was wrong with the first per-pass correction (_change_lineadj_9t.py), and what this does instead.

1. Horizontal offset. The 2006-08 points sit about 0.2 m off the 2019 ground. On a slope that is a vertical error of 0.2 m x tan(slope).
   Fit: d = z2006 - z2019(x, y) = a_e dz/dE + a_n dz/dN + c on slopes of 3 to 30 degrees (Huber weights). Move every 2006 point by (a_e, a_n).
   The fit is repeated after the move. It should return zero.
2. Flight-line offsets from OVERLAPS, not from the 2019 surface. The old method set each pass's median to the 2019 DEM, so any real
   change that covered a pass was removed with the striping. Here each pass is compared with its neighbours on gentle ground where they
   overlap. In an overlap both passes see the same ground in the same year, so real change cancels and an instrument offset does not.
   Offsets come from a least-squares solve over all overlapping pairs with a point-weighted zero-mean gauge. Applied to BOTH epochs.
3. Vertical datum. Old heights are NAVD88 (GEOID03), new are NAVD88 (GEOID12B). The two geoid models differ smoothly. A plane is fitted
   to the 2006 minus 2019 difference on gentle ground and its tilt is reported. A tilt of a few mm per km is removed by the 400 m high-pass
   and is not material. The grids are not applied.
4. Both surfaces are built from raw points with one 2 m TIN code (8 m gap limit), so the 2019 side is no longer a 0.5 m DEM averaged
   to 2 m while the 2006 side is a point-sampled TIN.

Also tested here. Injected real change: +0.25 m added to every 2006 point inside a 1 km disc. The share of it that each offset method
would remove is reported. And seam source: the DoD is built with 2019 raw and with 2019 adjusted, and the straight seams are counted in each.

Outputs
  data/9t/derived/lidar_2006_2008/dem_2006_v2_9t_2m.tif, dem_2019_v2_9t_2m.tif, dod_v2_9t_2m.tif, dod_v2_highpass_9t_2m.tif  (git-ignored)
  data/9t/results/change/change_v2_summary_9t.json, change_v2_offsets_9t.csv

Run: python notebooks/wellsight_v2/s7_analysis/_change_rebuild_v2_9t.py
"""
from __future__ import annotations

import itertools
import json
import os
import sys
from pathlib import Path

import laspy
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _change_lineadj_9t as L  # noqa: E402
from _change_seams_9t import seams  # noqa: E402
from _icp_change_classify_9t import destripe, highpass  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
RAW19 = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
OUTD = ROOT / "data/9t/derived/lidar_2006_2008"
OUTR = ROOT / "data/9t/results/change"
BB, N, RES, PAD = L.BB, L.N, L.RES, L.PAD
CELL = 4.0     # overlap comparison cell (m)
THIN19 = 0.25  # keep fraction of 2019 ground points for the DEM


def load_2019():
    X, Y, Z, P, G = [], [], [], [], []
    for f in sorted(RAW19.glob("USGS_LPC_PA_WesternPA_2019_D20_17TPF6*.laz")):
        with laspy.open(f) as rd:
            h = rd.header
            if h.maxs[0] < BB[0] - PAD or h.mins[0] > BB[2] + PAD or h.maxs[1] < BB[1] - PAD or h.mins[1] > BB[3] + PAD:
                continue
            crs = h.parse_crs()
            n = 0
            for pts in rd.chunk_iterator(4_000_000):
                g = np.asarray(pts.classification) == 2
                x, y = np.asarray(pts.x)[g], np.asarray(pts.y)[g]
                ok = (x > BB[0] - PAD) & (x < BB[2] + PAD) & (y > BB[1] - PAD) & (y < BB[3] + PAD)
                X.append(x[ok]); Y.append(y[ok]); Z.append(np.asarray(pts.z)[g][ok])
                P.append(np.asarray(pts.point_source_id)[g][ok]); G.append(np.asarray(pts.gps_time)[g][ok])
                n += int(ok.sum())
            print(f.name[-10:], "ground in range", n, "crs", (crs.to_epsg() if crs else None), flush=True)
    return [np.concatenate(a) for a in (X, Y, Z, P, G)]


def cells2(x, y):
    c = ((x - BB[0]) / RES).astype(int).clip(0, N - 1)
    r = ((BB[3] - y) / RES).astype(int).clip(0, N - 1)
    return r, c


def horiz_shift(x, y, z, ref, ge, gn, slope, nmax=2_000_000, seed=0):
    """Fit d = a_e*dz/dE + a_n*dz/dN + c, Huber weights. Returns (a_e, a_n, c) in metres. The point's true position is (x + a_e, y + a_n)."""
    rng = np.random.default_rng(seed)
    inb = (x >= BB[0]) & (x < BB[2]) & (y > BB[1]) & (y <= BB[3])
    idx = np.where(inb)[0]
    if len(idx) > nmax:
        idx = rng.choice(idx, nmax, replace=False)
    r, c = cells2(x[idx], y[idx])
    d = z[idx] - ref[r, c]
    s = slope[r, c]
    m = np.isfinite(d) & (s > 3) & (s < 30) & (np.abs(d) < 1.0)
    A = np.c_[ge[r, c][m], gn[r, c][m], np.ones(m.sum())]
    d = d[m]
    w = np.ones(len(d))
    coef = np.zeros(3)
    for _ in range(10):
        coef, *_ = np.linalg.lstsq(A * w[:, None], d * w, rcond=None)
        res = d - A @ coef
        sg = 1.4826 * np.median(np.abs(res - np.median(res)))
        w = np.sqrt(np.minimum(1.0, 1.5 * sg / np.maximum(np.abs(res), 1e-9)))
    return float(coef[0]), float(coef[1]), float(coef[2]), int(m.sum())


def overlap_offsets(x, y, z, lab, slope, min_cells=100, tag=""):
    """Per-pass vertical offsets from pairwise overlap differences on gentle ground, zero-mean gauge (point-weighted)."""
    r, c = cells2(x, y)
    gentle = slope[r, c] < 5.0
    df = pd.DataFrame({"lab": lab[gentle], "cell": ((x[gentle] - BB[0]) // CELL).astype(np.int64) * 100000 + ((y[gentle] - BB[1]) // CELL).astype(np.int64),
                       "z": z[gentle]})
    G = df.groupby(["lab", "cell"]).z.agg(["median", "size"]).reset_index()
    G = G[G["size"] >= 1]
    labs = sorted(G.lab.unique())
    k = {p: i for i, p in enumerate(labs)}
    npts = np.array([(lab == p).sum() for p in labs], float)
    rows, rhs, wts, pairs = [], [], [], []
    ser = {p: G[G.lab == p].set_index("cell")["median"] for p in labs}
    for a, b in itertools.combinations(labs, 2):
        common = ser[a].index.intersection(ser[b].index)
        if len(common) < min_cells:
            continue
        d = (ser[a][common] - ser[b][common]).to_numpy()
        d = d[np.abs(d - np.median(d)) < 0.3]
        if len(d) < min_cells:
            continue
        row = np.zeros(len(labs)); row[k[a]], row[k[b]] = 1.0, -1.0
        w = np.sqrt(len(d))
        rows.append(row * w); rhs.append(np.median(d) * w); wts.append(w)
        pairs.append((a, b, len(d), float(np.median(d))))
    gauge = npts / npts.sum() * 1e3
    A = np.vstack(rows + [gauge]) if rows else gauge[None, :]
    bvec = np.array(rhs + [0.0])
    o, *_ = np.linalg.lstsq(A, bvec, rcond=None)
    misfit = [float(p[3] - (o[k[p[0]]] - o[k[p[1]]])) for p in pairs]
    print(f"  {tag} passes {len(labs)}, overlapping pairs {len(pairs)}, offset std {o.std():.4f} m, pair misfit rms {np.sqrt(np.mean(np.square(misfit))) if misfit else float('nan'):.4f} m", flush=True)
    return dict(zip(labs, o)), pairs, misfit


def ref_offsets(x, y, z, lab, ref, slope, min_n=1500):
    """The OLD method (each pass median against the 2019 DEM), kept to measure how much real change it would remove."""
    r, c = cells2(x, y)
    d = z - ref[r, c]
    use = (slope[r, c] < 5.0) & (np.abs(d) < 0.5) & np.isfinite(d)
    out = {}
    for p in np.unique(lab):
        m = use & (lab == p)
        if m.sum() >= min_n:
            out[p] = float(np.median(d[m]))
    return out


def main():
    OUTR.mkdir(parents=True, exist_ok=True)
    ref = L.dem2019()
    gy, gx = np.gradient(np.nan_to_num(ref, nan=np.nanmean(ref)), RES)
    ge, gn = gx, -gy
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    summary = {}

    print("2006-08 points", flush=True)
    x6, y6, z6, p6, g6 = L.load_points()
    lab6 = L.passes(p6, g6)

    # 1. horizontal shift
    # The shift differs by flight line (first run: north +0.34 to +0.45 m on passes 17, 18, 20 and -0.06 to -0.11 m on 16, 19, 21), so it is
    # fitted and applied per pass. Passes with fewer than 200,000 points get the all-points value.
    ae, an, c0, n = horiz_shift(x6, y6, z6, ref, ge, gn, slope)
    print(f"all-points horizontal shift of 2006: east {ae:+.3f} m, north {an:+.3f} m (n={n})", flush=True)
    per, x6s, y6s = {}, x6.copy(), y6.copy()
    for p in np.unique(lab6):
        m = lab6 == p
        if m.sum() > 200000:
            a1, a2, _, nn = horiz_shift(x6[m], y6[m], z6[m], ref, ge, gn, slope, nmax=600000)
        else:
            a1, a2, nn = ae, an, 0
        x6s[m], y6s[m] = x6[m] + a1, y6[m] + a2
        per[int(p)] = (round(a1, 3), round(a2, 3), nn)
    print("  per-pass shift applied (east, north, n):", per, flush=True)
    res_pass = {}
    for p in np.unique(lab6):
        m = lab6 == p
        if m.sum() > 200000:
            b1, b2, _, _ = horiz_shift(x6s[m], y6s[m], z6[m], ref, ge, gn, slope, nmax=600000)
            res_pass[int(p)] = (round(b1, 3), round(b2, 3))
    print("  residual per pass after the move:", res_pass, flush=True)
    summary["horizontal_shift_2006_m"] = dict(all_points_east=round(ae, 3), all_points_north=round(an, 3), per_pass_applied=per, residual_per_pass=res_pass)
    x6, y6 = x6s, y6s

    # 3. datum tilt, on gentle ground, before any vertical correction
    r, c = cells2(x6, y6)
    inb = (x6 >= BB[0]) & (x6 < BB[2]) & (y6 > BB[1]) & (y6 <= BB[3])
    d = z6[inb] - ref[r[inb], c[inb]]
    gm = (slope[r[inb], c[inb]] < 5) & (np.abs(d) < 0.5) & np.isfinite(d)
    xe, yn = (x6[inb][gm] - (BB[0] + BB[2]) / 2) / 1000.0, (y6[inb][gm] - (BB[1] + BB[3]) / 2) / 1000.0
    A = np.c_[xe, yn, np.ones(gm.sum())]
    cf, *_ = np.linalg.lstsq(A, d[gm], rcond=None)
    print(f"datum tilt of 2006 minus 2019 on gentle ground: east {cf[0] * 1000:+.2f} mm/km, north {cf[1] * 1000:+.2f} mm/km, mean {cf[2]:+.4f} m", flush=True)
    summary["datum_tilt_mm_per_km"] = dict(east=round(float(cf[0] * 1000), 2), north=round(float(cf[1] * 1000), 2), mean_m=round(float(cf[2]), 4),
                                           across_tile_mm=round(float(np.hypot(cf[0], cf[1]) * 4.5 * 1000), 1))

    # 2. overlap offsets, 2006
    off6, pairs6, mis6 = overlap_offsets(x6, y6, z6, lab6, slope, tag="2006")
    off6_old = ref_offsets(x6, y6, z6, lab6, ref, slope)
    z6c = z6 - np.array([off6.get(p, 0.0) for p in lab6])
    rows = [dict(epoch=2006, pass_id=int(p), point_source_id=int(p) // 100, overlap_offset_m=round(off6.get(p, np.nan), 4), vs_2019_offset_m=round(off6_old.get(p, np.nan), 4),
                 n_points=int((lab6 == p).sum())) for p in np.unique(lab6)]

    # injection test: +0.25 m on every 2006 point in a 1 km disc at the tile centre
    cx, cy = (BB[0] + BB[2]) / 2, (BB[1] + BB[3]) / 2
    disc = np.hypot(x6 - cx, y6 - cy) < 1000.0
    zi = z6 + 0.25 * disc
    offi = overlap_offsets(x6, y6, zi, lab6, slope, tag="2006 + injected disc")[0]
    offi_old = ref_offsets(x6, y6, zi, lab6, ref, slope)

    def removed(off_clean, off_inj):
        a = np.array([off_clean.get(p, 0.0) for p in lab6[disc]])
        b = np.array([off_inj.get(p, 0.0) for p in lab6[disc]])
        return float((b - a).mean() / 0.25)
    summary["injected_disc_1km_plus0p25"] = dict(share_removed_overlap_method=round(removed(off6, offi), 3), share_removed_old_vs_2019_method=round(removed(off6_old, offi_old), 3))
    print("injection: share of a +0.25 m, 1 km disc removed by the offsets. overlap method", summary["injected_disc_1km_plus0p25"]["share_removed_overlap_method"],
          "old 2019-referenced method", summary["injected_disc_1km_plus0p25"]["share_removed_old_vs_2019_method"], flush=True)

    # global 2006 level (single constant, after the zero-mean gauge)
    f06 = OUTD / "dem_2006_v2_9t_2m.tif"
    if f06.exists() and os.environ.get("REUSE_06") == "1":
        import rasterio
        with rasterio.open(f06) as s_:
            d06 = s_.read(1).astype(np.float32)
        print("reusing", f06, flush=True)
    else:
        print("building 2006 DEM", flush=True)
        d06 = L.build_dem(x6, y6, z6c)
        L.write(f06, d06)
    del x6, y6, z6, z6c, zi

    print("2019 points", flush=True)
    x9, y9, z9, p9, g9 = load_2019()
    lab9 = L.passes(p9, g9)
    off9, pairs9, mis9 = overlap_offsets(x9, y9, z9, lab9, slope, tag="2019")
    for p in np.unique(lab9):
        rows.append(dict(epoch=2019, pass_id=int(p), point_source_id=int(p) // 100, overlap_offset_m=round(off9.get(p, np.nan), 4), vs_2019_offset_m=np.nan, n_points=int((lab9 == p).sum())))
    pd.DataFrame(rows).to_csv(OUTR / "change_v2_offsets_9t.csv", index=False)
    summary["offsets_2006_overlap"] = dict(std=round(float(np.std(list(off6.values()))), 4), n_passes=len(off6), n_pairs=len(pairs6), misfit_rms=round(float(np.sqrt(np.mean(np.square(mis6)))), 4))
    summary["offsets_2019_overlap"] = dict(std=round(float(np.std(list(off9.values()))), 4), n_passes=len(off9), n_pairs=len(pairs9),
                                           misfit_rms=round(float(np.sqrt(np.mean(np.square(mis9)))) if mis9 else None, 4))
    both = sorted(set(off6) & set(off6_old))
    if len(both) > 2:
        summary["offsets_2006_overlap_vs_2019ref_corr"] = round(float(np.corrcoef([off6[p] for p in both], [off6_old[p] for p in both])[0, 1]), 3)

    # Thin the 2019 ground points to the 2006 density. 2019 has about 7 times more points, and the sparse survey under-resolves pits,
    # so a comparison at unequal sampling reads every pit as changed. Random thinning, fixed seed. The overlap offsets above used all points.
    keep = np.random.default_rng(20261103).random(len(x9)) < THIN19
    x9, y9, z9, lab9 = x9[keep], y9[keep], z9[keep], lab9[keep]
    summary["thin_2019"] = dict(keep_fraction=THIN19, points_kept=int(keep.sum()))
    print(f"2019 thinned to {THIN19:.0%}: {int(keep.sum()):,} points ({keep.sum() / ((BB[2] - BB[0]) * (BB[3] - BB[1])):.2f} per m2)", flush=True)
    print("building 2019 DEM, raw passes", flush=True)
    d19_raw = L.build_dem(x9, y9, z9)
    if max(abs(v) for v in off9.values()) >= 0.01:
        print("building 2019 DEM, adjusted passes", flush=True)
        d19 = L.build_dem(x9, y9, z9 - np.array([off9.get(p, 0.0) for p in lab9]))
    else:
        print("2019 pass offsets are all under 1 cm: the adjusted 2019 surface is the raw one", flush=True)
        d19 = d19_raw
    L.write(OUTD / "dem_2019_v2_9t_2m.tif", d19)
    del x9, y9, z9

    res = {}
    gent = slope < 5.0
    for name, dm in (("2019_raw_passes", d19_raw), ("2019_adjusted_passes", d19)):
        if dm is d19_raw and d19 is d19_raw and name == "2019_raw_passes":
            continue
        dod = dm - d06
        mk = gent & np.isfinite(dod) & (np.abs(dod) < 0.5)
        dod = dod - np.median(dod[mk])
        res[name], hp = L.judge(name, dod)
        if name == "2019_adjusted_passes":
            L.write(OUTD / "dod_v2_9t_2m.tif", dod)
            L.write(OUTD / "dod_v2_highpass_9t_2m.tif", hp)
    summary["judge"] = res
    (OUTR / "change_v2_summary_9t.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
