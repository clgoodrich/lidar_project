"""Supervised contrast of the user's bold_roads vs faint_roads exemplars (9t).

`_road_morphology_bins.py` concluded, unsupervised, that 9t roads are one width
and that their incision depth is a continuum rather than two populations. The
user then hand-labelled exemplars of each variety. This script tests that
conclusion against those labels, and — as asked — compares not only the road
cross-section but the SURROUNDINGS and the road-to-surround CONTRAST.

Three bands per transect:
    road     |d| <= 3 m       the tread itself
    near     5 <= |d| <= 15   berms, shoulders, spoil
    context  25 <= |d| <= 60  the landscape the road sits in

For every raster each band gets a statistic, plus explicit contrast terms
(road - context, road / context). Proximity/landscape-position features are
added separately (distance to pads, pits, wells, drainage, other roads; local
road density).

Statistics are reported at TWO levels:
  - road level   (n = 8 vs 21) — honest, independent, low power
  - transect level             — more power, but transects within one road are
                                 correlated, so it is pseudo-replication and is
                                 labelled as such. Never quoted as the p-value.

Outputs (data/derivatives/experiments/road_morphology_bins/):
    bold_vs_faint_features_9t_05.csv        per-road feature table + label
    bold_vs_faint_effectsizes_9t_05.csv     ranked Cliff's delta / AUC / p
    bold_vs_faint_summary_9t_05.json        headline numbers
    fig_bold_vs_faint_profiles_9t_05.png    median transect profiles, 6 rasters
    fig_bold_vs_faint_effects_9t_05.png     ranked effect sizes
    fig_bold_vs_faint_context_9t_05.png     road vs context bar comparison

CLI:
  python notebooks/wellsight_v2/s7_analysis/_bold_vs_faint_roads.py
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
from _common import DERIV, DST_CRS, path_for  # noqa: E402

R9 = path_for("nine_t")
ANN = path_for("truth")
OUT = path_for("experiments") / "road_morphology_bins"

STEP = 10.0        # m between transects
HALF_W = 60.0      # m each side — wide enough to hold real context
DX = 0.5

BANDS = {
    "road":    lambda d: np.abs(d) <= 3.0,
    "near":    lambda d: (np.abs(d) >= 5.0) & (np.abs(d) <= 15.0),
    "context": lambda d: (np.abs(d) >= 25.0) & (np.abs(d) <= HALF_W),
}

RASTERS = {
    "dem":       R9 / "dem_9t_05.tif",
    "dsm":       R9 / "dsm_9t_05.tif",
    "slope":     R9 / "slope_9t_05.tif",
    "chm":       R9 / "chm_9t_05.tif",
    "inten":     R9 / "intensity_ground_9t_05.tif",
    "lrm5":      R9 / "lrm_5_9t_05.tif",
    "lrm25":     R9 / "lrm_25_9t_05.tif",
    "tpi15":     R9 / "tpi_15_9t_05.tif",
    "opos":      R9 / "openness_pos_9t_05.tif",
    "oneg":      R9 / "openness_neg_9t_05.tif",
    "rough":     R9 / "roughness_11_9t_05.tif",
    "relief10":  R9 / "local_relief_10_9t_05.tif",
    "gdens":     R9 / "ground_density_9t_05.tif",
}
# statistic per raster: canopy-like layers want p90 (CHM is zero-inflated),
# everything else wants a median.
P90 = {"chm", "dsm"}


def build_transects(gdf):
    offs = np.arange(-HALF_W, HALF_W + DX * 0.5, DX)
    X, Y, RI, TI = [], [], [], []
    tc = 0
    for ri, geom in zip(gdf.index.values, gdf.geometry.values):
        parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
        for part in parts:
            if part.length < 20:
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
    return (np.concatenate(X), np.concatenate(Y),
            np.concatenate(RI), np.concatenate(TI), offs)


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


def cliffs_delta(a, b):
    """Non-parametric effect size. +1 = a always greater, -1 = b always."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return np.nan, np.nan
    gt = sum((a[:, None] > b[None, :]).sum(axis=1))
    lt = sum((a[:, None] < b[None, :]).sum(axis=1))
    n = len(a) * len(b)
    delta = (gt - lt) / n
    auc = gt / n + 0.5 * (n - gt - lt) / n     # prob(bold > faint)
    return float(delta), float(auc)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    blocks = gpd.read_file(R9 / "pit_blocks_9t.gpkg")
    region = unary_union(blocks.geometry.values)

    frames = []
    for label, name in ((1, "bold_roads"), (0, "faint_roads")):
        g = gpd.read_file(ANN / f"{name}.shp")
        g = (g.set_crs(4326) if g.crs is None else g).to_crs(DST_CRS)
        g = g[g.intersects(region)].copy()
        g["label"] = label
        g["kind"] = "bold" if label else "faint"
        frames.append(g[["geometry", "label", "kind"]])
    gdf = pd.concat(frames, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=DST_CRS)
    gdf["length_m"] = gdf.length
    print(f"bold {int((gdf.label==1).sum())} roads / "
          f"{gdf[gdf.label==1].length_m.sum()/1000:.2f} km   "
          f"faint {int((gdf.label==0).sum())} roads / "
          f"{gdf[gdf.label==0].length_m.sum()/1000:.2f} km")

    xs, ys, ri, ti, offs = build_transects(gdf)
    n_t = ti.max() + 1
    n_off = len(offs)
    t_road = ri.reshape(n_t, n_off)[:, 0]
    print(f"transects: {n_t} (+/-{HALF_W:.0f} m at {DX} m) = {len(xs):,} samples")

    prof, per_t = {}, {}
    for nm, p in RASTERS.items():
        if not p.exists():
            print(f"  MISSING {p.name}")
            continue
        prof[nm] = sample(p, xs, ys).reshape(n_t, n_off)
        nanfrac = np.isnan(prof[nm]).mean()
        for bn, fn in BANDS.items():
            m = fn(offs)
            sub = np.where(m[None, :], prof[nm], np.nan)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                v = (np.nanpercentile(sub, 90, axis=1) if nm in P90
                     else np.nanmedian(sub, axis=1))
            per_t[f"{nm}_{bn}"] = v
        per_t[f"{nm}_contrast"] = per_t[f"{nm}_road"] - per_t[f"{nm}_context"]

        # LOCAL-Z CONTRAST — the "does it stand out from its own surroundings"
        # measure. A raw difference conflates a strong feature with a quiet
        # neighbourhood: a faint trace in smooth ground can be more detectable
        # than a bold road in broken ground. Dividing by the context band's own
        # robust spread (MAD -> sigma) asks how many local sigma the road
        # departs by, which is what "stands out" actually means and is the
        # quantity a detector effectively sees.
        cm = fn_ctx = BANDS["context"](offs)
        ctx = np.where(cm[None, :], prof[nm], np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c_med = np.nanmedian(ctx, axis=1)
            c_mad = np.nanmedian(np.abs(ctx - c_med[:, None]), axis=1) * 1.4826
        # floor the spread so a degenerate/quantized context cannot manufacture
        # a huge z; floored at the raster's own 5th-percentile non-zero MAD
        floor = np.nanpercentile(c_mad[c_mad > 0], 5) if np.any(c_mad > 0) else 1e-6
        per_t[f"{nm}_zcontrast"] = ((per_t[f"{nm}_road"] - c_med)
                                    / np.maximum(c_mad, floor))
        per_t[f"{nm}_ctx_spread"] = c_mad
        print(f"  {nm:9s} nan {nanfrac*100:5.2f}%   context spread (median MAD) "
              f"{np.nanmedian(c_mad):.4f}")

    # detrended cross-section -> incision depth, width
    z = prof["dem"]
    outer = (np.abs(offs) >= 30.0) & (np.abs(offs) <= HALF_W)
    resid = np.full_like(z, np.nan)
    hill = np.full(n_t, np.nan, np.float32)
    for i in range(n_t):
        m = outer & np.isfinite(z[i])
        if m.sum() < 10:
            continue
        cf = np.polyfit(offs[m], z[i][m], 1)
        resid[i] = z[i] - np.polyval(cf, offs)
        hill[i] = np.degrees(np.arctan(abs(cf[0])))
    L = (offs >= -12) & (offs <= -3)
    Rg = (offs >= 3) & (offs <= 12)
    C = np.abs(offs) <= 2
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bl = np.nanmax(np.where(L[None, :], resid, np.nan), axis=1)
        br = np.nanmax(np.where(Rg[None, :], resid, np.nan), axis=1)
        tr = np.nanmin(np.where(C[None, :], resid, np.nan), axis=1)
    per_t["incision_depth_m"] = np.fmax((bl + br) / 2 - tr, 0)
    per_t["hillslope_deg"] = hill
    per_t["relief_amp_m"] = (np.nanpercentile(np.where((np.abs(offs) <= 10)[None, :], resid, np.nan), 95, axis=1)
                             - np.nanpercentile(np.where((np.abs(offs) <= 10)[None, :], resid, np.nan), 5, axis=1))
    # canopy closure: fraction of the band with CHM above 2 m
    for bn, fn in BANDS.items():
        m = fn(offs)
        per_t[f"canopy_cover_{bn}"] = np.nanmean(
            np.where(m[None, :], prof["chm"] > 2.0, np.nan), axis=1)
    per_t["canopy_cover_contrast"] = (per_t["canopy_cover_road"]
                                      - per_t["canopy_cover_context"])

    dft = pd.DataFrame(per_t)
    dft["road"] = t_road
    agg = dft.groupby("road").median(numeric_only=True)
    agg["n_transects"] = dft.groupby("road").size()

    df = gdf.join(agg, how="inner")

    # ---- proximity / landscape position ------------------------------------
    def dist_to(path, layer=None, clip=True):
        try:
            h = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
        except Exception:
            return None
        h = (h.set_crs(4326) if h.crs is None else h).to_crs(DST_CRS)
        if clip:
            h = h[h.intersects(region.buffer(500))]
        if not len(h):
            return None
        u = h.union_all()
        return df.geometry.apply(lambda g: g.distance(u))
    for col, args in (("dist_pad_m", (ANN / "annotations_proj.gpkg", "plat")),
                      ("dist_pit_m", (ANN / "annotations_proj.gpkg", "pit_inside")),
                      ("dist_drain_m", (ANN / "annotations_proj.gpkg", "drainage")),
                      ("dist_wells_m", (path_for("truth") / "oil_gas_locations.gpkg", None))):
        v = dist_to(*args)
        if v is not None:
            df[col] = v.values
    allr = gpd.read_file(ANN / "roads.shp")
    allr = (allr.set_crs(4326) if allr.crs is None else allr).to_crs(DST_CRS)
    allr = allr[allr.intersects(region)]
    ru = allr.union_all()
    df["road_density_100m_km"] = [
        allr.intersection(g.buffer(100)).length.sum() / 1000 for g in df.geometry]
    # where does the unsupervised work put these roads?
    binp = OUT / "road_morphology_bins_9t_05.gpkg"
    if binp.exists():
        bg = gpd.read_file(binp)
        bu = bg.geometry.buffer(6)
        for i, g in enumerate(df.geometry):
            hits = bg[bu.intersects(g)]
            if len(hits):
                ov = hits.geometry.apply(lambda h: h.buffer(6).intersection(g).length)
                j = ov.idxmax()
                df.loc[df.index[i], "unsup_bin"] = bg.loc[j, "bin"]
                df.loc[df.index[i], "prominence_z"] = bg.loc[j, "prominence_z"]

    # ---- statistics ---------------------------------------------------------
    from scipy.stats import mannwhitneyu
    feats = [c for c in df.columns
             if c not in ("geometry", "label", "kind", "n_transects", "unsup_bin")
             and pd.api.types.is_numeric_dtype(df[c])]
    A = df[df.label == 1]
    B = df[df.label == 0]
    rows = []
    for c in feats:
        a, b = A[c].values, B[c].values
        if np.isfinite(a).sum() < 3 or np.isfinite(b).sum() < 3:
            continue
        d, auc = cliffs_delta(a, b)
        try:
            p = mannwhitneyu(a[np.isfinite(a)], b[np.isfinite(b)],
                             alternative="two-sided").pvalue
        except Exception:
            p = np.nan
        # transect-level (pseudo-replicated, higher power)
        ta = dft[dft.road.isin(A.index)][c] if c in dft.columns else None
        tb = dft[dft.road.isin(B.index)][c] if c in dft.columns else None
        td, tauc = (cliffs_delta(ta.values, tb.values)
                    if ta is not None else (np.nan, np.nan))
        rows.append(dict(feature=c, bold_med=np.nanmedian(a),
                         faint_med=np.nanmedian(b), delta=d, auc=auc, p=p,
                         delta_transect=td, auc_transect=tauc))
    res = pd.DataFrame(rows)
    res["abs_delta"] = res.delta.abs()
    res = res.sort_values("abs_delta", ascending=False).reset_index(drop=True)

    # Benjamini-Hochberg over the road-level tests
    m = res.p.notna().sum()
    res["q"] = np.nan
    ok = res.p.notna()
    ranks = res.loc[ok, "p"].rank(method="first")
    res.loc[ok, "q"] = (res.loc[ok, "p"] * m / ranks).clip(upper=1.0)
    res["q"] = res["q"][::-1].cummin()[::-1]

    pd.set_option("display.width", 200)
    print("\n=== top 22 by |Cliff's delta| (road level, n=8 vs 21) ===")
    print(res.head(22)[["feature", "bold_med", "faint_med", "delta", "auc",
                        "p", "q", "delta_transect"]].round(3).to_string(index=False))

    print(f"\nsignificant after BH correction (q < 0.05): "
          f"{int((res.q < 0.05).sum())} of {m} features")

    if "unsup_bin" in df.columns:
        ct = pd.crosstab(df.kind, df.unsup_bin, dropna=False)
        print("\n=== do the unsupervised bins agree with the labels? ===")
        print(ct.to_string())
        print("\nprominence_z:  bold %.2f  faint %.2f" % (
            A.prominence_z.median(), B.prominence_z.median()))

    df.drop(columns="geometry").to_csv(
        OUT / "bold_vs_faint_features_9t_05.csv", index=False)
    res.to_csv(OUT / "bold_vs_faint_effectsizes_9t_05.csv", index=False)
    (OUT / "bold_vs_faint_summary_9t_05.json").write_text(json.dumps({
        "n_bold": int((df.label == 1).sum()), "n_faint": int((df.label == 0).sum()),
        "km_bold": round(float(A.length_m.sum() / 1000), 2),
        "km_faint": round(float(B.length_m.sum() / 1000), 2),
        "n_transects": int(n_t),
        "bands_m": {"road": "<=3", "near": "5-15", "context": "25-60"},
        "n_sig_bh": int((res.q < 0.05).sum()),
        "top": json.loads(res.head(25).to_json(orient="records")),
    }, indent=2))

    # ---- figures ------------------------------------------------------------
    show = [("resid", "detrended elevation (m)", resid),
            ("slope", "slope (deg)", prof.get("slope")),
            ("chm", "canopy height (m)", prof.get("chm")),
            ("oneg", "openness (negative)", prof.get("oneg")),
            ("rough", "roughness", prof.get("rough")),
            ("inten", "ground intensity", prof.get("inten"))]
    fig, axes = plt.subplots(2, 3, figsize=(16, 8.5))
    for ax, (nm, lab, arr) in zip(axes.ravel(), show):
        if arr is None:
            continue
        for lb, col, tag in ((1, "#c1272d", "bold"), (0, "#2b6cb0", "faint")):
            sel = np.isin(t_road, df.index[df.label == lb])
            if not sel.any():
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                med = np.nanmedian(arr[sel], axis=0)
                q1 = np.nanpercentile(arr[sel], 25, axis=0)
                q3 = np.nanpercentile(arr[sel], 75, axis=0)
            ax.fill_between(offs, q1, q3, color=col, alpha=0.15)
            ax.plot(offs, med, color=col, lw=2, label=tag)
        for x0, x1 in ((-3, 3),):
            ax.axvspan(x0, x1, color="0.85", alpha=0.5, zorder=0)
        for x0, x1 in ((25, HALF_W), (-HALF_W, -25)):
            ax.axvspan(x0, x1, color="0.93", alpha=0.6, zorder=0)
        ax.axvline(0, color="0.5", lw=0.8, ls=":")
        ax.set_xlabel("distance from centreline (m)")
        ax.set_ylabel(lab)
        ax.set_title(lab, fontsize=10)
        ax.legend(fontsize=8)
    fig.suptitle("bold vs faint roads — transect profiles "
                 "(grey band = road, outer grey = context 25-60 m)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT / "fig_bold_vs_faint_profiles_9t_05.png", dpi=140)
    plt.close(fig)

    top = res.head(18).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.5, 7.5))
    cols = ["#c1272d" if d > 0 else "#2b6cb0" for d in top.delta]
    ax.barh(top.feature, top.delta, color=cols)
    ax.axvline(0, color="k", lw=0.8)
    for y, (d, q) in enumerate(zip(top.delta, top.q)):
        ax.text(d + (0.03 if d > 0 else -0.03), y,
                ("q<0.05" if q < 0.05 else f"q={q:.2f}"),
                va="center", ha="left" if d > 0 else "right", fontsize=7)
    ax.set_xlim(-1.35, 1.35)
    ax.set_xlabel("Cliff's delta   (red = higher on bold, blue = higher on faint)")
    ax.set_title(f"bold (n={len(A)}) vs faint (n={len(B)}) — ranked effect size\n"
                 f"road-level, Benjamini-Hochberg corrected", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "fig_bold_vs_faint_effects_9t_05.png", dpi=140)
    plt.close(fig)

    print(f"\nwrote:\n  {OUT / 'bold_vs_faint_features_9t_05.csv'}"
          f"\n  {OUT / 'bold_vs_faint_effectsizes_9t_05.csv'}"
          f"\n  {OUT / 'bold_vs_faint_summary_9t_05.json'}"
          f"\n  {OUT / 'fig_bold_vs_faint_profiles_9t_05.png'}"
          f"\n  {OUT / 'fig_bold_vs_faint_effects_9t_05.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
