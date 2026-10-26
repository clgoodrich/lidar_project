"""Score every NISAR feature band as a pad detector (protocol: docs/iterations/nisar_feature_products_plan.md).

Positives: annotated pad cores (pad shrunk CORE_SHRINK_M), one value per pad = median over core pixels.
Negatives: discs of DECOY_R_PX pixels, K_DECOY per pad, at least EXCL_M from any pad, pit, road or DEP
well. Two kinds:
  matched    decoy disc mean cover within 0.05 and mean slope within 1 degree of the pad core (so open ground is compared with open ground)
  unmatched  any allowed ground
AUC = P(pad value > decoy value), 95% CI by bootstrap over pads and decoys, Mann-Whitney p, then
Benjamini-Hochberg q over all bands. Also reported by canopy class of the pad (open < 25%, partly
grown 25-50%, grown over > 50%). Registration is the delivered one (no shift).

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_score_9t.py [--area 9t]
"""
import json
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from scipy.stats import mannwhitneyu, rankdata
from shapely.ops import unary_union

import _nisar_feat_common as C

TARGET = os.environ.get("TARGET", "pad")                   # "pad" (995 pad polygons) or "pit" (pit_outside rims)
BASE_CORE = 0.0 if TARGET == "pit" else 5.0
CORE_SHRINK_M = float(os.environ.get("CORE_SHRINK_M", BASE_CORE))   # larger values keep the window away from the edge
# decoy disc: radius 4 px (49 px) for pads; 1.5 px (9 px) for pits, whose rims cover about 8 px
EXCL_M, DECOY_R_PX, K_DECOY, B, SEED = 100.0, (2 if TARGET == "pit" else 4), 10, 300, 20261026
DISC_R2 = 2.25 if TARGET == "pit" else 16.0
N_DISC = 9 if TARGET == "pit" else 49   # pixels in a decoy disc
ROAD_NEAR = os.environ.get("ROAD_NEAR") == "1"        # decoys restricted to 30-100 m from a road (pads sit beside one)
SUFFIX = ("" if CORE_SHRINK_M == BASE_CORE else f"_core{CORE_SHRINK_M:.0f}m") + ("_roadnear" if ROAD_NEAR else "")
TOL_COVER, TOL_SLOPE_DEG = 0.05, 1.0
COVER_BINS = [0, 0.25, 0.5, 0.75, 1.01]
CLASSES = {"open": (0, 0.25), "partly": (0.25, 0.5), "grown": (0.5, 1.01)}


def auc_of(a, b):
    r = rankdata(np.r_[a, b])
    return (r[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))


def boot_ci(a, b, rng):
    v = [auc_of(rng.choice(a, len(a)), rng.choice(b, len(b))) for _ in range(B)]
    return np.percentile(v, [2.5, 97.5])


def bh(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    q = np.empty_like(p)
    q[o] = np.minimum.accumulate((p[o] * len(p) / np.arange(1, len(p) + 1))[::-1])[::-1]
    return np.minimum(q, 1)


def main():
    idx, stack, tf, shape = C.load()
    del stack
    grids = C.lidar_grids(tf, shape)
    feats = C.read_all()
    # product 1 stack (flatness script), without its lidar bands
    p1 = C.FEAT_DIR / f"nisar_feature_stack_{C.A.TAG}_5m.tif"
    if p1.exists():
        with rasterio.open(p1) as r:
            for i, d in enumerate(r.descriptions, 1):
                if not d.startswith("lidar_"):
                    feats[f"amp_stats:{d}"] = r.read(i)
    # lidar controls: if one of these separates pads from matched decoys, canopy or terrain leaks through the bins
    feats["control:cover"], feats["control:slope"], feats["control:rough"] = grids["cover"], grids["slope"], grids["rough"]
    print(f"{len(feats)} bands", flush=True)

    pads = C.ifg.read_layer(C.ifg.ANN, "plat").to_crs(CRS := C.CRS)
    pits = C.ifg.read_layer(C.ifg.ANN, "pit_outside").to_crs(CRS)
    targets = pits if TARGET == "pit" else pads
    pads_u = pads.union_all()
    roads = C.ifg.read_layer(C.ifg.ANN, "roads").to_crs(CRS)
    wells = gpd.read_file(C.A.WELLS).to_crs(CRS)
    keep = [pads.union_all(), pits.union_all(), wells.union_all()] + ([] if ROAD_NEAR else [roads.union_all()])
    excl_geom = unary_union(keep).buffer(EXCL_M)
    excl = rasterize([(excl_geom, 1)], out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
    if ROAD_NEAR:
        rd = roads.union_all()
        d_pad = np.array([g.centroid.distance(rd) for g in pads.geometry])
        print(f"pad centroid to road: median {np.median(d_pad):.0f} m, 90th pct {np.percentile(d_pad, 90):.0f} m", flush=True)
        far = rasterize([(rd.buffer(100), 1)], out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        near = rasterize([(rd.buffer(30), 1)], out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        excl = excl | ~far | near

    # pad table: core pixels, mean cover and slope
    rows = []
    for g in targets.geometry:
        core = g.buffer(-CORE_SHRINK_M) if CORE_SHRINK_M else g
        px = C.st.pixel_index(core, tf, shape) if not core.is_empty else np.array([], int)
        if len(px) < 4:
            continue
        cov, slo = np.nanmean(grids["cover"].ravel()[px]), np.nanmean(grids["slope"].ravel()[px])
        if np.isfinite(cov) and np.isfinite(slo):
            # score on the n_disc core pixels nearest the centre so a pad median has the same noise as a decoy disc
            rr, cc = np.divmod(px, shape[1])
            near = px[np.argsort((rr - np.median(rr)) ** 2 + (cc - np.median(cc)) ** 2)[:N_DISC]]
            rows.append((px, cov, slo, near, g.centroid.distance(pads_u) if TARGET == "pit" else np.nan))
    print(f"{len(rows)} of {len(targets)} {TARGET}s usable", flush=True)

    rng = np.random.default_rng(SEED)
    yy, xx = np.mgrid[-DECOY_R_PX:DECOY_R_PX + 1, -DECOY_R_PX:DECOY_R_PX + 1]
    disc = np.c_[yy[yy ** 2 + xx ** 2 <= DISC_R2], xx[yy ** 2 + xx ** 2 <= DISC_R2]]
    assert len(disc) == N_DISC
    anyvalid = np.all([np.isfinite(a) for a in list(feats.values())[:3]], axis=0)
    ok = (np.isfinite(grids["cover"]) & np.isfinite(grids["slope"]) & ~excl & anyvalid)
    ok[:DECOY_R_PX + 1] = ok[-DECOY_R_PX - 1:] = False
    ok[:, :DECOY_R_PX + 1] = ok[:, -DECOY_R_PX - 1:] = False
    cand = np.flatnonzero(ok.ravel())
    print(f"{len(cand)} candidate decoy pixels", flush=True)

    # fine matching: decoy disc mean cover within TOL_COVER and mean slope within TOL_SLOPE_DEG of the pad core
    def disc_px(centres):
        r, c = np.divmod(centres, shape[1])
        rr = np.clip(r[:, None] + disc[None, :, 0], 0, shape[0] - 1)
        cc = np.clip(c[:, None] + disc[None, :, 1], 0, shape[1] - 1)
        return rr * shape[1] + cc

    cand_cov = np.nanmean(grids["cover"].ravel()[disc_px(cand)], 1)
    cand_slo = np.nanmean(grids["slope"].ravel()[disc_px(cand)], 1)
    dec_m, dec_pad = [], []
    for k, r in enumerate(rows):
        p = cand[(np.abs(cand_cov - r[1]) <= TOL_COVER) & (np.abs(cand_slo - r[2]) <= TOL_SLOPE_DEG)]
        if len(p) >= K_DECOY:
            dec_m += list(rng.choice(p, K_DECOY, replace=False))
            dec_pad += [k] * K_DECOY
    dec_m, dec_pad = np.array(dec_m), np.array(dec_pad)
    print(f"{len(set(dec_pad))} of {len(rows)} pads have matched decoys", flush=True)
    dec_u = rng.choice(cand, len(rows) * K_DECOY)

    dm_px, du_px = disc_px(dec_m), disc_px(dec_u)
    pad_cover = np.array([r[1] for r in rows])
    pad_dist = np.array([r[4] for r in rows])
    out, store = [], {}
    for name, a in feats.items():
        f = a.ravel()
        pv = np.array([np.nanmedian(f[r[3]]) if np.isfinite(f[r[3]]).sum() >= 4 else np.nan for r in rows])
        dmv, duv = np.nanmedian(f[dm_px], 1), np.nanmedian(f[du_px], 1)
        store[name] = (pv, dmv)
        good = np.isfinite(pv) & np.isin(np.arange(len(rows)), dec_pad)
        if good.sum() < 30 or np.isfinite(dmv).sum() < 100:
            continue
        a_m, b_m = pv[good], dmv[np.isfinite(dmv)]
        a_u, b_u = pv[good], duv[np.isfinite(duv)]
        lo, hi = boot_ci(a_m, b_m, rng)
        rec = dict(band=name, n_pads=int(good.sum()), auc_matched=round(auc_of(a_m, b_m), 3),
                   ci_lo=round(lo, 3), ci_hi=round(hi, 3),
                   p=float(mannwhitneyu(a_m, b_m).pvalue), auc_unmatched=round(auc_of(a_u, b_u), 3))
        for cname, (c0, c1) in CLASSES.items():
            sel = good & (pad_cover >= c0) & (pad_cover < c1)
            dsel = np.isin(dec_pad, np.flatnonzero(sel)) & np.isfinite(dmv)
            rec[f"auc_{cname}"] = round(auc_of(pv[sel], dmv[dsel]), 3) if sel.sum() >= 15 and dsel.sum() >= 50 else np.nan
            rec[f"n_{cname}"] = int(sel.sum())
        if TARGET == "pit":
            sel = good & (pad_dist >= 50)
            dsel = np.isin(dec_pad, np.flatnonzero(sel)) & np.isfinite(dmv)
            rec["auc_farpad"] = round(auc_of(pv[sel], dmv[dsel]), 3) if sel.sum() >= 15 and dsel.sum() >= 50 else np.nan
            rec["n_farpad"] = int(sel.sum())
        out.append(rec)
    res = pd.DataFrame(out)
    blk = lambda px: (np.divmod(px, shape[1])[0] * 5 // 500) * 100000 + (np.divmod(px, shape[1])[1] * 5 // 500)  # noqa: E731
    names = list(store)
    np.savez_compressed(C.FEAT_DIR / f"nisar_{TARGET}_samples_{C.A.TAG}{SUFFIX}.npz", names=names,
                        pad=np.stack([store[n][0] for n in names]), dec=np.stack([store[n][1] for n in names]),
                        dec_pad=dec_pad, pad_block=blk(np.array([int(np.median(r[0])) for r in rows])), dec_block=blk(dec_m),
                        pad_cover=pad_cover, pad_dist=pad_dist)
    res["q"] = bh(res.p.values)
    res["dev"] = (res.auc_matched - 0.5).abs()
    res = res.sort_values("dev", ascending=False).drop(columns="dev")
    path = C.OUT / f"nisar_{TARGET}_feature_auc_per_band_{C.A.TAG}{SUFFIX}.csv"
    res.to_csv(path, index=False)
    json.dump(dict(n_bands=len(res), n_pads=len(rows), n_candidate_px=int(len(cand)),
                   n_q_lt_0p05=int((res.q < 0.05).sum()), core_shrink_m=CORE_SHRINK_M, excl_m=EXCL_M,
                   decoy_r_px=DECOY_R_PX, k_decoy=K_DECOY),
              open(C.OUT / f"nisar_{TARGET}_feature_auc_summary_{C.A.TAG}{SUFFIX}.json", "w"), indent=2)
    pd.set_option("display.width", 220)
    print(res.head(25).to_string(index=False))
    print("bands with q < 0.05:", int((res.q < 0.05).sum()), "of", len(res))


if __name__ == "__main__":
    main()
