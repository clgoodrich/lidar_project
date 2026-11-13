"""Does the NISAR backscatter follow what the optical sees (vegetation type), more than the canopy height or the ground?  (9t)

Optical: Sentinel-2 L2A, 10 m, open data from the Element 84 Earth Search STAC (AWS). Three clear scenes over the tile,
all on MGRS tile 17TPG: 2026-06-03 (leaf-on), 2026-09-07 (leaf-on, close to the NISAR summer dates) and 2025-10-27
(late fall, leaf-off in part). Bands used: green, red, near infrared (B08), shortwave infrared (B11), and the scene
classification (clouds, shadow and snow are masked). Each is averaged onto the 5 m radar grid and cached in
data/9t/derived/optical_s2/ (git-ignored).

Derived: NDVI per date, NDMI (moisture index from NIR and SWIR) on 2026-09-07, and NDVI(Jun) minus NDVI(Oct), a proxy for
how much of the vegetation drops its leaves (deciduous against evergreen and open ground).

Test (same block-mean design as _nisar_vs_canopy_9t.py, 50 m blocks): Spearman correlation of the NISAR date-mean
HH and HV (mean of the three tracks) with each optical layer and each lidar layer, and the share of variance (R2) of the
radar explained by the lidar layers alone, the optical layers alone, and both, overall and in closed canopy (cover > 0.8).
Also writes a four-panel picture of one 1 km window: Sentinel-2 NDVI, NISAR HV, lidar canopy height, lidar hillshade.

  NISAR_STACK=slc python _nisar_vs_optical_9t.py
"""
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.warp import Resampling, reproject
from scipy.stats import spearmanr

import _nisar_feat_common as C

SCENES = {"jun": "S2A_17TPG_20260603_0_L2A", "sep": "S2B_17TPG_20260907_0_L2A", "oct": "S2C_17TPG_20251027_0_L2A"}
BANDS = {"green": "green", "red": "red", "nir": "nir", "swir": "swir16", "scl": "scl"}
OPT = C.A.DATA / "derived" / "optical_s2"
BLOCK, TRACKS = 10, (26, 90, 162)       # 10 pixels of 5 m = 50 m


def item_assets(scene):
    r = requests.get(f"https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/{scene}", timeout=60)
    r.raise_for_status()
    return {k: v["href"] for k, v in r.json()["assets"].items()}


def fetch(tf, shape):
    OPT.mkdir(parents=True, exist_ok=True)
    out = {}
    for tag, scene in SCENES.items():
        path = OPT / f"s2_{tag}_green_red_nir_swir_scl_9t_5m.tif"
        if not path.exists():
            hrefs = item_assets(scene)
            layers = []
            for b, a in BANDS.items():
                dst = np.full(shape, np.nan, np.float32)
                with rasterio.open(hrefs[a]) as src:
                    reproject(rasterio.band(src, 1), dst, dst_transform=tf, dst_crs=C.CRS, src_nodata=0, dst_nodata=np.nan,
                              resampling=Resampling.nearest if b == "scl" else Resampling.average)
                layers.append(dst)
            with rasterio.open(path, "w", driver="GTiff", height=shape[0], width=shape[1], count=len(layers), dtype="float32",
                               crs=C.CRS, transform=tf, nodata=np.nan, compress="deflate") as d:
                for i, (a, n) in enumerate(zip(layers, BANDS), 1):
                    d.write(a, i)
                    d.set_band_description(i, n)
            print("wrote", path, flush=True)
        with rasterio.open(path) as r:
            g, rd, nir, sw, scl = (r.read(i) for i in range(1, 6))
        # reflectance = DN / 10000
        refl = lambda x: x / 10000.0  # noqa: E731  (these scenes carry no 1000 DN offset: red median is 267 DN)
        bad = np.isin(scl, (0, 1, 3, 8, 9, 11))   # thin cirrus (10) is kept: 63% of the 7 Sep scene is flagged cirrus and barely moves NDVI | ~np.isfinite(scl)
        red, nir, sw, g = refl(rd), refl(nir), refl(sw), refl(g)
        ndvi = (nir - red) / (nir + red)
        ndmi = (nir - sw) / (nir + sw)
        for n in (ndvi, ndmi):
            n[bad] = np.nan
        out[tag] = dict(ndvi=ndvi, ndmi=ndmi, red=np.where(bad, np.nan, red), nir=np.where(bad, np.nan, nir))
    return out


def block_mean(a, k=BLOCK):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k).astype(np.float64)
    ok = np.isfinite(b)
    with np.errstate(all="ignore"):
        m = np.where(ok, b, 0).sum((1, 3)) / ok.sum((1, 3))
    m[ok.sum((1, 3)) < 0.8 * k * k] = np.nan
    return m


def r2(y, X):
    X1 = np.c_[np.ones(len(y)), X]
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return 1 - (y - X1 @ beta).var() / y.var()


def main():
    with rasterio.open(C.FEAT_DIR / f"nisar_check_radnorm_{C.A.TAG}_5m.tif") as r:
        names, arr, tf, shape = list(r.descriptions), r.read(), r.transform, (r.height, r.width)
    opt = fetch(tf, shape)
    grids = C.lidar_grids(tf, shape)
    chm = C.to_grid(C.A.lidar("chm"), tf, shape)
    dem = C.to_grid(C.A.lidar("dem"), tf, shape)
    sar = {pol: np.nanmean([arr[names.index(f"raw_mean_{pol}_t{t:03d}")] for t in TRACKS], 0) for pol in ("hh", "hv")}
    layers = {"canopy_height": chm, "canopy_cover": grids["cover"], "ground_slope": grids["slope"], "ground_elevation": dem,
              "ndvi_jun": opt["jun"]["ndvi"], "ndvi_sep": opt["sep"]["ndvi"], "ndvi_oct": opt["oct"]["ndvi"],
              "ndvi_jun_minus_oct": opt["jun"]["ndvi"] - opt["oct"]["ndvi"], "ndmi_sep": opt["sep"]["ndmi"],
              "nir_sep": opt["sep"]["nir"]}
    B = {n: block_mean(a) for n, a in layers.items()}
    S = {n: block_mean(a) for n, a in sar.items()}
    lidar = ["canopy_height", "canopy_cover", "ground_slope", "ground_elevation"]
    optic = ["ndvi_jun", "ndvi_sep", "ndvi_oct", "ndvi_jun_minus_oct", "ndmi_sep", "nir_sep"]
    rows = []
    for sub, mk in (("all", lambda: np.ones_like(B["canopy_cover"], bool)), ("closed canopy (cover > 0.8)", lambda: B["canopy_cover"] > 0.8),
                    ("open ground (cover < 0.25)", lambda: B["canopy_cover"] < 0.25)):
        for pol, s in S.items():
            ok = mk() & np.isfinite(s) & np.all([np.isfinite(B[n]) for n in lidar + optic], axis=0)
            y = s[ok]
            row = dict(subset=sub, sar=pol, n_blocks=int(ok.sum()))
            for n in lidar + optic:
                row[f"spearman_{n}"] = round(float(spearmanr(y, B[n][ok]).statistic), 3)
            XL, XO = np.column_stack([B[n][ok] for n in lidar]), np.column_stack([B[n][ok] for n in optic])
            row["r2_lidar_only"], row["r2_optical_only"] = round(r2(y, XL), 3), round(r2(y, XO), 3)
            row["r2_lidar_and_optical"] = round(r2(y, np.hstack([XL, XO])), 3)
            rows.append(row)
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    res.to_csv(C.OUT / f"nisar_vs_optical_corr_{C.A.TAG}.csv", index=False)
    print(res.T.to_string(header=False))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    r0, c0, n = 250, 250, 200         # a 1 km window (200 pixels of 5 m)
    win = (slice(r0, r0 + n), slice(c0, c0 + n))
    hs = C.to_grid(C.A.lidar("hillshade"), tf, shape)
    from scipy.ndimage import uniform_filter
    hv_s = uniform_filter(np.where(np.isfinite(sar["hv"]), sar["hv"], np.nanmedian(sar["hv"])), 5)     # 25 m smoothing for display only
    pc = lambda a, q: tuple(np.nanpercentile(a[win], q))  # noqa: E731
    nd = opt["jun"]["ndvi"]
    panels = [("Sentinel-2 NDVI, 3 Jun 2026 (2-98% stretch)", nd, "Greys", pc(nd, (2, 98))),
              ("NISAR HV date-mean (dB), 3 tracks, 25 m smoothing", hv_s, "cividis", pc(hv_s, (2, 98))),
              ("Lidar canopy height (m)", chm, "cividis", (0, 30)), ("Lidar hillshade", hs, "Greys_r", None)]
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.9))
    for ax, (t, a, cm, lim) in zip(axes, panels):
        im = ax.imshow(a[win], cmap=cm, vmin=None if lim is None else lim[0], vmax=None if lim is None else lim[1])
        ax.set_title(t, fontsize=10)
        ax.set_xticks([]), ax.set_yticks([])
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    fig.suptitle("The same 1 km window of 9t, four layers", y=1.0)
    fig.tight_layout()
    fo = C.OUT / "figures"
    fo.mkdir(exist_ok=True)
    out = fo / f"nisar_vs_optical_window_9t_slc.png"
    fig.savefig(out, dpi=140)
    print(out)


if __name__ == "__main__":
    main()
