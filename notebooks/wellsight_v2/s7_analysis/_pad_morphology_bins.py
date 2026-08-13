"""Unsupervised pad morphology bins — joint 9t (Venango) + mkf (McKean).

v2 (2026-07-19): region-aware. All 995 annotated pads participate; features
come from each region's own rasters (9t 0.5 m; McKean 1 m from mkf_1m +
northcentral_b19 blocks, best-covering source picked per pad). Composition
features (n_pits, road distance, well counts) are 9t-only annotations, so the
JOINT clustering uses shape + terrain + canopy features exclusively.

Per-pad features:
  shape    area, perimeter, compactness 4piA/P^2, elongation, solidity,
           rectangularity
  terrain  slope mean/std inside; slope median in 2-30 m annulus; slope_ratio;
           flat_frac (slope < 3 deg); edge_slope (+/-2 m boundary ring);
           lrm11 p95-p5; tpi15 mean
  canopy   chm median inside / in annulus; chm_deficit (annulus - inside)

Known caveat: McKean terrain rasters are 1 m vs 9t 0.5 m — zonal medians and
means are fairly resolution-robust, but slope magnitudes run slightly lower at
1 m; treat cross-region slope comparisons with that in mind.

Clustering: StandardScaler -> PCA(0.9) -> KMeans. k from silhouette (3..8)
unless --k forces it (use --k 2/3 for broad bins). Deterministic.

Outputs (OUT_DIR, all suffixed _joint{_kN}):
  pad_bins_joint{sfx}.gpkg      pads + features + cluster + region, styled
  pad_features_joint.csv        cached feature table (delete to recompute)
  cluster_summary_joint{sfx}.csv, summary_joint{sfx}.json (incl region x bin)
  fig_cluster_profile_joint{sfx}.png, fig_cluster_montage_joint{sfx}.png
      (montage chips labeled with region)

Reproduce: python notebooks/wellsight_v2/s7_analysis/_pad_morphology_bins.py [--k N]
(The 2026-07-19 9t-only k=2/3/4 outputs in this folder came from the v1
script — see git history for that version.)
"""
import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent))
from _export_well_age_qgis import embed_styles, qml_categorized  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
T9 = path_for("nine_t")
MKF = path_for("derived") / "mckean" / "mkf" / "1m"
NC = path_for("data_3x3") / "northcentral_b19"
ANN = path_for("truth") / "annotations_proj.gpkg"
OUT_DIR = path_for("experiments") / "pad_morphology_bins"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:6346"

NC_BLOCKS = ["e1423n2235", "e1423n2238", "e1426n2236", "e1426n2239"]
REGION_RASTERS = {
    "9t": {
        "slope": [T9 / "slope_9t_05.tif"],
        "lrm11": [T9 / "lrm_11_9t_05.tif"],
        "tpi15": [T9 / "tpi_15_9t_05.tif"],
        "chm": [T9 / "chm_9t_05.tif"],
        "hs": [T9 / "hillshade_9t_05.tif"],
    },
    "mckean": {
        "slope": [MKF / "slope_mkf_1m.tif"],
        "lrm11": [MKF / "lrm_11_mkf_1m.tif"],
        "tpi15": [NC / b / f"tpi_15_{b}_1m.tif"
                  for b in ["e1423n2235", "e1423n2238"]],
        "chm": [NC / b / f"chm_{b}_1m.tif" for b in NC_BLOCKS],
        "hs": [NC / b / f"hillshade_{b}_1m.tif" for b in NC_BLOCKS],
    },
}

JOINT_FEATS = ["area_m2", "perim_m", "compactness", "elongation", "solidity",
               "rectangularity", "slope_mean", "slope_std", "slope_flatfrac",
               "slope_annulus", "edge_slope", "slope_ratio", "lrm11_relief",
               "tpi15_mean", "chm_in", "chm_annulus", "chm_deficit"]
LOG_FEATS = ["area_m2", "perim_m"]

CLUSTER_COLORS = ["141,211,199", "255,127,0", "31,120,180", "227,26,28",
                  "106,61,154", "178,223,138", "251,154,153", "253,191,111"]


def pick_src(srcs, bounds):
    """Best-covering open raster for a bbox (fully containing wins)."""
    best, best_cov = None, -1
    for s in srcs:
        b = s.bounds
        ix = min(bounds[2], b.right) - max(bounds[0], b.left)
        iy = min(bounds[3], b.top) - max(bounds[1], b.bottom)
        cov = max(ix, 0) * max(iy, 0)
        if cov > best_cov:
            best, best_cov = s, cov
    return best if best_cov > 0 else None


def zonal(srcs, geom, stat_fns):
    src = pick_src(srcs, geom.bounds)
    if src is None:
        return {k: np.nan for k in stat_fns}
    try:
        b = geom.bounds
        win = from_bounds(b[0] - 1, b[1] - 1, b[2] + 1, b[3] + 1,
                          src.transform).round_offsets().round_lengths()
        arr = src.read(1, window=win, boundless=True, fill_value=np.nan)
        mask = rasterize([(geom, 1)], out_shape=arr.shape,
                         transform=src.window_transform(win), fill=0,
                         dtype="uint8").astype(bool)
        vals = arr[mask].astype("float64")
        if src.nodata is not None:
            vals = vals[vals != src.nodata]
        vals = vals[np.isfinite(vals)]
        if len(vals) == 0:
            return {k: np.nan for k in stat_fns}
        return {k: fn(vals) for k, fn in stat_fns.items()}
    except Exception:
        return {k: np.nan for k in stat_fns}


def shape_feats(g):
    area, per = g.area, g.length
    compact = 4 * np.pi * area / per**2 if per > 0 else np.nan
    hull = g.convex_hull
    solidity = area / hull.area if hull.area > 0 else np.nan
    rect = g.minimum_rotated_rectangle
    if rect.geom_type == "Polygon" and rect.area > 0:
        rectangularity = area / rect.area
        xs, ys = rect.exterior.coords.xy
        e1 = np.hypot(xs[1] - xs[0], ys[1] - ys[0])
        e2 = np.hypot(xs[2] - xs[1], ys[2] - ys[1])
        elong = min(e1, e2) / max(e1, e2) if max(e1, e2) > 0 else np.nan
    else:
        rectangularity, elong = np.nan, np.nan
    return dict(area_m2=area, perim_m=per, compactness=compact,
                elongation=elong, solidity=solidity,
                rectangularity=rectangularity)


def assign_region(pads):
    with rasterio.open(REGION_RASTERS["9t"]["slope"][0]) as s:
        b9 = s.bounds
    with rasterio.open(REGION_RASTERS["mckean"]["slope"][0]) as s:
        bm = s.bounds
    cx, cy = pads.centroid.x, pads.centroid.y
    region = pd.Series("none", index=pads.index)
    region[(cx > b9.left) & (cx < b9.right)
           & (cy > b9.bottom) & (cy < b9.top)] = "9t"
    region[(cx > bm.left) & (cx < bm.right)
           & (cy > bm.bottom) & (cy < bm.top)] = "mckean"
    return region


def build_features(pads):
    med = lambda v: float(np.median(v))
    srcs = {}
    for reg, layers in REGION_RASTERS.items():
        srcs[reg] = {k: [rasterio.open(p) for p in ps if p.exists()]
                     for k, ps in layers.items() if k != "hs"}
    rows = []
    for i, row in pads.iterrows():
        g, reg = row.geometry, row["region"]
        s = srcs[reg]
        f = {"pad_i": row["pad_i"], "region": reg}
        f.update(shape_feats(g))
        annulus = g.buffer(30).difference(g.buffer(2))
        ring = g.boundary.buffer(2)
        f.update({f"slope_{k}": v for k, v in zonal(
            s["slope"], g, {"mean": lambda v: float(np.mean(v)),
                            "std": lambda v: float(np.std(v)),
                            "flatfrac": lambda v: float(np.mean(v < 3))}
        ).items()})
        f["slope_annulus"] = zonal(s["slope"], annulus, {"m": med})["m"]
        f["edge_slope"] = zonal(s["slope"], ring, {"m": med})["m"]
        f["slope_ratio"] = (f["slope_mean"] / f["slope_annulus"]
                            if f.get("slope_annulus") else np.nan)
        f["lrm11_relief"] = zonal(
            s["lrm11"], g, {"r": lambda v: float(np.percentile(v, 95)
                                                 - np.percentile(v, 5))})["r"]
        f["tpi15_mean"] = zonal(s["tpi15"], g,
                                {"m": lambda v: float(np.mean(v))})["m"]
        f["chm_in"] = zonal(s["chm"], g,
                            {"m": lambda v: med(np.clip(v, 0, 45))})["m"]
        f["chm_annulus"] = zonal(s["chm"], annulus,
                                 {"m": lambda v: med(np.clip(v, 0, 45))})["m"]
        f["chm_deficit"] = ((f["chm_annulus"] - f["chm_in"])
                            if pd.notna(f.get("chm_annulus"))
                            and pd.notna(f.get("chm_in")) else np.nan)
        rows.append(f)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(pads)}")
    for s in srcs.values():
        for lst in s.values():
            for d in lst:
                d.close()
    return pd.DataFrame(rows).set_index("pad_i")


def main(k_override=None):
    sfx = "_joint" + (f"_k{k_override}" if k_override else "")
    pads = gpd.read_file(ANN, layer="plat").to_crs(CRS)
    pads.geometry = pads.geometry.make_valid()
    pads = pads[pads.geometry.notna() & ~pads.geometry.is_empty].copy()
    pads = pads.reset_index(drop=True).reset_index(names="pad_i")
    pads["region"] = assign_region(pads)
    print(pads["region"].value_counts().to_dict())
    pads = pads[pads["region"] != "none"].copy()

    cache = OUT_DIR / "pad_features_joint.csv"
    if cache.exists():
        feat = pd.read_csv(cache).set_index("pad_i")
        print(f"loaded cached features for {len(feat)} pads")
    else:
        feat = build_features(pads)
        feat.to_csv(cache)

    X_df = feat[JOINT_FEATS].copy()
    for c in LOG_FEATS:
        X_df[c] = np.log1p(X_df[c])
    keep = X_df.dropna()
    dropped = feat.loc[feat.index.difference(keep.index), "region"]
    print(f"complete features: {len(keep)}/{len(X_df)} "
          f"(dropped by region: {dropped.value_counts().to_dict()})")
    Xs = StandardScaler().fit_transform(keep.values)
    pca = PCA(n_components=0.9, random_state=0)
    Xp = pca.fit_transform(Xs)

    sil = {}
    for k in range(2, 9):
        kmk = KMeans(n_clusters=k, n_init=20, random_state=0).fit(Xp)
        sil[k] = float(silhouette_score(Xp, kmk.labels_))
    best_k = k_override if k_override else max(
        {k: v for k, v in sil.items() if k >= 3}, key=sil.get)
    km = KMeans(n_clusters=best_k, n_init=50, random_state=0).fit(Xp)
    print(f"silhouettes: { {k: round(v, 3) for k, v in sil.items()} } "
          f"-> k={best_k}" + (" (forced)" if k_override else ""))

    keep_idx = keep.index
    feat["cluster"] = pd.Series(km.labels_, index=keep_idx)
    pads = pads.merge(feat.reset_index().drop(columns=["region"]),
                      on="pad_i", how="left")
    pads["cluster_lbl"] = pads["cluster"].map(
        lambda c: f"bin {int(c)}" if pd.notna(c) else "incomplete features")

    summary = feat.groupby("cluster")[JOINT_FEATS].median()
    summary["n_pads"] = feat.groupby("cluster").size()
    summary.to_csv(OUT_DIR / f"cluster_summary{sfx}.csv")
    xtab = pd.crosstab(feat["region"], feat["cluster"])
    print(summary[["area_m2", "slope_ratio", "edge_slope", "chm_deficit",
                   "n_pads"]].round(2))
    print("region x bin:")
    print(xtab)

    with open(OUT_DIR / f"summary{sfx}.json", "w") as fh:
        json.dump({"n_pads": int(len(pads)), "n_clustered": int(len(keep)),
                   "silhouette_by_k": sil, "best_k": best_k,
                   "pca_components": int(pca.n_components_),
                   "region_by_bin": {str(r): xtab.loc[r].to_dict()
                                     for r in xtab.index}},
                  fh, indent=2)

    gout = OUT_DIR / f"pad_bins{sfx}.gpkg"
    if gout.exists():
        gout.unlink()
    pads.drop(columns=[c for c in ["id", "n_roads", "n_not_roads"]
                       if c in pads.columns]).to_file(
        gout, layer="pad_bins", driver="GPKG")
    cats = [(f"bin {i}", f"bin {i} (n={int((feat['cluster'] == i).sum())})",
             CLUSTER_COLORS[i % len(CLUSTER_COLORS)])
            for i in range(best_k)]
    cats.append(("incomplete features", "incomplete features",
                 "220,220,220"))
    embed_styles(str(gout), [("pad_bins", "geom",
                              qml_categorized("fill", "cluster_lbl", cats))])

    z = (summary[JOINT_FEATS] - feat[JOINT_FEATS].mean()) \
        / feat[JOINT_FEATS].std()
    fig, ax = plt.subplots(figsize=(12, 0.6 * best_k + 2))
    im = ax.imshow(z.values, cmap="RdBu_r", vmin=-1.5, vmax=1.5,
                   aspect="auto")
    ax.set_xticks(range(len(JOINT_FEATS)), JOINT_FEATS, rotation=60,
                  ha="right", fontsize=8)
    ax.set_yticks(range(best_k),
                  [f"bin {i} (n={int(summary['n_pads'].iloc[i])})"
                   for i in range(best_k)])
    fig.colorbar(im, label="median z-score")
    ax.set_title("Pad morphology bins (9t + McKean) — median z-score")
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"fig_cluster_profile{sfx}.png", dpi=150)

    # montage: 6 closest-to-center per bin, region-labeled chips
    HALF = 60
    hs_srcs = {reg: [rasterio.open(p) for p in REGION_RASTERS[reg]["hs"]
                     if p.exists()] for reg in REGION_RASTERS}
    fig, axes = plt.subplots(best_k, 6, figsize=(6 * 2.1, best_k * 2.1))
    axes = np.atleast_2d(axes)
    for ci in range(best_k):
        members = keep_idx[km.labels_ == ci]
        d = np.linalg.norm(Xp[km.labels_ == ci] - km.cluster_centers_[ci],
                           axis=1)
        show = members[np.argsort(d)[:6]]
        for j in range(6):
            ax = axes[ci, j]
            ax.axis("off")
            if j >= len(show):
                continue
            prow = pads.loc[pads["pad_i"] == show[j]].iloc[0]
            geom, reg = prow.geometry, feat.loc[show[j], "region"]
            c = geom.centroid
            hs = pick_src(hs_srcs[reg], (c.x - HALF, c.y - HALF,
                                         c.x + HALF, c.y + HALF))
            if hs is None:
                continue
            win = from_bounds(c.x - HALF, c.y - HALF, c.x + HALF,
                              c.y + HALF, hs.transform)
            img = hs.read(1, window=win, boundless=True,
                          fill_value=0).astype("float64")
            if hs.nodata is not None:
                img[img == hs.nodata] = np.nan
            valid = img[np.isfinite(img)]
            if len(valid) == 0:
                continue
            lo, hi = np.percentile(valid, [2, 98])
            ax.imshow(img, cmap="gray", vmin=lo, vmax=max(hi, lo + 1))
            tr = hs.window_transform(win)
            ext = (geom.exterior.coords if geom.geom_type == "Polygon"
                   else max(geom.geoms, key=lambda g: g.area).exterior.coords)
            xs, ys = zip(*[((x - tr.c) / tr.a, (y - tr.f) / tr.e)
                           for x, y in ext])
            ax.plot(xs, ys, color="orange", lw=1.0)
            ax.text(0.02, 0.02, reg, transform=ax.transAxes, fontsize=7,
                    color="yellow", va="bottom")
            if j == 0:
                ax.set_title(f"bin {ci}", loc="left", fontsize=11)
    for lst in hs_srcs.values():
        for d in lst:
            d.close()
    fig.suptitle("Pad bins (9t + McKean) — hillshade chips (120 m)", y=1.0)
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"fig_cluster_montage{sfx}.png", dpi=140,
                bbox_inches="tight")
    print(f"outputs in {OUT_DIR}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=None,
                    help="force k instead of silhouette selection")
    main(ap.parse_args().k)
