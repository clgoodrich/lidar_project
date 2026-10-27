"""Does NISAR add to the lidar pad U-Net? Out-of-fold U-Net scores as one more feature next to the NISAR bands.

Rewritten 2026-10-27. The audit of 2026-10-26 (`docs/iterations/nisar_methodology_audit_20261026.md`, finding 3) found
that the original U-Net sampler could read held-out pixels. UNET_DIR (default `unet_cv5_iso`) holds the retrain with
whole-window block isolation (`s3_train/_pad_unet_iso_cv5.py`). The NISAR/lidar models here use the U-Net's own five
folds as their outer folds (the fold id is the CV group), so no row is in a test fold of one model and a training fold
of the other. One residual: a training row's U-Net score comes from a model that saw the test fold (usual for stacking
on out-of-fold scores).

The pad U-Net 5-fold CV (`notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py`) wrote one probability raster per
fold. For every pad core and every matched decoy disc the score is taken from the raster of the fold that holds out
the block the point lies in, as the mean of the 0.5 m probability over a 10 m window. Decoys in blocks with no pad
(no fold) are dropped, and every feature set below is scored on the same rows. The NISAR model uses the same CV as
the other scripts (C.oof_probs). The U-Net folds and the fusion folds are different splits.

  python _nisar_feat_fusion_9t.py     (needs the samples file with pad_xy / dec_xy)
"""
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from shapely.geometry import Point
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C
from _nisar_feat_ablate_9t import SUFFIX

UNET_DIR = os.environ.get("UNET_DIR", "unet_cv5_iso")
CV = C.A.DATA / "models" / "pad" / UNET_DIR
HALF = 10          # half window in 0.5 m pixels: a 10 m square


def main():
    S = C.load_samples("pad", SUFFIX)
    X, y, grp, xy, prod = S["X"], S["y"], S["grp"], S["xy"], S["prod"]
    ctl, lt, ctx, sar = C.feature_groups(prod)

    blocks = gpd.read_file(C.A.DATA / "derived" / "05" / "pad_blocks_9t.gpkg", layer="blocks").to_crs(6346)
    asg = pd.read_csv(C.A.DATA / "models" / "pad" / "unet_cv5" / "pad_cv5_fold_assignment_9t.csv").dropna().drop_duplicates("block_id")   # same folds in both runs
    bf = dict(zip(asg.block_id.astype(int), asg.fold.astype(int)))
    x6, y6 = Transformer.from_crs(C.CRS, 6346, always_xy=True).transform(xy[:, 0], xy[:, 1])
    pts = gpd.GeoDataFrame(geometry=[Point(a, b) for a, b in zip(x6, y6)], crs=6346)
    jb = gpd.sjoin(pts, blocks[["block_id", "geometry"]], how="left", predicate="within")
    jb = jb[~jb.index.duplicated()]
    fold = jb.block_id.map(lambda b: bf.get(int(b), -1) if pd.notna(b) else -1).values
    score = np.full(len(y), np.nan)
    for k in range(5):
        with rasterio.open(CV / f"fold{k}" / f"pad_prob_cvfold{k}_9t_05.tif") as r:
            arr = r.read(1)
            rr, cc = rasterio.transform.rowcol(r.transform, x6, y6)
        for i in np.flatnonzero(fold == k):
            a, b = rr[i], cc[i]
            w = arr[max(a - HALF, 0):a + HALF, max(b - HALF, 0):b + HALF]
            if w.size:
                score[i] = float(w.mean())
        del arr
    ok = np.isfinite(score)
    print(f"{ok.sum()} of {len(y)} rows have an out-of-fold U-Net score ({int(y[ok].sum())} pads)", flush=True)
    yy, Xk, sc, xyk = y[ok], X[ok], score[ok], xy[ok]
    grpk = fold[ok]                         # outer folds = the U-Net folds
    unet = sc[:, None]
    sets = {"U-Net out-of-fold, raw score": None,
            "lidar baseline (cover, slope, rough)": Xk[:, ctl],
            "lidar rich baseline (+ texture)": Xk[:, ctl | lt],
            "map x/y only": xyk,
            "all NISAR": Xk[:, sar],
            "U-Net + baseline": np.hstack([unet, Xk[:, ctl]]),
            "U-Net + rich baseline": np.hstack([unet, Xk[:, ctl | lt]]),
            "NISAR + baseline": Xk[:, sar | ctl],
            "NISAR + U-Net": np.hstack([Xk[:, sar], unet]),
            "NISAR + U-Net + rich baseline": np.hstack([Xk[:, sar | ctl | lt], unet])}
    rows = []
    for k, m in sets.items():
        a = roc_auc_score(yy, sc) if m is None else roc_auc_score(yy, C.oof_probs(m, yy, grpk, xy=xyk)[0])
        rows.append(dict(feature_set=k, auc=round(a, 3)))
        print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    res.insert(1, "n_pads", int(yy.sum()))
    res.insert(2, "n_decoys", int((1 - yy).sum()))
    path = C.OUT / f"nisar_pad_fusion_auc_{C.A.TAG}{SUFFIX}_{UNET_DIR}.csv"
    res.to_csv(path, index=False)
    print(path)


if __name__ == "__main__":
    main()
