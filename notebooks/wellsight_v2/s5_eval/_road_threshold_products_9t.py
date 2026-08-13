"""Per-threshold ROAD products: what each probability cutoff claims, and what it misses.

Road counterpart to `_pit_threshold_products_9t.py` and
`_pad_threshold_products_9t.py`. Same question, same held-out discipline.

MEASURING A ROAD IS NOT MEASURING A PIT
----------------------------------------
Pits and pads are blobs, so "found" is a containment or overlap test. Roads are
lines. A road is not found or missed as a unit -- it is found ALONG PART OF ITS
LENGTH. So the criterion here is length coverage:

  coverage(chunk) = fraction of that chunk's length lying within TOL_M of a
                    pixel the model called road at this threshold
  found           = coverage >= COVER_FRAC

TOL_M is 5 m. That is a tolerance on where the centreline sits, not a licence to
match a different road -- annotated roads on 9t are rarely within 5 m of each
other. COVER_FRAC is 0.5, so half a chunk must be covered before it counts.

Ground truth is the hand-drawn `roads` annotation, chunked to ~40 m in
`road_chunks_9t.gpkg`. Held out = the val + test chunks, which the U-Net never
trained on. No state well list, and no TIGER, is involved.

LEAKAGE WARNING -- ROAD NUMBERS ARE NOT COMPARABLE TO PIT AND PAD NUMBERS
-------------------------------------------------------------------------
Pits and pads are split as whole objects. Roads are split as ~40 m CHUNKS, so
485 of the 1,220 held-out road chunks (39.8%) belong to a parent road that also
has chunks in train. The model has seen the road 40 m up the line. That is a
long-standing BACKLOG item ("split leakage at block boundaries"), not something
introduced here, and it makes the headline road recall optimistic.

So every held-out road chunk carries a `clean` flag, true when its ENTIRE parent
road was held out (735 of 1,220 chunks, 221 of 344 parent roads). `recall_clean`
in the sweep CSV is the number to quote and to compare against pits and pads.
The unqualified `recall` is kept only so the gap between them stays visible.

THE CONFUSION CHECK
-------------------
Recall alone flatters a low threshold, because a model that calls everything a
road has perfect recall. The 3-class road model was built specifically to stop
drainage lines being called roads, so this script also measures, at every
threshold, how much held-out DRAINAGE and NOT_ROAD length gets claimed as road.
Those are hand-drawn negatives. Their claim rate is a real false-positive
signal, not a proxy.

Outputs per selected threshold:
  rasters      road_unet_mask_thrXpXX_9t_1m.tif / road_unet_prob_thrXpXX_9t_1m.tif
  gpkg         road_found_vs_missed / road_found / road_missed /
               midpoint_missed / locator_missed / drainage_claimed
  bookmarks    road_missed_bookmarks_thrXpXX_9t.xml
  contactsheet hillshade crop of every missed chunk

Run:
  python notebooks/wellsight_v2/s5_eval/_road_threshold_products_9t.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _threshold_common import (CRS, bookmarks_xml, contact_sheet, embed_style,
                               style_qml, tag, write_raster)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
NINE_T = path_for("nine_t")
PROB = path_for("models") / "road" / "unet_1m" / "road_prob.tif"
RASTER_DIR = path_for("models") / "road" / "unet_1m"
CHUNKS = NINE_T / "road_chunks_9t.gpkg"
HILLSHADE = NINE_T / "hillshade_9t_05.tif"
OUT = path_for("results") / "9t" / "road" / "thresholds"
OUT.mkdir(parents=True, exist_ok=True)

TOL_M = 5.0                # centreline tolerance, see docstring
COVER_FRAC = 0.50          # fraction of a chunk that must be covered
SAMPLE_M = 1.0             # spacing of coverage samples along each chunk
LOCATOR_R = 120.0
BOOKMARK_PAD = 80.0
CROP_HALF_M = 80.0

THRESHOLDS_SWEEP = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45,
                    0.50, 0.60, 0.70, 0.80, 0.90]
THRESHOLDS_PRODUCTS = [0.20, 0.30, 0.40, 0.50]


def coverage(lines: gpd.GeoSeries, dist_m: np.ndarray, transform) -> np.ndarray:
    """Fraction of each line within TOL_M of a road pixel, via a distance grid."""
    inv = ~transform
    H, W = dist_m.shape
    out = np.zeros(len(lines))
    for i, geom in enumerate(lines):
        L = geom.length
        if L <= 0:
            continue
        n = max(int(np.ceil(L / SAMPLE_M)) + 1, 2)
        pts = [geom.interpolate(d) for d in np.linspace(0, L, n)]
        cols, rows = inv * (np.array([p.x for p in pts]),
                            np.array([p.y for p in pts]))
        rr = np.clip(rows.astype(int), 0, H - 1)
        cc = np.clip(cols.astype(int), 0, W - 1)
        out[i] = float((dist_m[rr, cc] <= TOL_M).mean())
    return out


def main() -> int:
    print("== per-threshold ROAD products (ground truth = hand-drawn roads) ==\n")

    ch = gpd.read_file(CHUNKS, layer="chunks").to_crs(CRS)
    ch["length_m"] = ch.geometry.length
    held = ch[ch.split.isin(("val", "test"))].reset_index(drop=True)
    road_h = held[held.kind == "road"].reset_index(drop=True)
    drain_h = held[held.kind == "drainage"].reset_index(drop=True)
    notrd_h = held[held.kind == "not_road"].reset_index(drop=True)
    print(f"  held-out chunks:  road {len(road_h)} ({road_h.length_m.sum()/1000:.2f} km)"
          f"   drainage {len(drain_h)} ({drain_h.length_m.sum()/1000:.2f} km)"
          f"   not_road {len(notrd_h)} ({notrd_h.length_m.sum()/1000:.2f} km)")
    print(f"  criterion: >= {COVER_FRAC:.0%} of chunk length within {TOL_M:.0f} m "
          f"of a predicted road pixel")

    # ---- leakage-clean subset (see LEAKAGE WARNING in the docstring) ----
    ch["parent"] = ch.line_id.str.rsplit("_", n=1).str[0]
    road_h["parent"] = road_h.line_id.str.rsplit("_", n=1).str[0]
    train_parents = set(ch.loc[(ch.split == "train") & (ch.kind == "road"),
                               "parent"])
    road_h["clean"] = ~road_h.parent.isin(train_parents)
    n_clean = int(road_h["clean"].sum())
    print(f"  LEAKAGE: {len(road_h) - n_clean}/{len(road_h)} "
          f"({100 * (1 - n_clean / len(road_h)):.1f}%) held-out chunks share a "
          f"parent road with train chunks.")
    print(f"  'clean' column marks the {n_clean} chunks whose whole parent road "
          f"was held out. recall_clean is the honest number.\n")

    with rasterio.open(PROB) as r:
        prob = r.read(1).astype(np.float32)
        if r.nodata is not None:
            prob = np.where(prob == r.nodata, 0.0, prob)
        tf, prof = r.transform, r.profile.copy()
        px = abs(r.transform.a) * abs(r.transform.e)
        res = abs(r.transform.a)
    tile_ha = prob.size * px / 1e4

    # threshold-free: strongest road probability anywhere along each held-out chunk
    mx = _max_along(road_h.geometry, prob, tf)
    road_h["max_prob"] = np.round(mx, 3)
    print(f"  max road-probability along each held-out road chunk "
          f"(threshold-free): min {mx.min():.3f}  p05 {np.percentile(mx, 5):.3f}"
          f"  median {np.median(mx):.3f}  max {mx.max():.3f}")
    print(f"    chunks with NO road-like signal at all (max_prob < 0.05): "
          f"{int((mx < 0.05).sum())}/{len(mx)}\n")

    n_h = len(road_h)
    print(f"  sweep over {n_h} held-out ROAD chunks, with hand-drawn negatives:")
    print(f"  {'thr':>5} {'ha':>9} {'%tile':>7}  {'found':>6} {'MISSED':>7} "
          f"{'recall':>7} {'rec_cln':>8}  {'km_cov':>7}  {'drain%':>7} {'notrd%':>7}")
    sweep = []
    clean = road_h["clean"].to_numpy()
    for t in THRESHOLDS_SWEEP:
        m = prob >= t
        dist = ndi.distance_transform_edt(~m) * res
        cov_r = coverage(road_h.geometry, dist, tf)
        cov_d = coverage(drain_h.geometry, dist, tf)
        cov_n = coverage(notrd_h.geometry, dist, tf)
        found = cov_r >= COVER_FRAC
        km_cov = float((cov_r * road_h.length_m).sum() / 1000)
        d_rate = float((cov_d >= COVER_FRAC).mean()) if len(cov_d) else 0.0
        n_rate = float((cov_n >= COVER_FRAC).mean()) if len(cov_n) else 0.0
        ha = m.sum() * px / 1e4
        sweep.append(dict(threshold=t, ha_claimed=round(ha, 2),
                          pct_of_tile=round(100 * m.mean(), 3),
                          n_heldout_road=n_h,
                          found=int(found.sum()), missed=int((~found).sum()),
                          recall=round(found.mean(), 3),
                          n_clean=n_clean,
                          found_clean=int(found[clean].sum()),
                          recall_clean=round(float(found[clean].mean()), 3),
                          km_road_covered=round(km_cov, 2),
                          km_road_total=round(road_h.length_m.sum() / 1000, 2),
                          drainage_claimed_frac=round(d_rate, 3),
                          not_road_claimed_frac=round(n_rate, 3)))
        print(f"  {t:5.2f} {ha:9.2f} {100 * m.mean():7.3f}  "
              f"{int(found.sum()):6d} {int((~found).sum()):7d} "
              f"{found.mean():7.3f} {found[clean].mean():8.3f}  {km_cov:7.2f}  "
              f"{100 * d_rate:6.1f}% {100 * n_rate:6.1f}%")
    sw = pd.DataFrame(sweep)
    sw.to_csv(OUT / "road_threshold_sweep_9t.csv", index=False)
    print(f"\n  wrote {OUT / 'road_threshold_sweep_9t.csv'}\n")

    summary = []
    for t in THRESHOLDS_PRODUCTS:
        tg = tag(t)
        m = prob >= t
        dist = ndi.distance_transform_edt(~m) * res
        cov_r = coverage(road_h.geometry, dist, tf)
        cov_d = coverage(drain_h.geometry, dist, tf)
        found = cov_r >= COVER_FRAC

        rv = road_h.copy()
        rv["coverage"] = np.round(cov_r, 3)
        rv["verdict"] = np.where(found, "found", "missed")
        rv["threshold"] = t
        miss = rv[rv.verdict == "missed"].reset_index(drop=True)
        print(f"  thr {t:.2f}: {m.sum() * px / 1e4:.2f} ha, found "
              f"{int(found.sum())}/{n_h}, MISSED {len(miss)}")

        write_raster(RASTER_DIR / f"road_unet_mask_{tg}_9t_1m.tif",
                     m.astype(np.uint8), prof, dict(dtype="uint8", nodata=0),
                     dict(THRESHOLD=str(t), SOURCE=PROB.name,
                          MEANING="1 = road probability >= threshold"))
        write_raster(RASTER_DIR / f"road_unet_prob_{tg}_9t_1m.tif",
                     np.where(m, prob, np.nan).astype(np.float32), prof,
                     dict(dtype="float32", nodata=np.nan, predictor=2),
                     dict(THRESHOLD=str(t), SOURCE=PROB.name,
                          MEANING="road probability where >= threshold"))

        gp = OUT / f"road_heldout_found_vs_missed_{tg}_9t.gpkg"
        if gp.exists():
            gp.unlink()
        rv.to_file(gp, layer="road_found_vs_missed", driver="GPKG")
        rv[rv.verdict == "found"].to_file(gp, layer="road_found", driver="GPKG")
        if len(miss):
            miss.to_file(gp, layer="road_missed", driver="GPKG")
            mid = miss.copy()
            mid["geometry"] = miss.geometry.interpolate(0.5, normalized=True)
            mid.to_file(gp, layer="midpoint_missed", driver="GPKG")
            loc = miss.copy()
            loc["geometry"] = mid.geometry.buffer(LOCATOR_R)
            loc.to_file(gp, layer="locator_missed", driver="GPKG")
        dc = drain_h.copy()
        dc["coverage"] = np.round(cov_d, 3)
        dc = dc[dc.coverage >= COVER_FRAC]
        if len(dc):
            dc.to_file(gp, layer="drainage_claimed_as_road", driver="GPKG")
        embed_style(gp, "road_found_vs_missed", style_qml(kind="line"),
                    f"green found / red missed at threshold {t}")
        (OUT / f"road_heldout_found_vs_missed_{tg}_9t.qml").write_text(
            style_qml(kind="line"))

        bmp = OUT / f"road_missed_bookmarks_{tg}_9t.xml"
        mids = miss.geometry.interpolate(0.5, normalized=True)
        bmp.write_text(bookmarks_xml(
            [(f"MISSED {i:03d}/{len(miss)} {rr.line_id} cov={rr.coverage:.2f} @{t}",
              mids.iloc[i - 1].x, mids.iloc[i - 1].y)
             for i, rr in enumerate(miss.itertuples(), 1)],
            group=f"road missed {t}", id_prefix=f"roadmiss_{tg}",
            pad=BOOKMARK_PAD))

        contact_sheet(
            OUT / f"road_missed_contactsheet_{tg}_9t.png", HILLSHADE, miss, None,
            f"Held-out ROAD chunks missed at threshold {t}  "
            f"(red = annotated centreline)", CROP_HALF_M,
            lambda rr: (f"{rr.line_id}  ({rr.split})\n"
                        f"coverage {rr.coverage:.2f}  max_prob {rr.max_prob:.2f}"))

        summary.append(dict(threshold=t, ha_claimed=round(m.sum() * px / 1e4, 2),
                            pct_of_tile=round(100 * m.mean(), 3),
                            found=int(found.sum()), missed=len(miss),
                            n_heldout_road=n_h,
                            drainage_claimed=int((cov_d >= COVER_FRAC).sum()),
                            n_heldout_drainage=len(drain_h)))

    pd.DataFrame(summary).to_csv(
        OUT / "road_threshold_found_vs_missed_summary_9t.csv", index=False)
    road_h.drop(columns="geometry").to_csv(
        OUT / "road_heldout_max_prob_9t.csv", index=False)
    print(f"\n  tile = {tile_ha:.0f} ha")
    print(f"  all products in {OUT}")
    print(f"  rasters in {RASTER_DIR}")
    return 0


def _max_along(lines: gpd.GeoSeries, prob: np.ndarray, transform) -> np.ndarray:
    inv = ~transform
    H, W = prob.shape
    out = np.zeros(len(lines))
    for i, geom in enumerate(lines):
        L = max(geom.length, 1e-6)
        n = max(int(np.ceil(L / SAMPLE_M)) + 1, 2)
        pts = [geom.interpolate(d) for d in np.linspace(0, L, n)]
        cols, rows = inv * (np.array([p.x for p in pts]),
                            np.array([p.y for p in pts]))
        rr = np.clip(rows.astype(int), 0, H - 1)
        cc = np.clip(cols.astype(int), 0, W - 1)
        out[i] = float(prob[rr, cc].max())
    return out


if __name__ == "__main__":
    sys.exit(main())
