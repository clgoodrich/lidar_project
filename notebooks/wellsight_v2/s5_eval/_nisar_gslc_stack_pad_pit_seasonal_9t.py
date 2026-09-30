"""Multi-date NISAR GSLC brightness over 9t: pads and pits against their surroundings, by season.

WHY
---
One January GCOV image showed a faint pad signal: open pads about 0.8 dB darker
in HH than the forest ring (`docs/iterations/nisar_gcov_pad_vs_forest_backscatter_9t.md`).
A single image is grainy, so that signal could not be read pad by pad.
Averaging many dates suppresses the grain. The GSLC is also posted at 5 m instead
of 10 m. This script asks three questions:

  1. With the grain averaged down, do pads differ from their surroundings?
  2. Does the leaf-on against leaf-off change differ? That ratio is taken within
     one track, so terrain and viewing geometry cancel.
  3. Does anything show at pit scale?

DATA
----
Windows written by `notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py`
to `data/9t/derived/nisar_gslc_5m/`, plus its index CSV. Complex HH and HV at a
5 m posting, EPSG:32617. There are three tracks: 090 ascending, 162 ascending and
026 descending. Windows with under half their pixels valid are dropped;
2026-07-22 track 026D has none.

Seasons:
  * leaf-off fall: 2025-10-01 .. 2025-11-30 (beta collection)
  * winter:        2025-12-01 .. 2026-01-31 (beta; snow and frozen ground likely)
  * leaf-on:       2026-06-01 .. 2026-09-30 (provisional collection)

The beta and provisional collections were processed by different software
versions. A calibration offset between them would move every pixel by the same
amount. Feature-minus-ring differences cancel such an offset.

METHOD
------
  * Intensity is |s|^2. It is averaged per track and season in linear power.
  * The seasonal change for a set of pixels is a ratio of means:
    mean(leaf-on) / mean(leaf-off fall), in dB. It is not a mean of per-pixel
    ratios, which are far more skewed.
  * Pads: core pixels have their centre at least 3 m inside the pad. The ring is
    20-60 m outside, kept 10 m clear of every pad and road.
  * Pits: `pit_outside` polygons, meaning the whole pit including its rim. The
    ring is 10-30 m outside, kept 5 m clear of every pit and road.
  * **Decoy null (the key control).** Radar brightness is right-skewed. The mean
    of a few pixels therefore sits below the mean of many, even over identical
    ground. A pit covers about 8 pixels and its ring hundreds. A trial run
    without this control showed pits "2.4 dB darker" in seasonal change, while
    open and closed canopy did not differ at all pixel by pixel. That was the
    size effect.
    Each feature therefore gets 5 decoys: the same shape moved 150-600 m in a
    random direction, onto background at least 20 m from any pad, pit or road.
    Each decoy gets a ring built the same way. The excess is the feature's
    difference minus the median of its decoys' differences. Only the excess is
    evidence of a real signal.
  * Positive control, per pixel (so no size effect): background pixels under
    10% canopy against pixels over 90%, from the 2019 lidar CHM.
  * Registration, per track: the leaf-on HV mean is correlated with canopy cover
    at shifts of -20..+20 m. A shift is applied only when the best correlation
    is at least 0.10, the peak is inside the search range, and it beats the
    unshifted correlation by at least 0.02. Otherwise the track is used as
    delivered. The GCOV test measured about 10 m of offset on the beta data. At
    5 m pixels an offset that size smears a pit into its ring.
  * Each track's value is computed separately and then averaged over tracks.
    Tests are the Wilcoxon signed-rank test on the excess and the AUC of
    feature differences against all decoy differences. 95% CI by bootstrapping
    features.

Run:
  python notebooks/wellsight_v2/s5_eval/_nisar_gslc_stack_pad_pit_seasonal_9t.py
  python notebooks/wellsight_v2/s5_eval/_nisar_gslc_stack_pad_pit_seasonal_9t.py --force-best-shift

--force-best-shift applies each track's best canopy-correlation shift whatever its
strength. It is a sensitivity run. Its outputs carry `_forcedshift` in the name.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject
from scipy.stats import mannwhitneyu, spearmanr, wilcoxon
from shapely.affinity import translate

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
from _common import path_for, read_layer  # noqa: E402

SRC = path_for("data") / "9t" / "derived" / "nisar_gslc_5m"
INDEX = SRC / "nisar_gslc_window_index_9t_5m.csv"
ANN = path_for("truth") / "annotations_proj.gpkg"
CHM = path_for("data") / "9t" / "derived" / "1m" / "chm_9t_1m.tif"
OUT = path_for("results_9t") / "nisar"
FIG = OUT / "figures"
CRS = "EPSG:32617"

SEASONS = {"leafoff_fall": ("2025-10-01", "2025-11-30"),
           "winter": ("2025-12-01", "2026-01-31"),
           "leafon": ("2026-06-01", "2026-09-30")}
PAD_CORE_M, PAD_RING, PAD_EXCL = 3.0, (20.0, 60.0), 10.0
PIT_RING, PIT_EXCL = (10.0, 30.0), 5.0
SHIFTS = range(-20, 21, 5)
REG_MIN_RHO = 0.10   # below this the canopy correlation is too weak to locate a shift
N_PLACEBO = 5
B, SEED = 2000, 20260930

# lost/found pair, validate_palette.py --mode light --pairs all "#1F5FA8,#D97706":
# worst pair dE 21.1 deutan, 22.6 normal. Maps: greyscale, and PuOr (purple-orange,
# no green) for the signed seasonal change. Features and decoys also differ by marker.
FEAT_C, RING_C, INK = "#1F5FA8", "#D97706", "#141A1F"


def db(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(x)


def load_stack():
    idx = pd.read_csv(INDEX)
    for f in idx.loc[idx.valid_fraction < 0.5, "file"]:
        print(f"dropping {f}: valid fraction below 0.5")
    idx = idx[idx.valid_fraction >= 0.5].reset_index(drop=True)
    grids, bounds = set(), []
    for f in idx.file:
        with rasterio.open(SRC / f) as r:
            grids.add((r.transform.c % 5, r.transform.f % 5))
            bounds.append(r.bounds)
    if len(grids) != 1:
        raise RuntimeError(f"windows are not on one 5 m lattice: {grids}")
    x0 = max(b.left for b in bounds); x1 = min(b.right for b in bounds)
    y0 = max(b.bottom for b in bounds); y1 = min(b.top for b in bounds)
    tf = rasterio.Affine(5.0, 0, x0, 0, -5.0, y1)
    shape = (int(round((y1 - y0) / 5)), int(round((x1 - x0) / 5)))
    inten = {}
    for row in idx.itertuples():
        with rasterio.open(SRC / row.file) as r:
            a = r.read(window=rasterio.windows.from_bounds(x0, y0, x1, y1, r.transform))
        inten[row.file] = (np.abs(a[0]) ** 2, np.abs(a[1]) ** 2)
        assert inten[row.file][0].shape == shape, (row.file, inten[row.file][0].shape, shape)
    return idx, inten, tf, shape


# Short raster names: polarization, season, track. Values are season-mean dB, as delivered
# (no shift to the lidar); the change raster is summer mean minus fall mean, in dB.
RASTER_METRIC_NAME = {"leafoff_fall": "fall_2025", "winter": "winter_2025_26",
                      "leafon": "summer_2026", "change_leafon_vs_fall": "change_summer_minus_fall"}


def raster_name(metric: str, track: int, direction: str, tag: str) -> str:
    """metric is '<pol>_<season key>', e.g. 'hv_leafon'. Only as-delivered rasters are written."""
    assert tag == "asdelivered", tag
    pol, key = metric.split("_", 1)
    return f"nisar_{pol}_{RASTER_METRIC_NAME[key]}_track{track:03d}_9t_5m.tif"


def season_of(d: str):
    for s, (a, b) in SEASONS.items():
        if a <= d <= b:
            return s
    return None


def canopy_cover(tf, shape, shift=(0.0, 0.0)):
    """Share of 1 m CHM cells above 2 m in each 5 m pixel (2019 lidar)."""
    with rasterio.open(CHM) as r:
        chm = r.read(1, masked=True)
        src = np.where(chm.mask, np.nan, (chm.filled(0) > 2.0).astype(np.float32))
        dst = np.full(shape, np.nan, np.float32)
        t = rasterio.Affine(tf.a, 0, tf.c + shift[0], 0, tf.e, tf.f + shift[1])
        reproject(src, dst, src_transform=r.transform, src_crs=r.crs, src_nodata=np.nan,
                  dst_transform=t, dst_crs=CRS, dst_nodata=np.nan, resampling=Resampling.average)
    return dst


def auc(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(mannwhitneyu(a, b).statistic / (len(a) * len(b))) if len(a) and len(b) else np.nan


def pixel_index(geom, tf, shape):
    """Flat indices of pixels whose centre lies in geom; rasterized on a small window."""
    if geom.is_empty:
        return np.array([], dtype=np.int64)
    x0, y0, x1, y1 = geom.bounds
    c0 = max(0, int(np.floor((x0 - tf.c) / tf.a)))
    c1 = min(shape[1], int(np.ceil((x1 - tf.c) / tf.a)) + 1)
    r0 = max(0, int(np.floor((y1 - tf.f) / tf.e)))
    r1 = min(shape[0], int(np.ceil((y0 - tf.f) / tf.e)) + 1)
    if c1 <= c0 or r1 <= r0:
        return np.array([], dtype=np.int64)
    wtf = rasterio.Affine(tf.a, 0, tf.c + c0 * tf.a, 0, tf.e, tf.f + r0 * tf.e)
    m = rasterize([(geom, 1)], out_shape=(r1 - r0, c1 - c0), transform=wtf, fill=0, dtype="uint8")
    rr, cc = np.nonzero(m)
    return (rr + r0) * shape[1] + (cc + c0)


def ring_geom(g, ring, excl):
    return g.buffer(ring[1]).difference(g.buffer(ring[0])).difference(excl)


def pixel_sets(geom, core_m, ring, excl, tf, shape, ok_flat):
    core = pixel_index(geom.buffer(-core_m) if core_m else geom, tf, shape)
    rg = pixel_index(ring_geom(geom, ring, excl), tf, shape)
    return core[ok_flat[core]], rg[ok_flat[rg]]


def placebo_sets(geom, core_m, ring, excl, tf, shape, ok_flat, bg_flat, rng, k, tries=60):
    """Up to k copies of geom moved 150-600 m onto background, each with its own ring."""
    out = []
    for _ in range(tries):
        if len(out) == k:
            break
        a, r = rng.uniform(0, 2 * np.pi), rng.uniform(150, 600)
        g = translate(geom, r * np.cos(a), r * np.sin(a))
        core = pixel_index(g.buffer(-core_m) if core_m else g, tf, shape)
        if len(core) == 0 or not bg_flat[core].all():
            continue
        rg = pixel_index(ring_geom(g, ring, excl), tf, shape)
        rg = rg[ok_flat[rg]]
        if len(rg) < 10:
            continue
        out.append((core, rg))
    return out


def set_value(core, rg, L, num, den):
    """Feature-minus-ring in dB for one track. With den, a ratio of means (seasonal change)."""
    def m(idx, k):
        v = L[k][idx]
        v = v[np.isfinite(v)]
        return v.mean() if len(v) else np.nan
    if num not in L or (den and den not in L):
        return np.nan
    f = db(m(core, num)) - (db(m(core, den)) if den else 0.0)
    r = db(m(rg, num)) - (db(m(rg, den)) if den else 0.0)
    return f - r


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-best-shift", action="store_true")
    force = ap.parse_args().force_best_shift
    sfx = "_forcedshift" if force else ""
    FIG.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    idx, inten, tf, shape = load_stack()
    idx["season"] = idx.date.map(season_of)
    counts = idx.groupby(["track", "direction", "season"]).size().unstack(fill_value=0)
    print(counts)

    means = {}
    for (track, season), g in idx.groupby(["track", "season"]):
        for p, pi in (("hh", 0), ("hv", 1)):
            means[(track, season, p)] = np.nanmean(np.stack([inten[f][pi] for f in g.file]), axis=0)
    tracks = sorted(idx.track.unique())
    cover = canopy_cover(tf, shape)
    in_tile = np.isfinite(cover)

    # ---- registration per track ------------------------------------------------------
    reg, shift_of = [], {}
    for t in tracks:
        shift_of[t] = (0.0, 0.0)
        if (t, "leafon", "hv") not in means:
            continue
        hv = db(means[(t, "leafon", "hv")])
        res = {}
        for dx in SHIFTS:
            for dy in SHIFTS:
                c = cover if (dx, dy) == (0, 0) else canopy_cover(tf, shape, (dx, dy))
                ok = np.isfinite(c) & np.isfinite(hv)
                res[(dx, dy)] = float(spearmanr(c[ok], hv[ok]).statistic)
        (bx, by), br = max(res.items(), key=lambda kv: kv[1])
        r0 = res[(0, 0)]
        interior = abs(bx) < max(SHIFTS) and abs(by) < max(SHIFTS)
        use = force or (interior and br >= REG_MIN_RHO and br - r0 >= 0.02)
        if use:
            shift_of[t] = (float(bx), float(by))
        reg.append(dict(track=int(t), rho_unshifted=r0, best_dx=bx, best_dy=by, rho_best=br,
                        peak_inside_search=interior, applied=use))
        print(f"track {t}: rho0 {r0:.3f}, best {br:.3f} at ({bx:+d},{by:+d}) -> "
              f"{'applied' if use else 'as delivered'}")

    def aligned(arr, t):
        # a track pixel labelled x shows ground at x + shift; move it to that label
        cx, cy = int(round(shift_of[t][0] / 5)), int(round(shift_of[t][1] / 5))
        if cx == 0 and cy == 0:
            return arr
        outa = np.full_like(arr, np.nan)
        src_r0, dst_r0 = max(0, cy), max(0, -cy)
        src_c0, dst_c0 = max(0, -cx), max(0, cx)
        h, w = shape[0] - abs(cy), shape[1] - abs(cx)
        outa[dst_r0:dst_r0 + h, dst_c0:dst_c0 + w] = arr[src_r0:src_r0 + h, src_c0:src_c0 + w]
        return outa

    layers = {t: {f"{p}_{s}": aligned(means[(t, s, p)], t).ravel()
                  for s in SEASONS for p in ("hh", "hv") if (t, s, p) in means} for t in tracks}
    metrics = {}
    for p in ("hh", "hv"):
        for s in SEASONS:
            metrics[f"{p}_{s}"] = (f"{p}_{s}", None)
        metrics[f"{p}_change_leafon_vs_fall"] = (f"{p}_leafon", f"{p}_leafoff_fall")

    # ---- geometry ---------------------------------------------------------------------
    pads = read_layer(ANN, "plat").to_crs(CRS)[["pad_id", "geometry"]].dissolve(by="pad_id").reset_index()
    pits = read_layer(ANN, "pit_outside").to_crs(CRS).reset_index(drop=True)
    roads = read_layer(ANN, "roads").to_crs(CRS)
    feat_zone = rasterize([(g, 1) for g in pd.concat([pads.buffer(20), pits.buffer(20), roads.buffer(20)])],
                          out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
    ok_flat = in_tile.ravel()
    bg_flat = (in_tile & ~feat_zone).ravel()
    pad_excl = pd.concat([pads.buffer(PAD_EXCL), roads.buffer(PAD_EXCL)]).union_all()
    pit_excl = pd.concat([pits.buffer(PIT_EXCL), roads.buffer(PIT_EXCL)]).union_all()

    # ---- positive control, per pixel ----------------------------------------------------
    control = []
    cov = cover.ravel()
    op, cl = bg_flat & (cov < 0.10), bg_flat & (cov > 0.90)
    for t in tracks:
        L = layers[t]
        for m, (num, den) in metrics.items():
            if num not in L or (den and den not in L):
                continue
            v = db(L[num]) - (db(L[den]) if den else 0.0)
            a, b = v[op & np.isfinite(v)], v[cl & np.isfinite(v)]
            a = rng.choice(a, min(20000, len(a)), replace=False)
            b = rng.choice(b, min(20000, len(b)), replace=False)
            control.append(dict(track=int(t), metric=m, open_median_db=float(np.median(a)),
                                closed_median_db=float(np.median(b)), auc_closed_gt_open=auc(b, a)))
    control = pd.DataFrame(control)
    print(control.round(3).to_string())
    # whole-tile shift between seasons: seasonal, or a beta-vs-provisional calibration offset
    tile_median_change = {}
    for t in tracks:
        for p in ("hh", "hv"):
            L = layers[t]
            if f"{p}_leafon" in L and f"{p}_leafoff_fall" in L:
                v = db(L[f"{p}_leafon"]) - db(L[f"{p}_leafoff_fall"])
                tile_median_change[(int(t), p)] = float(np.nanmedian(v[ok_flat]))
    print("tile median leaf-on minus leaf-off (dB):", tile_median_change)

    # ---- features and their decoys ---------------------------------------------------------
    results, per_feature = [], {}
    for kind, geoms, ids, excl, core_m, ring in (
            ("pad", pads.geometry, pads.pad_id, pad_excl, PAD_CORE_M, PAD_RING),
            ("pit", pits.geometry, pits.index, pit_excl, 0.0, PIT_RING)):
        rows, decoys_all = [], {m: [] for m in metrics}
        for fid, g in zip(ids, geoms):
            core, rg = pixel_sets(g, core_m, ring, excl, tf, shape, ok_flat)
            if len(core) == 0 or len(rg) < 10:
                continue
            pls = placebo_sets(g, core_m, ring, excl, tf, shape, ok_flat, bg_flat, rng, N_PLACEBO)
            if not pls:
                continue
            row = dict(id=fid, n_core=len(core), n_ring=len(rg), n_decoys=len(pls))
            for m, (num, den) in metrics.items():
                real = [set_value(core, rg, layers[t], num, den) for t in tracks]
                row[f"{m}_feature"] = np.nanmean(real) if np.isfinite(real).any() else np.nan
                pv = []
                for pc, pr in pls:
                    v = [set_value(pc, pr, layers[t], num, den) for t in tracks]
                    if np.isfinite(v).any():
                        pv.append(np.nanmean(v))
                row[f"{m}_decoy_median"] = float(np.median(pv)) if pv else np.nan
                decoys_all[m] += pv
            rows.append(row)
        df = pd.DataFrame(rows)
        per_feature[kind] = df
        print(f"{kind}: {len(df)} features with rings and decoys")
        for m in metrics:
            real = df[f"{m}_feature"].to_numpy()
            dec = df[f"{m}_decoy_median"].to_numpy()
            ok = np.isfinite(real) & np.isfinite(dec)
            if ok.sum() < 10:
                continue
            exc = real[ok] - dec[ok]
            be = np.median(exc[rng.integers(0, ok.sum(), size=(B, ok.sum()))], axis=1)
            results.append(dict(features=kind, metric=m, n=int(ok.sum()),
                                median_feature_minus_ring_db=float(np.median(real[ok])),
                                median_decoy_minus_ring_db=float(np.median(dec[ok])),
                                median_excess_db=float(np.median(exc)),
                                excess_ci_lo=float(np.percentile(be, 2.5)),
                                excess_ci_hi=float(np.percentile(be, 97.5)),
                                auc_feature_gt_decoy=auc(real[ok], decoys_all[m]),
                                wilcoxon_p_excess=float(wilcoxon(exc).pvalue)))
    res = pd.DataFrame(results)
    print(res.round(3).to_string())

    # ---- outputs ---------------------------------------------------------------------------
    prof = dict(driver="GTiff", height=shape[0], width=shape[1], count=1, dtype="float32",
                crs=CRS, transform=tf, nodata=np.nan, compress="deflate")
    n_written = 0
    for t in ([] if force else tracks):
        d = idx[idx.track == t].direction.iat[0]
        tag = "lidaraligned" if shift_of[t] != (0.0, 0.0) else "asdelivered"
        L = layers[t]
        for m, (num, den) in metrics.items():
            if num not in L or (den and den not in L):
                continue
            v = (db(L[num]) - (db(L[den]) if den else 0.0)).reshape(shape)
            with rasterio.open(SRC / raster_name(m, t, d, tag), "w", **prof) as dst:
                dst.write(v.astype(np.float32), 1)
            n_written += 1
    print(f"wrote {n_written} rasters to {SRC}")
    for kind, df in per_feature.items():
        df.to_csv(OUT / f"nisar_gslc_stack_{kind}_vs_ring_and_decoys_per_feature{sfx}_9t_5m.csv", index=False)
    res.to_csv(OUT / f"nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season{sfx}_9t_5m.csv", index=False)
    control.to_csv(OUT / f"nisar_gslc_stack_open_vs_closed_canopy_control_by_track{sfx}_9t_5m.csv", index=False)
    (OUT / f"nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season{sfx}_9t_5m.json").write_text(json.dumps(dict(
        n_dates_by_track_season=counts.stack().rename("n").reset_index().to_dict("records"),
        registration=reg, shift_applied_m={int(k): v for k, v in shift_of.items()},
        seasons=SEASONS, n_decoys=N_PLACEBO,
        tile_median_change_leafon_minus_fall_db={f"{k[0]}_{k[1]}": v for k, v in tile_median_change.items()}, control=control.to_dict("records"),
        results=results), indent=1, default=str))

    # ---- figure ----------------------------------------------------------------------------
    # map the track with the most leaf-off dates; one-date seasons are pure speckle
    t0 = max(tracks, key=lambda t: counts.xs(t, level="track")["leafoff_fall"].sum())
    d0 = idx[idx.track == t0].direction.iat[0]
    L = layers[t0]
    fig, ax = plt.subplots(2, 2, figsize=(16, 13))
    ext = (tf.c, tf.c + shape[1] * 5, tf.f - shape[0] * 5, tf.f)
    img = db(L["hh_leafon"]).reshape(shape)
    lo, hi = np.nanpercentile(img[in_tile], [2, 98])
    ax[0, 0].imshow(img, extent=ext, cmap="gray", vmin=lo, vmax=hi, interpolation="nearest")
    pads.boundary.plot(ax=ax[0, 0], color=FEAT_C, lw=0.5)
    n_on = int(counts.loc[(t0, d0), "leafon"])
    ax[0, 0].set_title(f"HH brightness, mean of {n_on} leaf-on dates, track {t0}{d0}, 5 m\n"
                       "annotated pads outlined", loc="left", fontsize=11)
    ch = (db(L["hv_leafon"]) - db(L["hv_leafoff_fall"])).reshape(shape)
    ch = ch - tile_median_change[(int(t0), "hv")]
    im = ax[0, 1].imshow(ch, extent=ext, cmap="PuOr", vmin=-4, vmax=4, interpolation="nearest")
    pads.boundary.plot(ax=ax[0, 1], color=INK, lw=0.4)
    fig.colorbar(im, ax=ax[0, 1], fraction=0.04, pad=0.02).set_label("HV leaf-on minus leaf-off fall, relative to tile median (dB)")
    ax[0, 1].set_title(f"Seasonal change in HV, track {t0}{d0}\npurple = brighter in summer",
                       loc="left", fontsize=11)
    for a in ax[0]:
        a.set_xticks([]); a.set_yticks([])
        a.set_xlim(ext[0] + 200, ext[1] - 200); a.set_ylim(ext[2] + 200, ext[3] - 200)

    shown = ["hh_leafon", "hv_leafon", "hh_leafoff_fall", "hv_leafoff_fall",
             "hh_change_leafon_vs_fall", "hv_change_leafon_vs_fall"]
    label = {"leafon": "leaf-on", "leafoff_fall": "leaf-off\nfall", "change_leafon_vs_fall": "seasonal\nchange"}

    def panel(a, kind, title):
        df = per_feature[kind]
        for i, m in enumerate(shown):
            for off, col, mk, vals in ((-0.18, FEAT_C, "o", df[f"{m}_feature"]),
                                       (0.18, RING_C, "s", df[f"{m}_decoy_median"])):
                v = vals.dropna().to_numpy()
                a.scatter(i + off + rng.uniform(-0.1, 0.1, len(v)), v, s=4, color=col, marker=mk,
                          alpha=0.3, lw=0)
                q = np.percentile(v, [25, 50, 75])
                a.errorbar(i + off, q[1], yerr=[[q[1] - q[0]], [q[2] - q[1]]], fmt=mk, color=INK,
                           mfc=col, ms=8, capsize=4)
        a.axhline(0, color=INK, ls="--", lw=0.8)
        a.set_xticks(range(len(shown)))
        a.set_xticklabels([m[:2].upper() + "\n" + label[m[3:]] for m in shown], fontsize=10)
        a.set_ylabel("minus its own ring (dB), mean over tracks")
        a.set_ylim(-6, 6)
        a.set_title(title, loc="left", fontsize=11)
        a.scatter([], [], color=FEAT_C, marker="o", label=f"annotated {kind}s")
        a.scatter([], [], color=RING_C, marker="s", label="decoys: same shape on background")
        a.legend(frameon=False, fontsize=9, loc="lower left")

    panel(ax[1, 0], "pad", f"{len(per_feature['pad'])} pads and their decoys, each against its own "
                           "20-60 m ring\nmarkers are medians, bars IQR")
    panel(ax[1, 1], "pit", f"{len(per_feature['pit'])} pits and their decoys, each against its own "
                           "10-30 m ring\nmarkers are medians, bars IQR")
    fig.tight_layout()
    fp = FIG / f"nisar_gslc_stack_pad_pit_vs_decoy_leafon_leafoff_seasonal_change{sfx}_9t_5m.png"
    fig.savefig(fp, dpi=160)
    print(f"wrote {fp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
