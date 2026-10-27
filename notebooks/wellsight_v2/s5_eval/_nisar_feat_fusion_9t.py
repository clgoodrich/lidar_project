"""Does NISAR add to the lidar pad U-Net? Out-of-fold U-Net scores as one more feature next to the NISAR bands.

The pad U-Net 5-fold CV (`notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py`) wrote one probability raster per
fold, each predicted by a model that never saw that fold's 375 m blocks. For every pad core and every matched
decoy disc the score is taken from the raster of the fold that holds out the block the point lies in, as the mean
of the 0.5 m probability over a 10 m window. Decoys in blocks with no pad (no fold) are dropped, and every feature
set below is scored on the same rows. The NISAR model uses the same block CV as the other scripts.

Sets: U-Net alone (its raw AUC), lidar baseline, all NISAR, NISAR + U-Net, U-Net + baseline, all three.

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_fusion_9t.py     (needs the samples file with pad_xy / dec_xy)
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from shapely.geometry import Point
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C
from _nisar_feat_ablate_9t import SUFFIX, oof

CV = C.A.DATA / "models" / "pad" / "unet_cv5"
HALF = 10          # half window in 0.5 m pixels: a 10 m square


def main():
    z = np.load(C.FEAT_DIR / f"nisar_pad_samples_{C.A.TAG}{SUFFIX}.npz", allow_pickle=True)
    assert "pad_xy" in z.files, "re-run the pad scorer so the samples file holds pad_xy and dec_xy"
    names = [str(n) for n in z["names"]]
    pad, dec, dec_pad = z["pad"], z["dec"], z["dec_pad"]
    keep = np.isin(np.arange(pad.shape[1]), np.unique(dec_pad)) & np.isfinite(pad[names.index("control:cover")])
    pads = np.flatnonzero(keep)
    sel = np.flatnonzero(np.isin(dec_pad, pads))
    X = np.vstack([pad[:, pads].T, dec[:, sel].T])
    y = np.r_[np.ones(len(pads)), np.zeros(len(sel))].astype(int)
    grp = np.r_[z["pad_block"][pads], z["dec_block"][sel]]
    xy = np.vstack([z["pad_xy"][pads], z["dec_xy"][sel]])
    nan = np.stack([np.isnan(X[y == 1]).mean(0), np.isnan(X[y == 0]).mean(0)]).max(0)
    good = nan <= 0.20
    names = [n for n, g in zip(names, good) if g]
    X = np.where(np.isnan(X[:, good]), np.nanmedian(X[:, good], 0), X[:, good])
    prod = np.array([n.split(":")[0] for n in names])

    # fold of each point from the 375 m block it lies in
    blocks = gpd.read_file(C.A.DATA / "derived" / "05" / "pad_blocks_9t.gpkg", layer="blocks").to_crs(6346)
    asg = pd.read_csv(CV / "pad_cv5_fold_assignment_9t.csv").dropna().drop_duplicates("block_id")
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
    yy, grpk, Xk, sc = y[ok], grp[ok], X[ok], score[ok]
    ctl, sar = prod == "control", ~np.isin(prod, ["control", "context"])
    unet = sc[:, None]
    sets = {"U-Net out-of-fold, raw score": None,
            "lidar baseline (cover, slope, rough)": Xk[:, ctl],
            "all NISAR": Xk[:, sar],
            "U-Net + baseline": np.hstack([unet, Xk[:, ctl]]),
            "NISAR + baseline": Xk[:, sar | ctl],
            "NISAR + U-Net": np.hstack([Xk[:, sar], unet]),
            "NISAR + U-Net + baseline": np.hstack([Xk[:, sar | ctl], unet])}
    rows = []
    for k, m in sets.items():
        a = roc_auc_score(yy, sc) if m is None else roc_auc_score(yy, oof(m, yy, grpk))
        rows.append(dict(feature_set=k, auc=round(a, 3)))
        print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    res.insert(1, "n_pads", int(yy.sum()))
    res.insert(2, "n_decoys", int((1 - yy).sum()))
    path = C.OUT / f"nisar_pad_fusion_auc_{C.A.TAG}{SUFFIX}.csv"
    res.to_csv(path, index=False)
    print(path)


if __name__ == "__main__":
    main()
