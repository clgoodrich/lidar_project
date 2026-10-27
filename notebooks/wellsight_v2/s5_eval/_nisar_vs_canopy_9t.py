"""Does the NISAR backscatter follow the canopy or the ground? Whole-tile block-averaged test (9t, lidar-placed SLC stack).

For each track and polarisation the date-mean backscatter (dB, raw_mean_* from _nisar_feat_radnorm_9t.py) is compared with
lidar quantities on the same 5 m grid: canopy height (mean CHM), canopy cover, ground slope, ground elevation.
Everything is averaged over BLOCK x BLOCK pixels first (5, 10 and 20 pixels = 25, 50 and 100 m) to cut speckle and the
~10 m registration residual. Reported per block size:
  Spearman correlation of HH and HV (mean of the three tracks, and each track) with each lidar quantity
  partial correlation with canopy height after removing slope and elevation (residuals from a linear fit)
  share of variance (R2) of HV and HH explained by canopy height alone, by slope + elevation alone, and by all three
  the same inside closed canopy (cover > 0.8) and in open ground (cover < 0.25)
Outputs: data/9t/results/nisar/nisar_vs_canopy_corr_9t_slc.csv and a figure in
data/9t/results/nisar/figures/nisar_vs_canopy_hexbin_9t_slc.png.

  NISAR_STACK=slc python _nisar_vs_canopy_9t.py
"""
import numpy as np
import pandas as pd
import rasterio
from scipy.stats import spearmanr

import _nisar_feat_common as C

BLOCKS = (5, 10, 20)
TRACKS = (26, 90, 162)


def block_mean(a, k):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k).astype(np.float64)
    ok = np.isfinite(b)
    with np.errstate(all="ignore"):
        m = np.where(ok, b, 0).sum((1, 3)) / ok.sum((1, 3))
    m[ok.sum((1, 3)) < 0.8 * k * k] = np.nan
    return m


def resid(y, X):
    X1 = np.c_[np.ones(len(y)), X]
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return y - X1 @ beta


def r2(y, X):
    return 1 - resid(y, X).var() / y.var()


def main():
    path = C.FEAT_DIR / f"nisar_check_radnorm_{C.A.TAG}_5m.tif"
    with rasterio.open(path) as r:
        names, arr = list(r.descriptions), r.read()
        tf, shape = r.transform, (r.height, r.width)
    grids = C.lidar_grids(tf, shape)
    chm = C.to_grid(C.A.lidar("chm"), tf, shape)
    dem = C.to_grid(C.A.lidar("dem"), tf, shape)
    lid = {"canopy_height": chm, "canopy_cover": grids["cover"], "ground_slope": grids["slope"], "ground_elevation": dem}
    sar = {}
    for pol in ("hh", "hv"):
        per = [arr[names.index(f"raw_mean_{pol}_t{t:03d}")] for t in TRACKS]
        sar[pol] = np.nanmean(per, 0)
        for t, a in zip(TRACKS, per):
            sar[f"{pol}_t{t:03d}"] = a
    rows, keep = [], {}
    for k in BLOCKS:
        L = {n: block_mean(a, k) for n, a in lid.items()}
        S = {n: block_mean(a, k) for n, a in sar.items()}
        for sub, mask_fn in (("all", lambda L: np.ones_like(L["canopy_cover"], bool)),
                             ("closed canopy (cover > 0.8)", lambda L: L["canopy_cover"] > 0.8),
                             ("open ground (cover < 0.25)", lambda L: L["canopy_cover"] < 0.25)):
            m0 = mask_fn(L)
            for sn, s in S.items():
                ok = m0 & np.isfinite(s) & np.all([np.isfinite(v) for v in L.values()], axis=0)
                if ok.sum() < 200:
                    continue
                y = s[ok]
                row = dict(block_m=k * 5, subset=sub, sar=sn, n_blocks=int(ok.sum()))
                for ln, v in L.items():
                    row[f"spearman_{ln}"] = round(float(spearmanr(y, v[ok]).statistic), 3)
                terr = np.c_[L["ground_slope"][ok], L["ground_elevation"][ok]]
                row["partial_canopy_height_given_terrain"] = round(float(np.corrcoef(resid(y, terr), resid(L["canopy_height"][ok], terr))[0, 1]), 3)
                row["r2_canopy_height_only"] = round(r2(y, L["canopy_height"][ok][:, None]), 3)
                row["r2_terrain_only"] = round(r2(y, terr), 3)
                row["r2_canopy_and_terrain"] = round(r2(y, np.c_[L["canopy_height"][ok], terr]), 3)
                rows.append(row)
                if sn in ("hv", "hh") and sub == "all":
                    keep[(k * 5, sn)] = (L["canopy_height"][ok], y)
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    res.to_csv(C.OUT / f"nisar_vs_canopy_corr_{C.A.TAG}.csv", index=False)
    show = res[res.sar.isin(["hh", "hv"])]
    print(show.drop(columns="n_blocks").to_string(index=False))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, pol in zip(axes, ("hv", "hh")):
        x, y = keep[(50, pol)]
        h = ax.hexbin(x, y, gridsize=45, cmap="cividis", mincnt=1, bins="log")
        ax.set_xlabel("Canopy height, 50 m block mean (m)")
        ax.set_ylabel(f"NISAR {pol.upper()} date-mean, mean of 3 tracks (dB)")
        rho = spearmanr(x, y).statistic
        ax.set_title(f"{pol.upper()}: Spearman {rho:+.2f} over {len(x)} blocks", loc="left")
        fig.colorbar(h, ax=ax, label="blocks (log)")
    fig.suptitle("NISAR backscatter against lidar canopy height, 9t, 50 m blocks", y=1.0)
    fig.tight_layout()
    fo = C.OUT / "figures"
    fo.mkdir(exist_ok=True)
    out = fo / f"nisar_vs_canopy_hexbin_{C.A.TAG}.png"
    fig.savefig(out, dpi=140)
    print(out)


if __name__ == "__main__":
    main()
