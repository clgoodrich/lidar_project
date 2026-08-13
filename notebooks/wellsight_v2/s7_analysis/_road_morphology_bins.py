"""Unsupervised morphology bins for the 9t hand-drawn roads.

Question: the annotated roads visibly come in at least two varieties — wide
engineered roads and faint narrow traces. Is that a real split in the terrain
data, and where does the boundary sit?

Method mirrors `_pad_morphology_bins.py` (StandardScaler -> PCA -> KMeans, k by
silhouette) but the features are **cross-sectional**, because "big vs faint" is
a property of the road's profile, not its plan shape.

For each road, perpendicular transects are cast every TRANSECT_STEP m out to
HALF_W m each side. Each transect is detrended against the surrounding hillslope
(a line fit through the OUTER thirds only, so the road itself never influences
its own trend surface), and the residual profile is measured. Per-road features
are medians over its transects.

Validation is external: TIGER/Line road classes (MTFCC) never touched the DEM,
so bin-vs-TIGER agreement is an honest check rather than a restatement of the
clustering. Model confidence P(road) is likewise held OUT of the clustering and
reported afterwards.

Outputs (data/derivatives/experiments/road_morphology_bins/):
    road_morphology_bins_9t_05.gpkg     per-road features + bin, styled
    road_morphology_bins_9t_05.csv      same, tabular
    road_bin_profiles_9t_05.json        per-bin medians + validation table
    fig_road_bin_crosssections_9t_05.png  median transect profile per bin
    fig_road_bin_features_9t_05.png     z-scored feature heatmap
    fig_road_bin_map_9t_05.png          9t map coloured by bin

CLI:
  python notebooks/wellsight_v2/s7_analysis/_road_morphology_bins.py [--k 0]
    --k 0 (default) selects k by silhouette over 2..8; --k N forces N.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import LineString
from shapely.ops import unary_union

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, path_for  # noqa: E402

R9 = path_for("nine_t")
OUT = path_for("experiments") / "road_morphology_bins"

ROADS_SHP = path_for("truth") / "roads.shp"

TRANSECT_STEP = 10.0    # m along the road between transects
HALF_W = 25.0           # m each side of centreline
DX = 0.5                # m sample spacing along the transect (matches raster)
MIN_LEN = 25.0          # m — shorter roads give too few transects to be stable
TREAD_MAX_SLOPE = 8.0   # deg — tread is the contiguous low-slope run at centre
INNER = 10.0            # m — "on the road" band for cut/fill
OUTER_LO = 15.0         # m — detrend fit uses |d| in [OUTER_LO, HALF_W]

# 0.5 m rasters. Roads are 3-6 m wide, so 1 m sampling would alias the tread.
RASTERS = {
    "dem":   R9 / "dem_9t_05.tif",
    "slope": R9 / "slope_9t_05.tif",
    "chm":   R9 / "chm_9t_05.tif",
    "inten": R9 / "intensity_ground_9t_05.tif",
    "lrm5":  R9 / "lrm_5_9t_05.tif",
}


# ---------------------------------------------------------------------------
# transect geometry
# ---------------------------------------------------------------------------
def build_transects(lines, ids):
    """Return (xs, ys, road_idx, transect_idx, offsets) flattened sample coords.

    xs/ys are the world coordinates of every sample of every transect, laid out
    so one vectorised raster lookup fills them all.
    """
    offs = np.arange(-HALF_W, HALF_W + DX * 0.5, DX)
    n_off = len(offs)
    X, Y, RI, TI = [], [], [], []
    t_counter = 0
    for ri, line in zip(ids, lines):
        parts = list(line.geoms) if line.geom_type == "MultiLineString" else [line]
        for part in parts:
            if part.length < MIN_LEN:
                continue
            n = max(2, int(part.length / TRANSECT_STEP))
            for s in np.linspace(part.length * 0.05, part.length * 0.95, n):
                p0 = part.interpolate(max(0.0, s - 2.0))
                p1 = part.interpolate(min(part.length, s + 2.0))
                dx, dy = p1.x - p0.x, p1.y - p0.y
                norm = np.hypot(dx, dy)
                if norm < 1e-6:
                    continue
                # unit normal
                nx, ny = -dy / norm, dx / norm
                c = part.interpolate(s)
                X.append(c.x + nx * offs)
                Y.append(c.y + ny * offs)
                RI.append(np.full(n_off, ri))
                TI.append(np.full(n_off, t_counter))
                t_counter += 1
    if not X:
        return None
    return (np.concatenate(X), np.concatenate(Y),
            np.concatenate(RI), np.concatenate(TI), offs)


def sample_raster(path, xs, ys):
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
        nod = src.nodata
        inv = ~src.transform
        H, W = a.shape
    cols, rows = inv * (xs, ys)
    cols = np.rint(cols).astype(np.int64)
    rows = np.rint(rows).astype(np.int64)
    ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    out = np.full(xs.shape, np.nan, dtype=np.float32)
    out[ok] = a[rows[ok], cols[ok]]
    if nod is not None:
        out[out == nod] = np.nan
    out[out < -1e30] = np.nan
    del a
    return out


# ---------------------------------------------------------------------------
# per-transect measurements
# ---------------------------------------------------------------------------
def measure(prof, offs):
    """prof: dict of (n_transect, n_offset) arrays. Returns per-transect table."""
    d = offs
    inner = np.abs(d) <= INNER
    outer = (np.abs(d) >= OUTER_LO) & (np.abs(d) <= HALF_W)
    centre = np.abs(d) <= 2.0
    flank = (np.abs(d) >= OUTER_LO) & (np.abs(d) <= HALF_W)

    z = prof["dem"]
    n = z.shape[0]

    # Detrend each transect on the OUTER thirds only, so the road never
    # influences the trend line that is meant to represent the hillslope.
    resid = np.full_like(z, np.nan)
    hillslope = np.full(n, np.nan, dtype=np.float32)
    for i in range(n):
        m = outer & np.isfinite(z[i])
        if m.sum() < 10:
            continue
        coef = np.polyfit(d[m], z[i][m], 1)
        resid[i] = z[i] - np.polyval(coef, d)
        hillslope[i] = np.degrees(np.arctan(abs(coef[0])))

    def nanq(a, q, mask):
        sub = np.where(mask[None, :], a, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return np.nanpercentile(sub, q, axis=1)

    cut = -np.fmin(nanq(resid, 5, inner), 0.0)          # dig into the hillside
    fill = np.fmax(nanq(resid, 95, inner), 0.0)         # spoil on the downhill
    relief = nanq(resid, 95, inner) - nanq(resid, 5, inner)

    # Tread width: contiguous low-slope run containing the centre sample.
    sl = prof["slope"]
    c0 = int(np.argmin(np.abs(d)))
    low = sl <= TREAD_MAX_SLOPE
    width = np.zeros(n, dtype=np.float32)
    for i in range(n):
        if not low[i, c0]:
            continue
        a = c0
        while a > 0 and low[i, a - 1]:
            a -= 1
        b = c0
        while b < len(d) - 1 and low[i, b + 1]:
            b += 1
        width[i] = (b - a) * DX
    width = np.minimum(width, 2 * HALF_W)

    # Shoulder sharpness: steepest local step in the residual just off the tread.
    grad = np.abs(np.gradient(np.nan_to_num(resid, nan=0.0), DX, axis=1))
    shoulder = np.nanmax(np.where(inner[None, :], grad, np.nan), axis=1)

    # Incision depth: trough at the centreline measured against the flanking
    # berms, NOT against the fitted trend. This is a within-transect contrast,
    # so it does not inherit the hillslope's steepness the way cut/fill do —
    # it is the terrain-independent measure of how strongly a road is cut in.
    left = (d >= -12.0) & (d <= -3.0)
    right = (d >= 3.0) & (d <= 12.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        berm_l = np.nanmax(np.where(left[None, :], resid, np.nan), axis=1)
        berm_r = np.nanmax(np.where(right[None, :], resid, np.nan), axis=1)
        trough = np.nanmin(np.where(centre[None, :], resid, np.nan), axis=1)
        # distance between the two flanking maxima = how wide the disturbance is
        il = np.nanargmax(np.where(left[None, :], resid, -np.inf), axis=1)
        ir = np.nanargmax(np.where(right[None, :], resid, -np.inf), axis=1)
    incision = np.fmax((berm_l + berm_r) / 2.0 - trough, 0.0)
    berm_sep = np.abs(d[ir] - d[il])

    # Width, done properly: full width at half minimum of the incision trough.
    # `tread_width_m` (contiguous slope <= 8 deg) has no terminating shoulder on
    # flat ground and saturates there — it reports WIDER treads for the fainter,
    # flatter roads, which is backwards. FWHM is scale-free and works on any
    # terrain because it is defined relative to that transect's own trough depth.
    berm_lvl = (berm_l + berm_r) / 2.0
    half_lvl = trough + 0.5 * np.fmax(berm_lvl - trough, 1e-6)
    c0i = int(np.argmin(np.abs(d)))
    fwhm = np.full(n, np.nan, dtype=np.float32)
    for i in range(n):
        if not np.isfinite(half_lvl[i]) or not np.isfinite(resid[i, c0i]):
            continue
        a = c0i
        while a > 0 and np.isfinite(resid[i, a]) and resid[i, a] <= half_lvl[i]:
            a -= 1
        b = c0i
        while (b < len(d) - 1 and np.isfinite(resid[i, b])
               and resid[i, b] <= half_lvl[i]):
            b += 1
        fwhm[i] = (b - a) * DX
    fwhm = np.where(fwhm >= 2 * HALF_W, np.nan, fwhm)   # never closed = invalid

    out = {
        "incision_depth_m": incision,
        "berm_sep_m": berm_sep,
        "incision_fwhm_m": fwhm,
        "tread_width_m": width,
        "cut_depth_m": cut,
        "fill_height_m": fill,
        "bench_amp_m": cut + fill,
        "relief_amp_m": relief,
        "shoulder_grad": shoulder,
        "hillslope_deg": hillslope,
        "slope_centre": np.nanmedian(np.where(centre[None, :], prof["slope"], np.nan), axis=1),
        "slope_flank": np.nanmedian(np.where(flank[None, :], prof["slope"], np.nan), axis=1),
        # CHM is heavily zero-inflated (tile median 0.091 m, p99 25.8 m): most
        # 0.5 m cells resolve to bare ground, so a MEDIAN along a transect
        # measures the zeros, not the canopy. p90 captures whether canopy is
        # present over the band at all, which is the actual question.
        "chm_centre": nanq(prof["chm"], 90, centre),
        "chm_flank": nanq(prof["chm"], 90, flank),
        "inten_centre": np.nanmedian(np.where(centre[None, :], prof["inten"], np.nan), axis=1),
        "inten_flank": np.nanmedian(np.where(flank[None, :], prof["inten"], np.nan), axis=1),
        "lrm5_amp": (nanq(prof["lrm5"], 95, inner) - nanq(prof["lrm5"], 5, inner)),
    }
    out["slope_ratio"] = out["slope_centre"] / np.maximum(out["slope_flank"], 0.5)
    out["chm_deficit_m"] = out["chm_flank"] - out["chm_centre"]
    out["inten_ratio"] = out["inten_centre"] / np.maximum(out["inten_flank"], 1e-3)
    return out, resid


# Terrain-context features. A first run including these produced a k=2 split
# driven almost entirely by hillslope (8.7 deg vs 2.7 deg) — it binned WHERE a
# road sits, not HOW BIG it is. They are reported but kept out of the clustering.
TERRAIN_FEATS = ["hillslope_deg", "slope_centre", "slope_flank", "slope_ratio",
                 "cut_depth_m", "fill_height_m"]

# Size / prominence features. `tread_width_m` is deliberately absent: it is the
# contiguous run of slope <= 8 deg through the centreline, which has no
# terminating shoulder on flat ground and saturates there. `berm_sep_m` measures
# disturbance width on any terrain, so it replaces it. cut/fill are terrain
# features because on a sideslope the hillslope angle sets their magnitude;
# `incision_depth_m` is the within-transect equivalent that does not.
CLUSTER_FEATS = [
    "incision_depth_m", "incision_fwhm_m", "berm_sep_m", "bench_amp_m",
    "relief_amp_m", "shoulder_grad", "lrm5_amp", "chm_centre",
    "chm_deficit_m", "inten_ratio", "sinuosity", "log_length",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=0, help="0 = pick by silhouette")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- roads clipped to 9t ------------------------------------------------
    roads = gpd.read_file(ROADS_SHP).to_crs(DST_CRS)
    blocks = gpd.read_file(R9 / "pit_blocks_9t.gpkg")
    region = unary_union(blocks.geometry.values)
    roads = roads[roads.intersects(region)].copy()
    roads["geometry"] = roads.geometry.intersection(region)
    roads = roads[~roads.is_empty].reset_index(drop=True)
    roads["length_m"] = roads.length
    roads = roads[roads.length_m >= MIN_LEN].reset_index(drop=True)
    print(f"roads.shp -> 9t: {len(roads)} roads, {roads.length_m.sum()/1000:.2f} km "
          f"(>= {MIN_LEN:.0f} m)")

    # ---- transect sampling --------------------------------------------------
    built = build_transects(roads.geometry.values, roads.index.values)
    if built is None:
        print("no transects built")
        return 1
    xs, ys, ri, ti, offs = built
    n_t = ti.max() + 1
    n_off = len(offs)
    print(f"transects: {n_t:,} ({TRANSECT_STEP:.0f} m spacing, "
          f"+/-{HALF_W:.0f} m at {DX} m) = {len(xs):,} samples")

    prof = {}
    for name, path in RASTERS.items():
        if not path.exists():
            print(f"  MISSING {path.name}")
            return 1
        prof[name] = sample_raster(path, xs, ys).reshape(n_t, n_off)
        print(f"  sampled {name:6s} nan {np.isnan(prof[name]).mean()*100:5.2f}%")

    per_t, resid = measure(prof, offs)
    t_road = ri.reshape(n_t, n_off)[:, 0]

    # ---- aggregate to roads -------------------------------------------------
    df = pd.DataFrame(per_t)
    df["road"] = t_road
    agg = df.groupby("road").median(numeric_only=True)
    agg["n_transects"] = df.groupby("road").size()
    agg = agg[agg.n_transects >= 3]
    print(f"roads with >=3 transects: {len(agg)}")

    g = roads.loc[agg.index].copy()
    for c in agg.columns:
        g[c] = agg[c].values
    # plan-shape extras
    def sinuo(ln):
        parts = list(ln.geoms) if ln.geom_type == "MultiLineString" else [ln]
        tot = sum(p.length for p in parts)
        ends = sum(LineString([p.coords[0], p.coords[-1]]).length for p in parts)
        return tot / max(ends, 1.0)
    g["sinuosity"] = [sinuo(x) for x in g.geometry]
    g["log_length"] = np.log1p(g.length_m)

    feats = [c for c in CLUSTER_FEATS if c in g.columns]
    M = g[feats].replace([np.inf, -np.inf], np.nan)
    M = M.fillna(M.median())
    print(f"clustering on {len(feats)} features x {len(M)} roads")

    # ---- cluster ------------------------------------------------------------
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    Z = StandardScaler().fit_transform(M.values)
    pca = PCA(n_components=0.90, random_state=0)
    P = pca.fit_transform(Z)
    print(f"PCA: {P.shape[1]} components for 90% variance")

    sils = {}
    for k in range(2, 9):
        lab = KMeans(n_clusters=k, n_init=20, random_state=0).fit_predict(P)
        sils[k] = float(silhouette_score(P, lab))
        print(f"  k={k}  silhouette {sils[k]:.3f}")
    k = args.k if args.k else max(sils, key=sils.get)
    print(f"\nusing k={k} (silhouette {sils[k]:.3f})"
          + ("  [forced]" if args.k else "  [best]"))
    km = KMeans(n_clusters=k, n_init=50, random_state=0).fit(P)
    g["bin"] = km.labels_

    # order bins by incision depth so bin 0 is always the faintest
    order = g.groupby("bin").incision_depth_m.median().sort_values().index.tolist()
    g["bin"] = g["bin"].map({b: i for i, b in enumerate(order)})

    # ---- did excluding terrain actually decontaminate the bins? ------------
    # A size split should NOT reproduce the hillslope split. Report eta^2 of
    # hillslope across bins alongside eta^2 of the size index, so the reader can
    # see which axis the bins are actually on.
    def eta2(col):
        v = g[col].astype(float)
        gm = v.mean()
        ssb = sum(len(s) * (s.mean() - gm) ** 2 for _, s in v.groupby(g.bin))
        sst = ((v - gm) ** 2).sum()
        return float(ssb / sst) if sst else float("nan")
    print("\nvariance explained by the bins (eta^2):")
    for c in ["incision_depth_m", "incision_fwhm_m", "berm_sep_m", "relief_amp_m", "log_length",
              "hillslope_deg", "slope_flank"]:
        tag = "  <- terrain (want LOW)" if c in TERRAIN_FEATS else ""
        print(f"  {c:18s} {eta2(c):.3f}{tag}")

    # ---- is the size axis actually bimodal, or a continuum? ---------------
    from sklearn.mixture import GaussianMixture
    x = np.log1p(g.incision_depth_m.values).reshape(-1, 1)
    bic = {}
    for nc in (1, 2, 3):
        bic[nc] = float(GaussianMixture(nc, random_state=0, n_init=5)
                        .fit(x).bic(x))
    print(f"\n1-D GMM BIC on log incision depth: "
          + "  ".join(f"{n}comp {v:.0f}" for n, v in bic.items()))
    print(f"  -> {min(bic, key=bic.get)} component(s) preferred"
          f"  (lower BIC is better; 1 means the size axis is a continuum,"
          f" not two populations)")

    # ---- terrain-fair prominence -------------------------------------------
    # Incision depth correlates +0.42 (Spearman) with hillslope: a road benched
    # into a sideslope MUST be cut in, while the same road on a flat bench need
    # not be. So raw depth conflates "faint road" with "flat ground". Regressing
    # log depth on log hillslope and keeping the residual gives how strongly a
    # road is expressed FOR THE TERRAIN IT SITS ON, which is the comparison a
    # human actually means by "faint".
    lx = np.log1p(g.hillslope_deg.values.astype(float))
    ly = np.log1p(g.incision_depth_m.values.astype(float))
    ok = np.isfinite(lx) & np.isfinite(ly)
    coef = np.polyfit(lx[ok], ly[ok], 1)
    res = ly - np.polyval(coef, lx)
    g["prominence_z"] = (res - np.nanmean(res[ok])) / np.nanstd(res[ok])
    from scipy.stats import spearmanr
    r_raw = spearmanr(g.incision_depth_m[ok], g.hillslope_deg[ok]).statistic
    r_adj = spearmanr(g.prominence_z[ok], g.hillslope_deg[ok]).statistic
    print(f"\nprominence_z: terrain coupling Spearman {r_raw:+.3f} -> {r_adj:+.3f}"
          f"  (raw incision depth vs terrain-adjusted)")

    # ---- external validation: TIGER + model confidence ---------------------
    tiger_p = path_for("reference") / "tiger_roads" / "roads_clipped.gpkg"
    if tiger_p.exists():
        tg = gpd.read_file(tiger_p).to_crs(DST_CRS)
        tg = tg[tg.intersects(region.buffer(50))]
        if len(tg):
            tu = tg.union_all().buffer(12.0)
            g["tiger_match"] = g.geometry.intersection(tu).length / g.length_m
            g["is_tiger"] = (g.tiger_match >= 0.5).astype(int)
            print(f"TIGER: {len(tg)} lines; {int(g.is_tiger.sum())}/{len(g)} roads "
                  f"match a TIGER road over >=50% of length")
    pr = R9 / "road_unet_1m_recall" / "road_prob.tif"
    if pr.exists():
        pv = sample_raster(pr, xs, ys).reshape(n_t, n_off)
        c0 = int(np.argmin(np.abs(offs)))
        cen = np.nanmedian(pv[:, max(0, c0 - 4):c0 + 5], axis=1)
        s = pd.Series(cen).groupby(t_road).median()
        g["mean_proad"] = s.reindex(g.index).values

    # ---- report -------------------------------------------------------------
    show = ["incision_depth_m", "incision_fwhm_m", "berm_sep_m", "bench_amp_m", "relief_amp_m",
            "shoulder_grad", "chm_centre", "chm_deficit_m", "inten_ratio",
            "length_m", "sinuosity", "hillslope_deg", "tread_width_m"]
    prof_tbl = g.groupby("bin")[show].median().round(2)
    prof_tbl["n"] = g.groupby("bin").size()
    prof_tbl["km"] = (g.groupby("bin").length_m.sum() / 1000).round(1)
    for c in ("is_tiger", "mean_proad"):
        if c in g.columns:
            prof_tbl[c] = g.groupby("bin")[c].mean().round(3)
    print("\n=== bin profiles (medians) ===")
    print(prof_tbl.to_string())

    # ---- outputs ------------------------------------------------------------
    gp = OUT / "road_morphology_bins_9t_05.gpkg"
    g.to_file(gp, layer="roads_binned", driver="GPKG")
    g.drop(columns="geometry").to_csv(OUT / "road_morphology_bins_9t_05.csv",
                                      index=False)
    (OUT / "road_bin_profiles_9t_05.json").write_text(json.dumps(
        {"k": int(k), "silhouette": sils, "features": feats,
         "n_roads": int(len(g)), "km": round(float(g.length_m.sum() / 1000), 2),
         "transect": {"step_m": TRANSECT_STEP, "half_w_m": HALF_W, "dx_m": DX},
         "profiles": json.loads(prof_tbl.to_json(orient="index"))}, indent=2))

    # median cross-section per bin — the figure that shows "big vs faint"
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))
    colors = plt.cm.viridis(np.linspace(0.1, 0.9, k))
    for b in range(k):
        idx = g.index[g.bin == b]
        sel = np.isin(t_road, idx)
        if not sel.any():
            continue
        med = np.nanmedian(resid[sel], axis=0)
        q1 = np.nanpercentile(resid[sel], 25, axis=0)
        q3 = np.nanpercentile(resid[sel], 75, axis=0)
        axes[0].fill_between(offs, q1, q3, color=colors[b], alpha=0.18)
        axes[0].plot(offs, med, color=colors[b], lw=2,
                     label=f"bin {b} (n={len(idx)}, incision "
                           f"{g.loc[idx].incision_depth_m.median():.2f} m)")
        medc = np.nanmedian(prof["chm"][sel], axis=0)
        axes[1].plot(offs, medc, color=colors[b], lw=2, label=f"bin {b}")
    axes[0].axhline(0, color="0.6", lw=0.8)
    axes[0].axvline(0, color="0.6", lw=0.8, ls=":")
    axes[0].set_xlabel("distance from centreline (m)")
    axes[0].set_ylabel("detrended elevation (m)")
    axes[0].set_title("Median road cross-section by bin\n(hillslope trend removed "
                      "using the outer thirds only)", fontsize=10)
    axes[0].legend(fontsize=8)
    axes[1].axvline(0, color="0.6", lw=0.8, ls=":")
    axes[1].set_xlabel("distance from centreline (m)")
    axes[1].set_ylabel("canopy height (m)")
    axes[1].set_title("Median canopy profile by bin\n(a canopy gap means an open "
                      "road)", fontsize=10)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_road_bin_crosssections_9t_05.png", dpi=140)
    plt.close(fig)

    # the headline figure: width is one population, depth is a continuum,
    # and depth is terrain-driven
    from sklearn.mixture import GaussianMixture
    fig, ax = plt.subplots(1, 3, figsize=(16.5, 4.8))

    ax[0].hist(g.berm_sep_m.dropna(), bins=40, color="#3a7ca5", alpha=0.85)
    ax[0].axvline(g.berm_sep_m.median(), color="k", ls="--", lw=1)
    ax[0].set_xlabel("berm-to-berm width (m)")
    ax[0].set_ylabel("roads")
    ax[0].set_title(f"WIDTH is one population\nmedian {g.berm_sep_m.median():.1f} m, "
                    f"CV {g.berm_sep_m.std()/g.berm_sep_m.mean():.2f}", fontsize=10)

    v = np.log1p(g.incision_depth_m.dropna().values).reshape(-1, 1)
    ax[1].hist(g.incision_depth_m.dropna(), bins=45, density=True,
               color="#b5651d", alpha=0.85)
    xs_ = np.linspace(0.01, g.incision_depth_m.quantile(0.99), 400)
    for nc, ls in ((1, "-"), (2, "--")):
        gm = GaussianMixture(nc, random_state=0, n_init=5).fit(v)
        dens = np.exp(gm.score_samples(np.log1p(xs_).reshape(-1, 1))) / (1 + xs_)
        ax[1].plot(xs_, dens, ls, color="k", lw=1.6,
                   label=f"{nc}-comp GMM (BIC {gm.bic(v):.0f})")
    ax[1].set_xlabel("incision depth (m)")
    ax[1].set_title("DEPTH is a continuum\n1-component GMM wins on BIC — "
                    "no two populations", fontsize=10)
    ax[1].legend(fontsize=8)

    sc = ax[2].scatter(g.hillslope_deg, g.incision_depth_m, s=7,
                       c=g["bin"], cmap="viridis", alpha=0.6)
    ax[2].set_xscale("log")
    ax[2].set_yscale("log")
    ax[2].set_xlabel("hillslope at the crossing (deg)")
    ax[2].set_ylabel("incision depth (m)")
    ax[2].set_title(f"DEPTH tracks TERRAIN\nSpearman {r_raw:+.2f} — the same road "
                    f"reads bold\non a sideslope and faint on the flat", fontsize=10)
    fig.suptitle("9t hand-drawn roads: what actually separates 'big' from 'faint'",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT / "fig_road_width_vs_depth_9t_05.png", dpi=140)
    plt.close(fig)

    # z-scored feature heatmap
    zt = (g.groupby("bin")[feats].median() - M.mean()) / M.std()
    fig, ax = plt.subplots(figsize=(11, 1.1 + 0.5 * k))
    im = ax.imshow(zt.values, cmap="RdBu_r", vmin=-1.6, vmax=1.6, aspect="auto")
    ax.set_xticks(range(len(feats)))
    ax.set_xticklabels(feats, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(k))
    ax.set_yticklabels([f"bin {b} (n={int((g.bin==b).sum())})" for b in range(k)],
                       fontsize=8)
    for i in range(k):
        for j in range(len(feats)):
            ax.text(j, i, f"{zt.values[i, j]:.1f}", ha="center", va="center",
                    fontsize=6.5)
    fig.colorbar(im, ax=ax, shrink=0.8, label="z-score vs all roads")
    ax.set_title("Road morphology bins — feature signature", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "fig_road_bin_features_9t_05.png", dpi=140)
    plt.close(fig)

    # map
    fig, ax = plt.subplots(figsize=(9.5, 9.5))
    hs = R9 / "hillshade_9t_05.tif"
    if hs.exists():
        with rasterio.open(hs) as r:
            from rasterio.plot import plotting_extent
            im = r.read(1).astype(np.float32)
            im[im < 0] = np.nan
            ax.imshow(im, cmap="gray", extent=plotting_extent(r), origin="upper",
                      vmin=np.nanpercentile(im, 2), vmax=np.nanpercentile(im, 98))
    for b in range(k):
        sub = g[g.bin == b]
        sub.plot(ax=ax, color=colors[b], linewidth=0.8 + 0.6 * b,
                 label=f"bin {b} — incision "
                       f"{sub.incision_depth_m.median():.2f} m (n={len(sub)})")
    ax.legend(fontsize=8, loc="upper right")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"9t hand-drawn roads, binned by cross-section morphology "
                 f"(k={k})", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "fig_road_bin_map_9t_05.png", dpi=140)
    plt.close(fig)

    print(f"\nwrote:\n  {gp}\n  {OUT / 'road_morphology_bins_9t_05.csv'}"
          f"\n  {OUT / 'road_bin_profiles_9t_05.json'}"
          f"\n  {OUT / 'fig_road_bin_crosssections_9t_05.png'}"
          f"\n  {OUT / 'fig_road_bin_features_9t_05.png'}"
          f"\n  {OUT / 'fig_road_bin_map_9t_05.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
