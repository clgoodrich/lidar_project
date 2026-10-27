"""Shared helpers for the NISAR feature products (docs/iterations/nisar_feature_products_plan.md).

Every product script loads the complex windows once, computes bands, and writes them with
write_bands(). The scorer reads every nisar_feat_*.tif back with read_all(). One GeoTIFF per
product keeps a failed or re-run product from touching the others.

Area is picked with --area (9t default), as for the other NISAR scripts.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ifg = importlib.import_module("_nisar_gslc_interferogram_pits_9t")
st, A = ifg.st, ifg.A
CRS, OUT = ifg.CRS, ifg.OUT
FEAT_DIR = A.DATA / "derived" / "nisar_features_5m"


def load():
    """idx, stack (file -> complex array [pol, y, x]; pol 0 = HH, 1 = HV), transform, shape."""
    return ifg.load_complex()


def by_track(idx):
    """(track, rows sorted by date) for each track."""
    for t, g in idx.groupby("track"):
        yield int(t), g.sort_values("date").reset_index(drop=True)


def cube(g, stack, pol):
    """Complex samples of one polarisation for the dates of g: (date, y, x)."""
    return np.stack([stack[f][pol] for f in g.file])


def to_grid(path, tf, shape):
    """Mean of a 1 m lidar raster on the 5 m radar grid."""
    with rasterio.open(path) as r:
        src = r.read(1, masked=True)
        src = np.where(src.mask, np.nan, src.filled(0)).astype(np.float32)
        dst = np.full(shape, np.nan, np.float32)
        reproject(src, dst, src_transform=r.transform, src_crs=r.crs, src_nodata=np.nan,
                  dst_transform=tf, dst_crs=CRS, dst_nodata=np.nan, resampling=Resampling.average)
    return dst


def lidar_grids(tf, shape):
    """slope (deg), roughness_5 and canopy cover on the radar grid."""
    return dict(slope=to_grid(A.lidar("slope"), tf, shape), rough=to_grid(A.lidar("roughness_5"), tf, shape),
                cover=st.canopy_cover(tf, shape))


def db(x):
    return 10 * np.log10(np.where(x > 0, x, np.nan))


def write_bands(product, bands, tf, shape):
    """Write {name: 2-D array} to nisar_feat_<product>_<area>_5m.tif, band names kept."""
    FEAT_DIR.mkdir(parents=True, exist_ok=True)
    path = FEAT_DIR / f"nisar_feat_{product}_{A.TAG}_5m.tif"
    with rasterio.open(path, "w", driver="GTiff", height=shape[0], width=shape[1], count=len(bands), dtype="float32",
                       crs=CRS, transform=tf, nodata=np.nan, compress="deflate") as dst:
        for i, (n, a) in enumerate(bands.items(), 1):
            dst.write(np.asarray(a, np.float32), i)
            dst.set_band_description(i, n)
    print(f"wrote {path} ({len(bands)} bands)", flush=True)
    return path


def read_all():
    """{band name: array} for every product file of this area, product name prefixed."""
    out = {}
    for p in sorted(FEAT_DIR.glob(f"nisar_feat_*_{A.TAG}_5m.tif")):
        prod = p.name[len("nisar_feat_"):-len(f"_{A.TAG}_5m.tif")]
        with rasterio.open(p) as r:
            for i, d in enumerate(r.descriptions, 1):
                out[f"{prod}:{d}"] = r.read(i)
    return out


CV_XY = None          # map x, y of every sample row; set by the caller so the CV can keep a buffer between train and test
CV_BUFFER_M = 250.0
SEED_CV = 20261026


def suffix(target):
    """Name tag of a scoring design, from the environment. One definition for the scorer, model, ablation and checks scripts,
    so their file names cannot drift apart."""
    import os
    base = 0 if target == "pit" else 5
    core = float(os.environ.get("CORE_SHRINK_M", base))
    local = float(os.environ.get("LOCAL_M", 0))
    return (("" if core == base else f"_core{core:.0f}m") + ("_roadnear" if os.environ.get("ROAD_NEAR") == "1" else "")
            + ("_roughmatch" if os.environ.get("MATCH_ROUGH") == "1" else "")
            + ("_confuser" if os.environ.get("CONFUSER") == "1" else "")
            + ("_shape" if os.environ.get("SHAPE") == "1" else "") + ("_inc" if os.environ.get("INC_MATCH") == "1" else "")
            + ("_placebo" if os.environ.get("PLACEBO") == "1" else "")
            + (f"_local{local:.0f}" if local else ""))


def fit_predict(Xtr, ytr, Xte):
    """The model of every script: bands more than 20% missing in either training class are dropped, the rest are
    median-imputed with training medians, histogram gradient boosting. Returns P(target) for Xte, or None if no band is left."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    nr = np.stack([np.isnan(Xtr[ytr == 1]).mean(0), np.isnan(Xtr[ytr == 0]).mean(0)]).max(0)
    good = nr <= 0.20
    if not good.any():
        return None
    med = np.nanmedian(Xtr[:, good], 0)
    fill = lambda A: np.where(np.isnan(A), med, A)  # noqa: E731
    m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=200, l2_regularization=1.0,
                                       min_samples_leaf=40, class_weight="balanced", random_state=SEED_CV)
    m.fit(fill(Xtr[:, good]), ytr)
    return m.predict_proba(fill(Xte[:, good]))[:, 1]


def oof_probs(X, y, grp, xy=None, buffer_m=None, seed=None):
    """Out-of-fold probabilities, 5-fold GroupKFold by block. Everything that looks at the labels happens inside the
    training fold: bands more than 20% missing in either training class are dropped and the rest are median-imputed
    with training medians. Training rows within buffer_m of any test row are removed so that neighbouring footprints
    cannot sit on both sides. seed=None is the deterministic GroupKFold; an integer gives a shuffled StratifiedGroupKFold
    (stratified on the label, grouped by block), for repeated CV. Returns (p, [test index arrays])."""
    from scipy.spatial import cKDTree
    from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
    xy = CV_XY if xy is None else xy
    buffer_m = CV_BUFFER_M if buffer_m is None else buffer_m
    p = np.full(len(y), np.nan)
    folds = []
    splitter = GroupKFold(5) if seed is None else StratifiedGroupKFold(5, shuffle=True, random_state=seed)
    for tr, te in splitter.split(X, y, grp):
        if buffer_m and xy is not None:
            d, _ = cKDTree(xy[te]).query(xy[tr])
            tr = tr[d > buffer_m]
        q = fit_predict(X[tr], y[tr], X[te])
        if q is None:
            continue
        p[te] = q
        folds.append(te)
    return p, folds


def load_samples(target, suffix, tag=None):
    """Rows of the samples file written by _nisar_feat_score_9t.py, raw (NaN kept): names, X, y, grp, xy, cover, z.
    tag picks another area's file (e.g. "613590_slc") and leaves the module-level CV coordinates alone."""
    path = FEAT_DIR / f"nisar_{target}_samples_{A.TAG}{suffix}.npz" if tag is None else (
        A.path_for("data") / tag.split("_")[0] / "derived" / "nisar_features_5m" / f"nisar_{target}_samples_{tag}{suffix}.npz")
    z = np.load(path, allow_pickle=True)
    names = [str(n) for n in z["names"]]
    dec_pad = z["dec_pad"]
    keep = np.isin(np.arange(z["pad"].shape[1]), np.unique(dec_pad)) & np.isfinite(z["pad"][names.index("control:cover")])
    pads = np.flatnonzero(keep)
    sel = np.flatnonzero(np.isin(dec_pad, pads))
    X = np.vstack([z["pad"][:, pads].T, z["dec"][:, sel].T])
    y = np.r_[np.ones(len(pads)), np.zeros(len(sel))].astype(int)
    grp = np.r_[z["pad_block"][pads], z["dec_block"][sel]]
    xy = np.vstack([z["pad_xy"][pads], z["dec_xy"][sel]])
    cover = np.r_[z["pad_cover"][pads], z["pad_cover"][dec_pad[sel]]]
    global CV_XY
    if tag is None:
        CV_XY = xy
    return dict(names=names, X=X, y=y, grp=grp, xy=xy, cover=cover, z=z, pads=pads, sel=sel,
                prod=np.array([n.split(":")[0] for n in names]))


def sample_values(flat, z):
    """A raster (flattened, radar grid) read on the footprints of a samples file: (value per target, value per decoy).
    Median over each footprint, NaN when fewer than min(4, nb) pixels are finite, as in the scorer."""
    near = z["pad_near"]
    v = np.where(near >= 0, flat[np.clip(near, 0, None)], np.nan)
    nb = (near >= 0).sum(1)
    pv = np.nanmedian(v, 1)
    pv[np.isfinite(v).sum(1) < np.minimum(4, nb)] = np.nan
    H, W = [int(t) for t in z["grid_shape"]]
    r, c = np.divmod(z["dec_ctr"], W)
    o, ok = z["off_a"][z["dec_pad"]], z["valid_a"][z["dec_pad"]]
    d = flat[np.clip(r[:, None] + o[:, :, 0], 0, H - 1) * W + np.clip(c[:, None] + o[:, :, 1], 0, W - 1)]
    d = np.where(ok, d, np.nan)
    dv = np.nanmedian(d, 1)
    dv[np.isfinite(d).sum(1) < np.minimum(4, ok.sum(1))] = np.nan
    return pv, dv


def feature_groups(prod):
    """Boolean masks: simple lidar controls, lidar texture, road context, and the SAR bands."""
    ctl, lt, ctx = prod == "control", prod == "lidartex", prod == "context"
    return ctl, lt, ctx, ~ctl & ~lt & ~ctx
