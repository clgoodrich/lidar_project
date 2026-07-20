"""Unsupervised pad morphology bins on 9t — no age target, just archetypes.

Per-pad features (9t pads only — needs the 9t 0.5 m rasters):
  shape        area, perimeter, compactness 4piA/P^2, elongation, solidity,
               rectangularity (area / min-rotated-rect area)
  composition  n_pits inside, distance to nearest annotated road,
               n catalog wells within 50 m
  terrain      slope mean/std inside; slope median in a 30 m annulus;
               slope_ratio (inside/annulus — engineered-flat detector);
               flat_frac (slope < 3 deg); edge_slope (mean slope in a
               +/-2 m boundary ring — edge crispness); lrm11 p95-p5 inside
               (internal relief); tpi15 mean (bench/fill signature)
  canopy       chm median inside; chm median in annulus; chm_deficit
               (annulus - inside — regrowth clock proxy)

Clustering: StandardScaler -> PCA(0.9) -> KMeans, k chosen by silhouette
over k=3..8. Deterministic (random_state=0).

Outputs (OUT_DIR):
  pad_bins.gpkg            pads + features + cluster, style embedded
  pad_features.csv         full feature table
  cluster_summary.csv      per-cluster median of every feature + count
  fig_cluster_montage.png  6 example hillshade chips per cluster
  fig_cluster_profile.png  z-scored median feature heatmap per cluster
  summary.json             k selection, silhouettes, PCA variance

Reproduce: python notebooks/wellsight_v2/analysis/_pad_morphology_bins.py
"""
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

ROOT = Path(__file__).resolve().parents[3]
T9 = ROOT / "data/derivatives/tiles/9t"
ANN = ROOT / "data/derivatives/annotations/annotations_proj.gpkg"
WELLS = ROOT / "data/derivatives/venango_wells_all.gpkg"
OUT_DIR = ROOT / "data/derivatives/experiments/pad_morphology_bins"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:6346"

RASTERS = {"slope": T9 / "slope_9t_05.tif",
           "lrm11": T9 / "lrm_11_9t_05.tif",
           "tpi15": T9 / "tpi_15_9t_05.tif",
           "chm": T9 / "chm_9t_05.tif",
           "hs": T9 / "hillshade_9t_05.tif"}

CLUSTER_COLORS = ["141,211,199", "255,127,0", "31,120,180", "227,26,28",
                  "106,61,154", "178,223,138", "251,154,153", "253,191,111"]


def zonal(src, geom, stat_fns):
    """Rasterize one geometry into its bounding window; return masked stats."""
    b = geom.bounds
    try:
        win = from_bounds(b[0] - 1, b[1] - 1, b[2] + 1, b[3] + 1,
                          src.transform)
        win = win.round_offsets().round_lengths()
        arr = src.read(1, window=win, boundless=True,
                       fill_value=src.nodata if src.nodata is not None
                       else np.nan)
        tr = src.window_transform(win)
        mask = rasterize([(geom, 1)], out_shape=arr.shape, transform=tr,
                         fill=0, dtype="uint8").astype(bool)
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


def main():
    pads = gpd.read_file(ANN, layer="plat").to_crs(CRS)
    pads.geometry = pads.geometry.make_valid()
    pads = pads[pads.geometry.notna() & ~pads.geometry.is_empty].copy()
    pits = gpd.read_file(ANN, layer="pit_inside").to_crs(CRS)
    roads = gpd.read_file(ANN, layer="roads").to_crs(CRS)
    wells = gpd.read_file(WELLS).to_crs(CRS)

    # keep pads inside the 9t raster footprint
    with rasterio.open(RASTERS["slope"]) as s:
        l9, b9, r9, t9 = s.bounds
    pads = pads[(pads.centroid.x > l9) & (pads.centroid.x < r9) &
                (pads.centroid.y > b9) & (pads.centroid.y < t9)].copy()
    pads = pads.reset_index(drop=True).reset_index(names="pad_i")
    print(f"9t pads: {len(pads)}")

    rows = []
    srcs = {k: rasterio.open(p) for k, p in RASTERS.items() if k != "hs"}
    med = lambda v: float(np.median(v))
    for i, row in pads.iterrows():
        g = row.geometry
        f = {"pad_i": row["pad_i"]}
        f.update(shape_feats(g))
        f["n_pits"] = int(pits.intersects(g).sum())
        f["d_road_m"] = float(roads.distance(g).min()) if len(roads) else np.nan
        f["n_wells_50m"] = int((wells.distance(g) <= 50).sum())

        annulus = g.buffer(30).difference(g.buffer(2))
        ring = g.boundary.buffer(2)
        f.update({f"slope_{k}": v for k, v in zonal(
            srcs["slope"], g, {"mean": lambda v: float(np.mean(v)),
                               "std": lambda v: float(np.std(v)),
                               "flatfrac": lambda v: float(np.mean(v < 3))}
        ).items()})
        f["slope_annulus"] = zonal(srcs["slope"], annulus, {"m": med})["m"]
        f["edge_slope"] = zonal(srcs["slope"], ring, {"m": med})["m"]
        f["slope_ratio"] = (f["slope_mean"] / f["slope_annulus"]
                            if f.get("slope_annulus") else np.nan)
        f["lrm11_relief"] = zonal(
            srcs["lrm11"], g,
            {"r": lambda v: float(np.percentile(v, 95)
                                  - np.percentile(v, 5))})["r"]
        f["tpi15_mean"] = zonal(srcs["tpi15"], g,
                                {"m": lambda v: float(np.mean(v))})["m"]
        f["chm_in"] = zonal(srcs["chm"], g,
                            {"m": lambda v: med(np.clip(v, 0, 45))})["m"]
        f["chm_annulus"] = zonal(srcs["chm"], annulus,
                                 {"m": lambda v: med(np.clip(v, 0, 45))})["m"]
        f["chm_deficit"] = ((f["chm_annulus"] - f["chm_in"])
                            if pd.notna(f.get("chm_annulus"))
                            and pd.notna(f.get("chm_in")) else np.nan)
        rows.append(f)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(pads)}")
    for s in srcs.values():
        s.close()

    feat = pd.DataFrame(rows).set_index("pad_i")
    feat.to_csv(OUT_DIR / "pad_features.csv")

    fcols = [c for c in feat.columns]
    X_df = feat[fcols].copy()
    # log-scale the heavy-tailed size features
    for c in ["area_m2", "perim_m", "n_wells_50m", "d_road_m"]:
        X_df[c] = np.log1p(X_df[c])
    keep = X_df.dropna()
    print(f"pads with complete features: {len(keep)}/{len(X_df)}")
    Xs = StandardScaler().fit_transform(keep.values)
    pca = PCA(n_components=0.9, random_state=0)
    Xp = pca.fit_transform(Xs)

    sil = {}
    for k in range(3, 9):
        km = KMeans(n_clusters=k, n_init=20, random_state=0).fit(Xp)
        sil[k] = float(silhouette_score(Xp, km.labels_))
    best_k = max(sil, key=sil.get)
    km = KMeans(n_clusters=best_k, n_init=50, random_state=0).fit(Xp)
    print(f"silhouettes: {sil} -> k={best_k}")

    keep_idx = keep.index
    feat["cluster"] = pd.Series(km.labels_, index=keep_idx)
    pads = pads.merge(feat.reset_index(), on="pad_i", how="left")
    pads["cluster_lbl"] = pads["cluster"].map(
        lambda c: f"bin {int(c)}" if pd.notna(c) else "incomplete features")

    summary = feat.groupby("cluster")[fcols].median()
    summary["n_pads"] = feat.groupby("cluster").size()
    summary.to_csv(OUT_DIR / "cluster_summary.csv")
    print(summary[["area_m2", "slope_ratio", "edge_slope", "chm_deficit",
                   "n_pits", "n_pads"]].round(2))

    with open(OUT_DIR / "summary.json", "w") as fh:
        json.dump({"n_pads_9t": int(len(pads)),
                   "n_clustered": int(len(keep)),
                   "silhouette_by_k": sil, "best_k": best_k,
                   "pca_components": int(pca.n_components_),
                   "pca_var": [round(float(v), 3)
                               for v in pca.explained_variance_ratio_]},
                  fh, indent=2)

    gout = OUT_DIR / "pad_bins.gpkg"
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

    # z-scored median heatmap
    z = (summary[fcols] - feat[fcols].mean()) / feat[fcols].std()
    fig, ax = plt.subplots(figsize=(12, 0.6 * best_k + 2))
    im = ax.imshow(z.values, cmap="RdBu_r", vmin=-1.5, vmax=1.5,
                   aspect="auto")
    ax.set_xticks(range(len(fcols)), fcols, rotation=60, ha="right",
                  fontsize=8)
    ax.set_yticks(range(best_k),
                  [f"bin {i} (n={int(summary['n_pads'].iloc[i])})"
                   for i in range(best_k)])
    fig.colorbar(im, label="median z-score")
    ax.set_title("Pad morphology bins — feature profile (median z-score)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_cluster_profile.png", dpi=150)

    # hillshade chip montage: 6 pads nearest each cluster center
    HALF = 60  # m -> 120 m chips
    with rasterio.open(RASTERS["hs"]) as hs:
        fig, axes = plt.subplots(best_k, 6,
                                 figsize=(6 * 2.1, best_k * 2.1))
        axes = np.atleast_2d(axes)
        for ci in range(best_k):
            members = keep_idx[km.labels_ == ci]
            d = np.linalg.norm(Xp[km.labels_ == ci]
                               - km.cluster_centers_[ci], axis=1)
            show = members[np.argsort(d)[:6]]
            for j in range(6):
                ax = axes[ci, j]
                ax.axis("off")
                if j >= len(show):
                    continue
                geom = pads.loc[pads["pad_i"] == show[j],
                                "geometry"].iloc[0]
                c = geom.centroid
                win = from_bounds(c.x - HALF, c.y - HALF, c.x + HALF,
                                  c.y + HALF, hs.transform)
                img = hs.read(1, window=win, boundless=True, fill_value=0)
                ax.imshow(img, cmap="gray", vmin=1, vmax=255)
                tr = hs.window_transform(win)
                xs, ys = zip(*[((x - tr.c) / tr.a, (y - tr.f) / tr.e)
                               for x, y in
                               (geom.exterior.coords if geom.geom_type ==
                                "Polygon" else
                                max(geom.geoms,
                                    key=lambda g: g.area).exterior.coords)])
                ax.plot(xs, ys, color="orange", lw=1.0)
                if j == 0:
                    ax.set_title(f"bin {ci}", loc="left", fontsize=11,
                                 color="k")
        fig.suptitle("Pad morphology bins — hillshade chips (120 m), "
                     "closest-to-center examples", y=1.0)
        fig.tight_layout()
        fig.savefig(OUT_DIR / "fig_cluster_montage.png", dpi=140,
                    bbox_inches="tight")
    print(f"outputs in {OUT_DIR}")


if __name__ == "__main__":
    main()
