"""Split the 9t annotated roads into bold and faint layers.

Applies the discriminator measured in [[road_bold_vs_faint]] to every road in
`annotations/roads.shp` clipped to 9t, and writes two GeoPackage layers.

The discriminator is the **local-z contrast**: how many robust local sigma the
road departs from its own 25-60 m surroundings. Positive openness is the primary
score — it separated the 29 exemplars perfectly, is genuinely continuous
(2.2 M unique raster values), and unlike the raw difference it is not fooled by a
quiet neighbourhood.

Deliberately EXCLUDED from the score:
  dist_pad_m, road_density_100m_km  — separate the exemplars perfectly but all 8
      bold exemplars touch a pad, so these encode the pad confound rather than
      boldness. Including them would relabel "near a pad" as "bold".
  roughness_11  — quantised to a sqrt(k) ladder (1,032 unique values in 81 M
      cells); the exemplar gap spans a single rung.
  chm / dsm / gdens / inten  — CHM is zero-inflated so its z-contrast divides by
      a near-zero MAD; gdens and inten are 42-45% nodata.

Outputs (data/derivatives/experiments/road_morphology_bins/):
    roads_bold_faint_9t_05.gpkg
        layer `roads_bold_9t`   — roads scoring bold-like
        layer `roads_faint_9t`  — roads scoring faint-like
        layer `roads_scored_9t` — all roads with scores, for thresholding by hand
    roads_bold_faint_9t_05_scores.csv
    fig_roads_bold_faint_split_9t_05.png

CLI:
  python notebooks/wellsight_v2/analysis/_classify_9t_roads_bold_faint.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from shapely.ops import unary_union

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS  # noqa: E402

R9 = DERIV / "tiles" / "9t"
ANN = DERIV / "annotations"
OUT = DERIV / "experiments" / "road_morphology_bins"

# Transects every 5 m and roads chopped into 50 m segments -> ~10 transects per
# scored unit. Whole-road scoring was wrong: within-road SD of the score (2.230)
# EXCEEDS between-road SD (1.892), ICC 0.419, and the median road's own
# transects vote only 57% bold. Boldness is a property of a place along a road,
# not of a road, so the scored unit has to be a segment.
STEP, HALF_W, DX = 5.0, 60.0, 0.5
MIN_LEN = 20.0
SEG_M = 50.0

# Only channels that survived the trust audit in road_bold_vs_faint.md.
RASTERS = {
    "dem":      R9 / "dem_9t_05.tif",
    "slope":    R9 / "slope_9t_05.tif",
    "opos":     R9 / "openness_pos_9t_05.tif",
    "oneg":     R9 / "openness_neg_9t_05.tif",
    "lrm5":     R9 / "lrm_5_9t_05.tif",
    "lrm25":    R9 / "lrm_25_9t_05.tif",
    "tpi15":    R9 / "tpi_15_9t_05.tif",
    "relief10": R9 / "local_relief_10_9t_05.tif",
}
PRIMARY = "opos_zcontrast"
PANEL = ["opos_zcontrast", "lrm25_zcontrast", "tpi15_zcontrast",
         "slope_zcontrast", "relief10_zcontrast", "oneg_zcontrast",
         "incision_depth_m"]


def segmentise(gdf, seg_m=SEG_M):
    """Chop each road into ~seg_m pieces, carrying the parent road id."""
    from shapely.geometry import LineString
    rows = []
    for pid, geom in zip(gdf.index.values, gdf.geometry.values):
        parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
        for part in parts:
            if part.length < MIN_LEN:
                continue
            n = max(1, int(round(part.length / seg_m)))
            edges = np.linspace(0.0, part.length, n + 1)
            for t0, t1 in zip(edges[:-1], edges[1:]):
                k = max(2, int(np.ceil((t1 - t0) / 5.0)) + 1)
                ts = np.linspace(t0, t1, k)
                ls = LineString([(p.x, p.y) for p in
                                 (part.interpolate(x) for x in ts)])
                if ls.length > 1.0:
                    rows.append({"parent_road": int(pid), "geometry": ls})
    out = gpd.GeoDataFrame(rows, crs=gdf.crs)
    out["length_m"] = out.length
    return out.reset_index(drop=True)


def build_transects(gdf):
    offs = np.arange(-HALF_W, HALF_W + DX * 0.5, DX)
    X, Y, RI, TI = [], [], [], []
    tc = 0
    for ri, geom in zip(gdf.index.values, gdf.geometry.values):
        parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
        for part in parts:
            if part.length < MIN_LEN:
                continue
            n = max(2, int(part.length / STEP))
            for s in np.linspace(part.length * 0.05, part.length * 0.95, n):
                p0 = part.interpolate(max(0.0, s - 2.0))
                p1 = part.interpolate(min(part.length, s + 2.0))
                dx, dy = p1.x - p0.x, p1.y - p0.y
                nn = np.hypot(dx, dy)
                if nn < 1e-6:
                    continue
                nx, ny = -dy / nn, dx / nn
                c = part.interpolate(s)
                X.append(c.x + nx * offs)
                Y.append(c.y + ny * offs)
                RI.append(np.full(len(offs), ri))
                TI.append(np.full(len(offs), tc))
                tc += 1
    return (np.concatenate(X), np.concatenate(Y), np.concatenate(RI),
            np.concatenate(TI), offs)


def sample(path, xs, ys):
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
        nod, inv = src.nodata, ~src.transform
        H, W = a.shape
    c, r = inv * (xs, ys)
    c = np.rint(c).astype(np.int64)
    r = np.rint(r).astype(np.int64)
    ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
    o = np.full(xs.shape, np.nan, np.float32)
    o[ok] = a[r[ok], c[ok]]
    if nod is not None:
        o[o == nod] = np.nan
    o[o < -1e30] = np.nan
    del a
    return o


def featurise(gdf, tag):
    """Per-road local-z contrast features. Identical maths for exemplars and
    the full road set, so the threshold transfers."""
    xs, ys, ri, ti, offs = build_transects(gdf)
    n_t = ti.max() + 1
    n_off = len(offs)
    t_road = ri.reshape(n_t, n_off)[:, 0]
    road_m = np.abs(offs) <= 3.0
    ctx_m = (np.abs(offs) >= 25.0) & (np.abs(offs) <= HALF_W)
    print(f"  [{tag}] {len(gdf)} roads -> {n_t} transects, {len(xs):,} samples")

    per_t = {}
    dem = None
    for nm, p in RASTERS.items():
        arr = sample(p, xs, ys).reshape(n_t, n_off)
        if nm == "dem":
            dem = arr
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rv = np.nanmedian(np.where(road_m[None, :], arr, np.nan), axis=1)
            cv = np.nanmedian(np.where(ctx_m[None, :], arr, np.nan), axis=1)
            cmad = np.nanmedian(
                np.abs(np.where(ctx_m[None, :], arr, np.nan) - cv[:, None]),
                axis=1) * 1.4826
        pos = cmad[np.isfinite(cmad) & (cmad > 0)]
        floor = np.nanpercentile(pos, 5) if pos.size else 1e-6
        per_t[f"{nm}_zcontrast"] = (rv - cv) / np.maximum(cmad, floor)

    # incision depth, detrended on |d| in [30, 60] so the road never shapes its
    # own trend surface
    outer = (np.abs(offs) >= 30.0) & (np.abs(offs) <= HALF_W)
    resid = np.full_like(dem, np.nan)
    for i in range(n_t):
        m = outer & np.isfinite(dem[i])
        if m.sum() < 10:
            continue
        cf = np.polyfit(offs[m], dem[i][m], 1)
        resid[i] = dem[i] - np.polyval(cf, offs)
    L = (offs >= -12) & (offs <= -3)
    Rg = (offs >= 3) & (offs <= 12)
    C = np.abs(offs) <= 2
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bl = np.nanmax(np.where(L[None, :], resid, np.nan), axis=1)
        br = np.nanmax(np.where(Rg[None, :], resid, np.nan), axis=1)
        tr = np.nanmin(np.where(C[None, :], resid, np.nan), axis=1)
    per_t["incision_depth_m"] = np.fmax((bl + br) / 2 - tr, 0)

    d = pd.DataFrame(per_t)
    d["road"] = t_road
    agg = d.groupby("road").median(numeric_only=True)
    agg["n_transects"] = d.groupby("road").size()
    return agg


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    blocks = gpd.read_file(R9 / "pit_blocks_9t.gpkg")
    region = unary_union(blocks.geometry.values)

    # ---- exemplars ---------------------------------------------------------
    ex = []
    for lab, nm in ((1, "bold_roads"), (0, "faint_roads")):
        g = gpd.read_file(ANN / f"{nm}.shp")
        g = (g.set_crs(4326) if g.crs is None else g).to_crs(DST_CRS)
        g = g[g.intersects(region)].copy()
        g["label"] = lab
        ex.append(g[["geometry", "label"]])
    ex = gpd.GeoDataFrame(pd.concat(ex, ignore_index=True),
                          geometry="geometry", crs=DST_CRS)
    exf = featurise(ex, "exemplars").join(ex[["label"]])

    b = exf[exf.label == 1][PRIMARY]
    f = exf[exf.label == 0][PRIMARY]
    print(f"\n{PRIMARY}:  bold  max {b.max():.3f}  median {b.median():.3f}")
    print(f"{' ' * len(PRIMARY)}   faint min {f.min():.3f}  median {f.median():.3f}")
    gap = f.min() - b.max()
    thr = (b.max() + f.min()) / 2.0
    print(f"  separation gap {gap:+.3f} sigma;  threshold {thr:.3f} "
          f"(bold if {PRIMARY} <= threshold)")
    if gap <= 0:
        print("  WARNING: exemplars overlap on the primary score — the "
              "threshold is a compromise, not a clean cut")

    # honest-ish check: leave-one-out on a single-feature midpoint rule.
    # Perfect separation makes this optimistic; it is reported, not trusted.
    loo = 0
    for i in exf.index:
        tr_ = exf.drop(index=i)
        bb, ff = tr_[tr_.label == 1][PRIMARY], tr_[tr_.label == 0][PRIMARY]
        t_ = (bb.max() + ff.min()) / 2.0
        pred = 1 if exf.loc[i, PRIMARY] <= t_ else 0
        loo += int(pred == exf.loc[i, "label"])
    print(f"  leave-one-out accuracy {loo}/{len(exf)} "
          f"({loo/len(exf)*100:.0f}%) — optimistic, the classes are separable")

    # ---- all 9t annotated roads --------------------------------------------
    roads = gpd.read_file(ANN / "roads.shp").to_crs(DST_CRS)
    roads = roads[roads.intersects(region)].copy()
    roads["geometry"] = roads.geometry.intersection(region)
    roads = roads[~roads.is_empty].reset_index(drop=True)
    roads["length_m"] = roads.length
    roads = roads[roads.length_m >= MIN_LEN].reset_index(drop=True)
    print(f"\nroads.shp -> 9t: {len(roads)} roads, "
          f"{roads.length_m.sum()/1000:.2f} km")
    segs = segmentise(roads)
    print(f"  chopped into {len(segs)} segments of ~{SEG_M:.0f} m")
    rf = featurise(segs, "9t segments")
    out = segs.join(rf, how="inner")

    # Three classes, defined by the EXEMPLAR RANGES rather than a midpoint.
    # 18% of units fall in the gap between the two exemplar ranges; forcing them
    # to a side is what made the first version look random on screen. They are
    # labelled `ambiguous` and shipped as their own layer instead.
    bold_hi = float(b.max())      # bold exemplars are all <= this
    faint_lo = float(f.min())     # faint exemplars are all >= this
    out["class"] = np.where(out[PRIMARY] <= bold_hi, "bold",
                   np.where(out[PRIMARY] >= faint_lo, "faint", "ambiguous"))
    # margin in sigma from the decision boundary — how confident, and which way
    out["margin_sigma"] = (thr - out[PRIMARY]).round(3)
    out["faint_score"] = out[PRIMARY].round(3)

    print(f"\n=== split of the ANNOTATED 9t network ({SEG_M:.0f} m segments) ===")
    counts = {}
    for c in ("bold", "ambiguous", "faint"):
        s_ = out[out["class"] == c]
        counts[c] = (len(s_), s_.length_m.sum() / 1000)
        print(f"  {c:9s} {len(s_):5d} segs  {s_.length_m.sum()/1000:7.2f} km  "
              f"({len(s_)/len(out)*100:4.1f}%)")
    nb, kb = counts["bold"]
    nf, kf = counts["faint"]
    # Internal consistency of each parent road. Whole-road labelling was
    # arbitrary precisely because so many roads are mixed along their length.
    vote = out.groupby("parent_road")["class"].apply(lambda s: (s == "bold").mean())
    mixed = int(((vote > 0.25) & (vote < 0.75)).sum())
    print(f"\n  parent roads internally MIXED (25-75% bold segments): "
          f"{mixed}/{vote.size} ({mixed/vote.size*100:.0f}%)")
    print("  -> that mixing is why whole-road labels looked arbitrary")
    print(f"\n  {PRIMARY} quantiles over the annotated network:")
    print("   ", out[PRIMARY].quantile([.05, .25, .5, .75, .95]).round(2).to_dict())
    print(f"  exemplar reference: bold median {b.median():.2f}, "
          f"faint median {f.median():.2f}")

    # ---- attach model response + data split --------------------------------
    # Both matter for reading the layers. The road model trained on 9t, so
    # P(road) on train blocks is a memorisation figure and says nothing about
    # whether the class is detectable; only the test blocks test that.
    pr = R9 / "road_unet_1m_recall" / "road_prob.tif"
    if pr.exists():
        with rasterio.open(pr) as s:
            pa = s.read(1).astype(np.float32)
            pinv = ~s.transform
            PH, PW = pa.shape

        def pmean(geom, step=3.0):
            n = max(2, int(geom.length / step))
            v = []
            for t in np.linspace(0, 1, n):
                p = geom.interpolate(t, normalized=True)
                c, r = pinv * (p.x, p.y)
                r, c = int(r), int(c)
                if 0 <= r < PH and 0 <= c < PW and pa[r, c] >= 0:
                    v.append(pa[r, c])
            return float(np.mean(v)) if v else np.nan
        out["P_road"] = [pmean(x) for x in out.geometry]
        del pa
    sp = gpd.sjoin(out[["geometry"]], blocks[["split", "geometry"]],
                   how="left", predicate="intersects")
    out["split"] = sp.groupby(level=0).first()["split"]

    if "P_road" in out.columns:
        te = out[out.split == "test"]
        tr = out[out.split == "train"]
        print("\n=== does the split predict detection? ===")
        for nm, sub in (("train (memorised)", tr), ("test (held out)", te)):
            if not len(sub):
                continue
            bb = sub[sub["class"] == "bold"]
            ff = sub[sub["class"] == "faint"]
            print(f"  {nm:20s} bold {bb.P_road.mean():.3f} "
                  f"({(bb.P_road>=.5).mean()*100:3.0f}% >=0.5, n={len(bb)})   "
                  f"faint {ff.P_road.mean():.3f} "
                  f"({(ff.P_road>=.5).mean()*100:3.0f}% >=0.5, n={len(ff)})")

    # ---- write -------------------------------------------------------------
    gp = OUT / "roads_bold_faint_9t_05.gpkg"
    keep = ["geometry", "parent_road", "length_m", "class", "faint_score",
            "margin_sigma", "n_transects", "P_road", "split"] + [
            c for c in PANEL if c in out.columns]
    keep = [c for c in keep if c in out.columns]
    o = out[keep]
    o[o["class"] == "bold"].to_file(gp, layer="roads_bold_9t", driver="GPKG")
    o[o["class"] == "faint"].to_file(gp, layer="roads_faint_9t", driver="GPKG")
    o[o["class"] == "ambiguous"].to_file(gp, layer="roads_ambiguous_9t",
                                         driver="GPKG")
    o.to_file(gp, layer="roads_scored_9t", driver="GPKG")
    o.drop(columns="geometry").to_csv(
        OUT / "roads_bold_faint_9t_05_scores.csv", index=False)

    (OUT / "roads_bold_faint_9t_05_threshold.json").write_text(json.dumps({
        "primary_score": PRIMARY, "threshold": float(thr),
        "rule": f"bold if {PRIMARY} <= {thr:.4f}",
        "exemplar_bold_max": float(b.max()), "exemplar_faint_min": float(f.min()),
        "separation_gap_sigma": float(gap),
        "loo_accuracy": f"{loo}/{len(exf)}",
        "excluded_features": ["dist_pad_m", "road_density_100m_km",
                              "roughness_11", "chm", "dsm", "gdens", "inten"],
        "n_bold": nb, "n_faint": nf, "km_bold": round(kb, 2),
        "km_faint": round(kf, 2),
    }, indent=2))

    # ---- figure ------------------------------------------------------------
    fig, ax = plt.subplots(1, 2, figsize=(15, 6))
    ax[0].hist(out[PRIMARY].clip(-12, 4), bins=60, color="0.6",
               label=f"annotated 9t roads (n={len(out)})")
    ax[0].axvspan(bold_hi, faint_lo, color="0.85", alpha=0.9, zorder=0,
                  label="ambiguous band (gap between exemplar ranges)")
    ax[0].axvline(bold_hi, color="#c1272d", ls="--", lw=1.4,
                  label=f"bold cut {bold_hi:.2f}")
    ax[0].axvline(faint_lo, color="#2b6cb0", ls="--", lw=1.4,
                  label=f"faint cut {faint_lo:.2f}")
    for v, c, lb in ((b, "#c1272d", "bold exemplars"),
                     (f, "#2b6cb0", "faint exemplars")):
        ax[0].plot(np.clip(v, -12, 4), np.full(len(v), ax[0].get_ylim()[1] * 0.5),
                   "|", color=c, ms=18, mew=2.5, label=lb)
    ax[0].set_xlabel(f"{PRIMARY}  (local sigma vs 25-60 m surroundings)")
    ax[0].set_ylabel("roads")
    ax[0].set_title("Where the annotated network sits\nrelative to the exemplars",
                    fontsize=10)
    ax[0].legend(fontsize=8)

    hs = R9 / "hillshade_9t_05.tif"
    if hs.exists():
        from rasterio.plot import plotting_extent
        with rasterio.open(hs) as r:
            im = r.read(1).astype(np.float32)
            im[im < 0] = np.nan
            ax[1].imshow(im, cmap="gray", extent=plotting_extent(r),
                         origin="upper", vmin=np.nanpercentile(im, 2),
                         vmax=np.nanpercentile(im, 98))
    o[o["class"] == "ambiguous"].plot(
        ax=ax[1], color="#bbbbbb", linewidth=0.7,
        label=f"ambiguous ({counts['ambiguous'][0]}, {counts['ambiguous'][1]:.0f} km)")
    o[o["class"] == "bold"].plot(ax=ax[1], color="#c1272d", linewidth=1.3,
                                 label=f"bold ({nb}, {kb:.0f} km)")
    o[o["class"] == "faint"].plot(ax=ax[1], color="#2b6cb0", linewidth=1.1,
                                  label=f"faint ({nf}, {kf:.0f} km)")
    ax[1].legend(fontsize=8, loc="upper right")
    ax[1].set_xticks([])
    ax[1].set_yticks([])
    ax[1].set_title(f"9t annotated roads, {SEG_M:.0f} m segments",
                    fontsize=10)
    fig.suptitle("Bold vs faint split of the annotated 9t road network",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT / "fig_roads_bold_faint_split_9t_05.png", dpi=140)
    plt.close(fig)

    print(f"\nwrote:\n  {gp}"
          f"\n    layers: roads_bold_9t, roads_faint_9t, roads_scored_9t"
          f"\n  {OUT / 'roads_bold_faint_9t_05_scores.csv'}"
          f"\n  {OUT / 'roads_bold_faint_9t_05_threshold.json'}"
          f"\n  {OUT / 'fig_roads_bold_faint_split_9t_05.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
