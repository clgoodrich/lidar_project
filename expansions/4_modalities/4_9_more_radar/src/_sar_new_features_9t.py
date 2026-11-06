"""S4 of framework 4.9. Build SAR feature rasters for one arm on its native grid and sample them on the frozen rows.

Purpose. Two steps, either alone.
  --rows-only  Write the frozen scoring rows from the NISAR samples files (targets, decoys, blocks, map x and y, and
               the rich lidar baseline features). Repeated decoy locations are dropped with the key used by
               notebooks/wellsight_v2/s5_eval/_nisar_feat_dedupe_9t.py (centre pixel and footprint size). Uses
               _nisar_feat_common.load_samples with NISAR_STACK=slc (pads also LOCAL_M=1500), so the rows are the
               ones the NISAR result was scored on.
  features     From the arm's geocoded stacks (linear power, one band per date) compute per polarisation the mean
               backscatter in dB, temporal coefficient of variation, GLCM contrast and homogeneity on the dB image
               (offsets (0,1) and (1,0), exact for a single offset via moving means), and local contrast against a
               20 to 60 m ring. Add mean coherence when a coherence stack exists, and H, alpha and the Pauli
               diagonal (T11, T22, T33 in dB) when a T3 file exists. Then sample every band on each row as the
               median inside a disc of the target radius, so decoys get the same footprint size as targets.
The feature list is frozen here. Feature sets are never chosen on the scoring blocks.
Inputs.
  data/9t/derived/nisar_features_5m/nisar_<target>_samples_9t_slc*.npz (held, --rows-only)
  data/9t/derived/sar_new/<arm>/sar_<arm>_<pol>_stack_9t.tif (assumed), optional _coh_stack_ and _t3_ files
Outputs.
  expansions/4_modalities/4_9_more_radar/data/processed/sar_rows_<target>_9t.csv   rows (and arm columns once built)
  data/9t/derived/sar_new/<arm>/sar_<arm>_features_9t.tif                         multi-band, band names in descriptions
Run.
  python expansions/4_modalities/4_9_more_radar/src/_sar_new_features_9t.py --target pit --rows-only
  python expansions/4_modalities/4_9_more_radar/src/_sar_new_features_9t.py --target pit --arm A1 [--stack-dir DIR] [--rows CSV]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage as ndi
from scipy.signal import fftconvolve

import _sar_kit_4_9 as sk


# ----------------------------------------------------------------------------- rows
def rows_from_nisar(target: str) -> pd.DataFrame:
    os.environ.setdefault("NISAR_STACK", "slc")
    if target == "pad":
        os.environ.setdefault("LOCAL_M", "1500")
    sys.path.insert(0, str(sk.S5_EVAL))
    argv, sys.argv = sys.argv, sys.argv[:1]          # the NISAR modules read sys.argv for --area
    try:
        import _nisar_feat_common as C
    finally:
        sys.argv = argv
    S = C.load_samples(target, C.suffix(target))
    z = S["z"]
    ctl, lt, _, _ = C.feature_groups(S["prod"])
    n0 = len(S["pads"])
    key = np.array([f"{c}_{n}" for c, n in zip(z["dec_ctr"][S["sel"]], z["dec_n"][S["sel"]])])
    keep = np.r_[np.arange(n0), n0 + np.sort(np.unique(key, return_index=True)[1])]
    cols = np.flatnonzero(ctl | lt)
    df = pd.DataFrame(S["X"][keep][:, cols], columns=[f"base:{S['names'][i]}" for i in cols])
    df.insert(0, "ym", S["xy"][keep, 1])
    df.insert(0, "x", S["xy"][keep, 0])
    df.insert(0, "block", S["grp"][keep])
    df.insert(0, "y", S["y"][keep])
    df.insert(0, "row", np.arange(len(df)))
    return df


# ----------------------------------------------------------------------------- features
def read_stack(p: Path, crs: str):
    import rasterio
    with rasterio.open(p) as d:
        sk.ek.assert_crs(d, crs)
        a = d.read().astype("float64")
        if d.nodata is not None:
            a[a == d.nodata] = np.nan
        return a, d.transform, d.res[0]


def to_db(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10 * np.log10(np.where(x > 0, x, np.nan))


def glcm_stats(db: np.ndarray, win: int, levels: int, rng_db) -> tuple[np.ndarray, np.ndarray]:
    """GLCM contrast and homogeneity in a win x win window, averaged over offsets (0,1) and (1,0).
    For one offset these equal the window means of d^2 and 1 / (1 + d^2), d the grey-level difference of the pair."""
    lo, hi = rng_db
    q = np.floor((np.clip(np.nan_to_num(db, nan=lo), lo, hi) - lo) / (hi - lo) * (levels - 1) + 0.5)
    con, hom = np.zeros_like(q), np.zeros_like(q)
    for dy, dx in ((0, 1), (1, 0)):
        d = np.zeros_like(q)
        d[: q.shape[0] - dy, : q.shape[1] - dx] = q[dy:, dx:] - q[: q.shape[0] - dy, : q.shape[1] - dx]
        con += ndi.uniform_filter(d ** 2, win) / 2
        hom += ndi.uniform_filter(1 / (1 + d ** 2), win) / 2
    return con, hom


def ring_contrast(lin: np.ndarray, res: float, r_in: float, r_out: float) -> np.ndarray:
    """dB of the pixel minus dB of the mean linear power in an annulus r_in to r_out metres."""
    R = int(np.ceil(r_out / res))
    yy, xx = np.mgrid[-R:R + 1, -R:R + 1] * res
    k = ((np.hypot(yy, xx) >= r_in) & (np.hypot(yy, xx) <= r_out)).astype(float)
    ok = np.isfinite(lin)
    num = fftconvolve(np.where(ok, lin, 0), k, mode="same")
    den = fftconvolve(ok.astype(float), k, mode="same")
    with np.errstate(divide="ignore", invalid="ignore"):
        ring = np.where(den > 0.5, num / den, np.nan)
    return to_db(lin) - to_db(ring)


def h_alpha(t3: np.ndarray) -> dict:
    """Cloude-Pottier entropy and mean alpha (degrees) from T3 bands T11 T22 T33 T12re T12im T13re T13im T23re T23im."""
    t11, t22, t33, a, b, c, d, e, f = t3
    H, W = t11.shape
    T = np.zeros((H, W, 3, 3), complex)
    T[..., 0, 0], T[..., 1, 1], T[..., 2, 2] = t11, t22, t33
    T[..., 0, 1], T[..., 0, 2], T[..., 1, 2] = a + 1j * b, c + 1j * d, e + 1j * f
    T[..., 1, 0], T[..., 2, 0], T[..., 2, 1] = np.conj(T[..., 0, 1]), np.conj(T[..., 0, 2]), np.conj(T[..., 1, 2])
    bad = ~np.isfinite(T).all((-1, -2))
    T[bad] = np.eye(3)
    w, v = np.linalg.eigh(T)
    w = np.clip(w.real, 1e-12, None)
    p = w / w.sum(-1, keepdims=True)
    ent = -(p * np.log(p) / np.log(3)).sum(-1)
    alpha = np.degrees(np.arccos(np.clip(np.abs(v[..., 0, :]), 0, 1)))
    out = {"entropy": ent, "alpha_deg": (p * alpha).sum(-1),
           "pauli_t11_db": to_db(t11), "pauli_t22_db": to_db(t22), "pauli_t33_db": to_db(t33)}
    for k in out:
        out[k] = np.where(bad, np.nan, out[k])
    return out


def build_features(stack_dir: Path, arm: str, cfg: dict):
    F, A = cfg["features"], cfg["arms"][arm]
    bands, tf, res = {}, None, None
    for pol in A["pols"]:
        p = stack_dir / f"sar_{arm}_{pol}_stack_9t.tif"
        if not p.exists():
            continue
        st, tf, res = read_stack(p, cfg["crs"])
        with np.errstate(invalid="ignore", divide="ignore"):
            m = np.nanmean(st, 0)
            bands[f"{pol}_mean_db"] = to_db(m)
            bands[f"{pol}_tcv"] = np.nanstd(st, 0) / m if st.shape[0] > 1 else np.full(m.shape, np.nan)
        bands[f"{pol}_glcm_contrast"], bands[f"{pol}_glcm_homog"] = glcm_stats(bands[f"{pol}_mean_db"], F["glcm_window_px"],
                                                                               F["glcm_levels"], F["glcm_db_range"])
        bands[f"{pol}_ring_contrast_db"] = ring_contrast(m, res, F["ring_inner_m"], F["ring_outer_m"])
    if not bands:
        sk.need(stack_dir / f"sar_{arm}_{A['pols'][0]}_stack_9t.tif", f"geocoded stack for arm {arm}", cfg["inputs"]["stack"])
    coh = stack_dir / f"sar_{arm}_coh_stack_9t.tif"
    if coh.exists():
        bands["coh_mean"] = np.nanmean(read_stack(coh, cfg["crs"])[0], 0)
    t3 = stack_dir / f"sar_{arm}_t3_9t.tif"
    if t3.exists():
        bands.update(h_alpha(read_stack(t3, cfg["crs"])[0]))
    return bands, tf, res


def write_features(path: Path, bands: dict, tf, crs: str) -> None:
    import rasterio
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(bands)
    H, W = bands[names[0]].shape
    with rasterio.open(path, "w", driver="GTiff", width=W, height=H, count=len(names), dtype="float32", crs=crs,
                       transform=tf, nodata=np.nan, compress="deflate", tiled=True) as d:
        for i, n in enumerate(names, 1):
            d.write(bands[n].astype("float32"), i)
            d.set_band_description(i, n)


def sample_disc(bands: dict, tf, x, y, radius: float) -> pd.DataFrame:
    """Median of each band inside a disc of radius around each (x, y). The centre pixel alone when the disc is smaller."""
    res = abs(tf.a)
    R = max(0, int(np.ceil(radius / res)))
    oy, ox = np.mgrid[-R:R + 1, -R:R + 1]
    m = np.hypot(oy * res, ox * res) <= max(radius, res / 2)
    oy, ox = oy[m], ox[m]
    inv = ~tf
    cols, rows = inv * (np.asarray(x), np.asarray(y))
    r0, c0 = np.floor(rows).astype(int), np.floor(cols).astype(int)
    out = {}
    for n, a in bands.items():
        H, W = a.shape
        rr, cc = r0[:, None] + oy[None], c0[:, None] + ox[None]
        ok = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
        v = np.where(ok, a[np.clip(rr, 0, H - 1), np.clip(cc, 0, W - 1)], np.nan)
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                out[n] = np.nanmedian(v, 1)
    return pd.DataFrame(out)


def main(argv=None) -> int:
    cfg = sk.load_cfg()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", default=cfg["prereg"]["primary_target"], choices=sorted(cfg["targets"]))
    ap.add_argument("--rows-only", action="store_true")
    ap.add_argument("--arm", default=None, choices=sorted(cfg["arms"]))
    ap.add_argument("--rows", default=None)
    ap.add_argument("--stack-dir", default=None)
    ap.add_argument("--features-out", default=None)
    a = ap.parse_args(argv)
    rows_p = Path(a.rows) if a.rows else sk.ek.exp_dir("4.9") / "data" / "processed" / f"sar_rows_{a.target}_9t.csv"
    if a.rows_only:
        df = rows_from_nisar(a.target)
        sk.ek.assert_no_nan(df.block, "block")
        rows_p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(rows_p, index=False)
        sk.prov(rows_p.parent, f"sar_rows_{a.target}", outputs=[rows_p], params={"n": len(df), "n_targets": int(df.y.sum())})
        print(rows_p, len(df), "rows,", int(df.y.sum()), "targets")
        return 0
    if not a.arm:
        raise ValueError("--arm is needed unless --rows-only")
    df = pd.read_csv(sk.need(rows_p, "frozen scoring rows (run with --rows-only first)"))
    sd = Path(a.stack_dir) if a.stack_dir else sk.resolve(cfg["outputs"]["features"], arm=a.arm)
    bands, tf, res = build_features(sd, a.arm, cfg)
    fo = Path(a.features_out) if a.features_out else sk.resolve(cfg["outputs"]["features"], arm=a.arm) / f"sar_{a.arm}_features_9t.tif"
    write_features(fo, bands, tf, cfg["crs"])
    smp = sample_disc(bands, tf, df.x, df.ym, cfg["targets"][a.target]["radius_m"])
    smp.columns = [f"arm:{a.arm}:{c}" for c in smp.columns]
    df = pd.concat([df.drop(columns=[c for c in df if c.startswith(f"arm:{a.arm}:")]), smp], axis=1)
    sk.ek.assert_rows(df, len(smp), "rows after sampling")
    df.to_csv(rows_p, index=False)
    sk.prov(fo.parent, f"sar_new_features_{a.arm}", inputs=sorted(sd.glob(f"sar_{a.arm}_*_9t.tif")), outputs=[fo, rows_p],
            params={"arm": cfg["arms"][a.arm], "features": cfg["features"], "native_res_m": res, "bands": list(bands)})
    print(fo, list(bands))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
