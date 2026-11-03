"""Where the 2006-08 to 2019 lidar change falls, by NLCD land cover (9t).

Inputs: NLCD 2006 and 2019 (data/9t/derived/landcover, from _fetch_nlcd_9t.py), the per-pass-corrected high-passed change
(data/9t/derived/lidar_2006_2008/dod_v2_highpass_9t_2m.tif, from _change_rebuild_v2_9t.py), the 2019 DEM for slope, and the change patches
(data/_experiments/icp/change_9t/change_patches_9t_singleicp.gpkg).
NLCD is 30 m, so every 2 m cell takes its 30 m class (nearest). Treat class edges as +/-30 m fuzzy.

Slope is a confounder. Noise in the change field grows with slope (robust sigma 0.062 m flat, 0.181 m above 25 deg), and cover classes
sit on different slopes. So the by-class table is reported on all ground and on gentle ground (slope under 10 deg).

Outputs (data/9t/results/change/): change_landcover_by_class_9t.csv, change_landcover_transitions_9t.csv,
  change_landcover_patches_9t.csv, change_landcover_9t.png

Run: python notebooks/wellsight_v2/s7_analysis/_change_landcover_9t.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _change_lineadj_9t as L  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/9t/results/change"
LC = ROOT / "data/9t/derived/landcover"
BB, N = L.BB, L.N
T = from_origin(BB[0], BB[3], 2.0, 2.0)
THR = 0.235
NAMES = {11: "open water", 21: "developed, open", 22: "developed, low", 23: "developed, medium", 41: "deciduous forest", 42: "evergreen forest",
         43: "mixed forest", 52: "shrub", 71: "herbaceous", 81: "pasture/hay", 90: "woody wetland", 95: "herbaceous wetland"}
GROUP = {11: "water", 21: "developed", 22: "developed", 23: "developed", 41: "forest", 42: "forest", 43: "forest", 52: "open/shrub",
         71: "open/shrub", 81: "open/shrub", 90: "wetland", 95: "wetland"}
# Palette: cut #1F5FA8, fill #D97706 (validated, worst dE 23.3 deutan / 25.4 normal, see CLAUDE.md). Greys are neutrals, always labelled.
CUT, FILL, GREY, CHAR, WET = "#1F5FA8", "#D97706", "#8E959B", "#2B2F36", "#5FB4E0"


def lc(y):
    d = np.zeros((N, N), np.uint8)
    with rasterio.open(LC / f"nlcd_{y}_landcover_9t.tif") as s:
        reproject(rasterio.band(s, 1), d, src_transform=s.transform, src_crs=s.crs, dst_transform=T, dst_crs="EPSG:6346", resampling=Resampling.nearest)
    return d


def rd(p):
    with rasterio.open(p) as s:
        return s.read(1).astype(float)


def main():
    l06, l19 = lc(2006), lc(2019)
    ref = L.dem2019()
    gy, gx = np.gradient(np.nan_to_num(ref, nan=np.nanmean(ref)), 2.0)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    h = rd(ROOT / "data/9t/derived/lidar_2006_2008/dod_v2_highpass_9t_2m.tif")
    ok = np.isfinite(h)
    # slope-normalised field (change / slope noise level, written by _icp_change_classify_9t.py --source lineadj --zscale)
    z = rd(ROOT / "data/_experiments/icp/change_9t/dod_9t_v2_z_z_2m.tif")
    zc, zf = np.isfinite(z) & (z < -3), np.isfinite(z) & (z > 3)
    cut, fill = ok & (h < -THR), ok & (h > THR)
    rows = []
    for c in sorted(np.unique(l19)):
        r = dict(nlcd_2019=int(c), name=NAMES.get(int(c), str(c)), group=GROUP.get(int(c)))
        for tag, sel in (("all", ok & (l19 == c)), ("gentle", ok & (l19 == c) & (slope < 10))):
            n = int(sel.sum())
            r[f"cells_{tag}"] = n
            r[f"share_cut_{tag}"] = round(float(cut[sel].sum() / n), 4) if n else np.nan
            r[f"share_fill_{tag}"] = round(float(fill[sel].sum() / n), 4) if n else np.nan
            r[f"sigma_{tag}_m"] = round(L.robust(h[sel])[1], 3) if n > 500 else np.nan
        sa = ok & (l19 == c)
        r["z3_cut_all"] = round(float(zc[sa].mean()), 4) if sa.any() else np.nan
        r["z3_fill_all"] = round(float(zf[sa].mean()), 4) if sa.any() else np.nan
        r["mean_slope_deg"] = round(float(slope[ok & (l19 == c)].mean()), 1)
        rows.append(r)
    D = pd.DataFrame(rows)
    D.to_csv(OUT / "change_landcover_by_class_9t.csv", index=False)
    print(D.to_string(index=False))

    ch = ok & (l06 != l19)
    tr = pd.DataFrame({"from_2006": l06[ch], "to_2019": l19[ch], "cut": cut[ch], "fill": fill[ch], "dz": h[ch]})
    G = tr.groupby(["from_2006", "to_2019"]).agg(cells=("dz", "size"), share_cut=("cut", "mean"), share_fill=("fill", "mean"), median_dz_m=("dz", "median")).reset_index()
    G["from_name"] = G.from_2006.map(NAMES)
    G["to_name"] = G.to_2019.map(NAMES)
    G["area_ha"] = (G.cells * 4 / 1e4).round(2)
    G = G.sort_values("cells", ascending=False)
    G.to_csv(OUT / "change_landcover_transitions_9t.csv", index=False)
    print(f"cells whose class changed {ch.sum() / ok.sum():.3%}\n", G.head(12).to_string(index=False))
    stable = ok & ~ch
    print("stable cells beyond threshold", round(float((cut | fill)[stable].mean()), 4), " class-changed cells", round(float((cut | fill)[ch].mean()), 4))

    forest = (41, 42, 43)
    for ptag, pfile in (("singleicp", "change_patches_9t_singleicp.gpkg"), ("lineadj_z", "change_patches_9t_lineadj_z.gpkg"), ("v2_z", "change_patches_9t_v2_z.gpkg")):
        R = patch_table(gpd.read_file(ROOT / "data/_experiments/icp/change_9t" / pfile), l06, l19, h, forest)
        R.to_csv(OUT / f"change_landcover_patches_{ptag}_9t.csv", index=False)
        print("==", ptag, len(R), "patches")
        print(R.groupby(["cls", "nlcd_2019_name"]).size().to_string())
        print("patches with any class change under them", int((R.class_changed_share > 0).sum()), "of", len(R))
        nf = R[R.share_nonforest_2019 >= 0.5]
        print("patches mostly non-forest", len(nf))
        print(nf[["patch_id", "cls", "sign", "area_m2", "mean_dz_m", "nlcd_2006_name", "nlcd_2019_name"]].to_string(index=False))
    figure(D, l19, cut, fill, ok)


def patch_table(P, l06, l19, h, forest):
    rec = []
    for r in P.itertuples():
        m = ~geometry_mask([r.geometry], out_shape=h.shape, transform=T)
        a, b = l19[m], l06[m]
        maj19, maj06 = np.bincount(a).argmax(), np.bincount(b).argmax()
        rec.append(dict(patch_id=r.patch_id, cls=r.cls, sign=r.sign, area_m2=r.area_m2, mean_dz_m=r.mean_dz_m, slope_deg=r.slope_deg,
                        nlcd_2019=int(maj19), nlcd_2019_name=NAMES.get(int(maj19)), nlcd_2006=int(maj06), nlcd_2006_name=NAMES.get(int(maj06)),
                        share_forest_2019=round(float(np.isin(a, forest).mean()), 2), share_nonforest_2019=round(float((~np.isin(a, forest)).mean()), 2),
                        class_changed_share=round(float((a != b).mean()), 2)))
    return pd.DataFrame(rec)


def figure(D, l19, cut, fill, ok):
    forest = (41, 42, 43)
    codes = {"forest": 0, "developed": 1, "open/shrub": 2, "wetland": 3, "water": 4}
    lut = np.zeros(256, np.uint8)
    for k, v in GROUP.items():
        lut[k] = codes[v]
    g = lut[l19]
    cols = ["#E4E6E8", CHAR, FILL, WET, GREY]
    ext = (BB[0], BB[2], BB[1], BB[3])
    fig, ax = plt.subplots(1, 3, figsize=(17, 6.2), gridspec_kw=dict(width_ratios=[1, 1, 1.05]))
    ax[0].imshow(g, cmap=ListedColormap(cols), vmin=0, vmax=4, extent=ext, interpolation="nearest")
    ax[0].set_title("NLCD 2019 land cover (30 m)")
    fshare = float(np.isin(l19[ok], forest).mean())
    ax[0].legend(handles=[Patch(color=c, label=n) for c, n in zip(cols, [f"forest {fshare:.0%}", "developed", "open / shrub", "wetland", "water"])],
                 loc="lower left", fontsize=8, framealpha=0.95)
    im = np.full((N, N, 3), 0.93)
    im[cut] = np.array([0x1F, 0x5F, 0xA8]) / 255
    im[fill] = np.array([0xD9, 0x77, 0x06]) / 255
    im[~ok] = 1
    ax[1].imshow(im, extent=ext, interpolation="nearest")
    ax[1].contour(np.linspace(BB[0], BB[2], N), np.linspace(BB[3], BB[1], N), (g != 0).astype(float), levels=[0.5], colors=[CHAR], linewidths=0.8)
    ax[1].set_title("Change beyond 0.235 m: lower in 2019 (blue), higher (orange)\nblack lines = edge of non-forest cover", fontsize=10)
    for a in ax[:2]:
        a.set_xticks([])
        a.set_yticks([])
    d = D[D.cells_gentle > 3000]
    y = np.arange(len(d))
    ax[2].barh(y - 0.2, d.share_cut_gentle * 100, 0.4, color=CUT, label="lower in 2019 (cut)")
    ax[2].barh(y + 0.2, d.share_fill_gentle * 100, 0.4, color=FILL, label="higher in 2019 (fill)")
    ax[2].set_yticks(y)
    ax[2].set_yticklabels([f"{n}  (n={c:,})" for n, c in zip(d.name, d.cells_gentle)], fontsize=8)
    ax[2].invert_yaxis()
    ax[2].set_xlabel("% of cells beyond 0.235 m, gentle ground only (slope < 10 deg)")
    ax[2].set_title("Share of each cover type that changed")
    ax[2].legend(fontsize=8, loc="lower right")
    fig.suptitle("Lidar change 2006-08 to 2019 against land cover, tile 9t", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT / "change_landcover_9t.png", dpi=140)
    print(OUT / "change_landcover_9t.png")


if __name__ == "__main__":
    main()
