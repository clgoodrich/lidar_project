"""Score every NISAR feature band as a pad detector (protocol: docs/iterations/nisar_feature_products_plan.md).

Positives: annotated pad cores (pad shrunk CORE_SHRINK_M), one value per pad = median over core pixels.
Negatives: discs of DECOY_R_PX pixels, K_DECOY per pad, at least EXCL_M from any pad, pit, road or DEP
well. Two kinds:
  matched    decoy disc mean cover within 0.05 and mean slope within 1 degree of the pad core (so open ground is compared with open ground)
  unmatched  any allowed ground
AUC = P(pad value > decoy value), 95% CI by bootstrap over pads and decoys, Mann-Whitney p, then
Benjamini-Hochberg q over all bands. Also reported by canopy class of the pad (open < 25%, partly
grown 25-50%, grown over > 50%). Registration is the delivered one (no shift).

Options (environment), each adds a tag to the output names (C.suffix):
  SHAPE=1      decoys use the target's own pixel footprint (translated onto matched ground), not a disc
  INC_MATCH=1  decoys are also matched on the terrain illumination gain of each track (geometry:sim_db, a function of
               the local incidence angle), within 0.5 dB
  CONFUSER=1   decoys come only from other clearings: connected open ground (smoothed canopy cover < 0.30) of at least
               1,000 m2, at least 50 m from every annotated pad, pit and well and 15 m from a road (with ROAD_NEAR=1, 30 to 100 m beside a road).
               House lots, landings, fields and corridors. Unannotated pads in that set are unlabelled positives.
  PLACEBO=1    the "pad" is the pad's footprint moved 150 to 300 m onto matched ground (it should score like a
               decoy, but it keeps the pad's neighbourhood)

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_score_9t.py [--area 9t]
"""
import json
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import gaussian_filter, sobel, uniform_filter
from scipy.stats import mannwhitneyu, rankdata
from shapely.ops import unary_union

import _nisar_feat_common as C

TARGET = os.environ.get("TARGET", "pad")                   # "pad" (995 pad polygons) or "pit" (pit_outside rims)
BASE_CORE = 0.0 if TARGET == "pit" else 5.0
CORE_SHRINK_M = float(os.environ.get("CORE_SHRINK_M", BASE_CORE))   # larger values keep the window away from the edge
# decoy disc: radius 4 px (49 px) for pads; 1.5 px (9 px) for pits, whose rims cover about 8 px
EXCL_M, DECOY_R_PX, K_DECOY, B, SEED = 100.0, (2 if TARGET == "pit" else 4), 10, 300, 20261026
DISC_R2 = 2.25 if TARGET == "pit" else 16.0
N_DISC = 9 if TARGET == "pit" else 49   # pixels in the largest decoy disc
BINS = [4, 9] if TARGET == "pit" else [9, 16, 25, 36, 49]   # a target is scored on the largest bin that fits its core; its decoys use the same count
ROAD_NEAR = os.environ.get("ROAD_NEAR") == "1"        # decoys restricted to 30-100 m from a road (pads sit beside one)
MATCH_ROUGH = os.environ.get("MATCH_ROUGH") == "1"    # also match decoy roughness (pits are rough by definition)
LOCAL_M = float(os.environ.get("LOCAL_M", 0))         # >0: decoys only 100 m to LOCAL_M from their own target (same neighbourhood)
SHAPE = os.environ.get("SHAPE") == "1" or os.environ.get("PLACEBO") == "1"     # a placebo keeps the pad's footprint shape
INC_MATCH = os.environ.get("INC_MATCH") == "1"
PLACEBO = os.environ.get("PLACEBO") == "1"
CONFUSER = os.environ.get("CONFUSER") == "1"
CLEARING_MIN_PX, CLEARING_COVER = 40, 0.30       # 40 px at 5 m = 1,000 m2
SHIFT_M = (150.0, 300.0)
SUFFIX = C.suffix(TARGET)
TOL_COVER, TOL_SLOPE_DEG, TOL_INC_DB = 0.05, 1.0, 0.5
PREFILTER_CAP = 80000      # SHAPE: candidates kept for the exact footprint test, after the disc prefilter
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


def local_sd(d, w):
    m = uniform_filter(d, w)
    return np.sqrt(np.maximum(uniform_filter(d * d, w) - m * m, 0))


def lidar_texture(grids):
    """Equal-richness lidar baseline: the same kind of operators the SAR spatial product uses, run on the lidar
    cover, slope and roughness grids, plus forest fraction at 75 m and 155 m (a small opening in forest)."""
    out = {}
    for key, a in grids.items():
        bad = ~np.isfinite(a)
        d = np.where(bad, np.nanmedian(a), a).astype(np.float64)
        m = lambda x: np.where(bad, np.nan, x)  # noqa: E731
        for w in (3, 7, 11, 15):
            out[f"lidartex:{key}_sd{w}"] = m(local_sd(d, w))
        ds = gaussian_filter(d, 1)
        out[f"lidartex:{key}_grad"] = m(np.hypot(sobel(ds, 0), sobel(ds, 1)))
        out[f"lidartex:{key}_dog"] = m(gaussian_filter(d, 1) - gaussian_filter(d, 4))
        out[f"lidartex:{key}_mean15"] = m(uniform_filter(d, 15))
        if key == "cover":
            out["lidartex:cover_mean31"], out["lidartex:cover_sd31"] = m(uniform_filter(d, 31)), m(local_sd(d, 31))
    return out


def main():
    idx, stack, tf, shape = C.load()
    del stack
    grids = C.lidar_grids(tf, shape)
    feats = C.read_all()
    # height residual dropped 2026-10-26: forest median height 0.1-0.8 m (expected metres to tens of metres) and a sign forced per track
    feats = {k: v for k, v in feats.items() if not k.startswith("heightresid:")}
    # product 1 stack (flatness script), without its lidar bands
    p1 = C.FEAT_DIR / f"nisar_feature_stack_{C.A.TAG}_5m.tif"
    if p1.exists():
        with rasterio.open(p1) as r:
            for i, d in enumerate(r.descriptions, 1):
                if not d.startswith("lidar_"):
                    feats[f"amp_stats:{d}"] = r.read(i)
    # lidar controls: if one of these separates pads from matched decoys, canopy or terrain leaks through the bins
    feats["control:cover"], feats["control:slope"], feats["control:rough"] = grids["cover"], grids["slope"], grids["rough"]
    feats.update(lidar_texture(grids))
    print(f"{len(feats)} bands", flush=True)

    pads = C.ifg.read_layer(C.ifg.ANN, "plat").to_crs(CRS := C.CRS)
    pits = C.ifg.read_layer(C.ifg.ANN, "pit_outside").to_crs(CRS)
    targets = pits if TARGET == "pit" else pads
    pads_u = pads.union_all()
    roads = C.ifg.read_layer(C.ifg.ANN, "roads").to_crs(CRS)
    wells = gpd.read_file(C.A.WELLS).to_crs(CRS)
    keep = [pads.union_all(), pits.union_all(), wells.union_all()] + ([] if ROAD_NEAR else [roads.union_all()])
    excl_geom = unary_union(keep).buffer(EXCL_M)
    if CONFUSER:     # clearings are by definition not pads, so only 50 m clear of pads, pits and wells and 15 m of roads (100 m left almost none)
        excl_geom = unary_union([pads.union_all(), pits.union_all(), wells.union_all()]).buffer(50.0).union(roads.union_all().buffer(15.0))
    excl = rasterize([(excl_geom, 1)], out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
    if ROAD_NEAR:
        rd = roads.union_all()
        d_pad = np.array([g.centroid.distance(rd) for g in pads.geometry])
        print(f"pad centroid to road: median {np.median(d_pad):.0f} m, 90th pct {np.percentile(d_pad, 90):.0f} m", flush=True)
        far = rasterize([(rd.buffer(100), 1)], out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        near = rasterize([(rd.buffer(30), 1)], out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        excl = excl | ~far | near

    # target table: core pixels, then the nb core pixels nearest the centre (nb = largest bin that fits the core)
    inc_keys = sorted(k for k in feats if k.startswith("geometry:sim_db_t")) if INC_MATCH else []
    G = {**grids, **{k: feats[k] for k in inc_keys}}
    rows = []
    for g in targets.geometry:
        core = g.buffer(-CORE_SHRINK_M) if CORE_SHRINK_M else g
        px = C.st.pixel_index(core, tf, shape) if not core.is_empty else np.array([], int)
        fit = [b for b in BINS if b <= len(px)]
        if not fit:
            continue
        nb = max(fit)
        rr, cc = np.divmod(px, shape[1])
        near = px[np.argsort((rr - np.median(rr)) ** 2 + (cc - np.median(cc)) ** 2)[:nb]]
        cov, slo = np.nanmean(grids["cover"].ravel()[near]), np.nanmean(grids["slope"].ravel()[near])
        rou = np.nanmean(grids["rough"].ravel()[near])
        inc = np.array([np.nanmean(G[k].ravel()[near]) for k in inc_keys])
        nr, nc = np.divmod(near, shape[1])
        ctr = (int(round(np.median(rr))), int(round(np.median(cc))))
        off = np.c_[nr - ctr[0], nc - ctr[1]]          # footprint of the nb pixels, relative to the centre pixel
        if np.isfinite(cov) and np.isfinite(slo) and (np.isfinite(rou) or not MATCH_ROUGH) and np.isfinite(inc).all():
            rows.append((px, cov, slo, near, g.centroid.distance(pads_u) if TARGET == "pit" else np.nan, rou, g.area,
                         g.centroid.x, g.centroid.y, nb, off, inc))
    print(f"{len(rows)} of {len(targets)} {TARGET}s usable", flush=True)

    rng = np.random.default_rng(SEED)
    yy, xx = np.mgrid[-DECOY_R_PX:DECOY_R_PX + 1, -DECOY_R_PX:DECOY_R_PX + 1]
    disc = np.c_[yy[yy ** 2 + xx ** 2 <= DISC_R2], xx[yy ** 2 + xx ** 2 <= DISC_R2]]
    assert len(disc) == N_DISC
    disc = disc[np.lexsort((np.arctan2(disc[:, 0], disc[:, 1]), (disc ** 2).sum(1)))]   # nearest first, so disc[:nb] is the nb-pixel disc
    anyvalid = np.all([np.isfinite(a) for a in list(feats.values())[:3]], axis=0)
    ok = (np.isfinite(grids["cover"]) & np.isfinite(grids["slope"]) & ~excl & anyvalid)
    ok[:DECOY_R_PX + 1] = ok[-DECOY_R_PX - 1:] = False
    ok[:, :DECOY_R_PX + 1] = ok[:, -DECOY_R_PX - 1:] = False
    if CONFUSER:
        from scipy.ndimage import binary_erosion, label
        clear = uniform_filter(np.nan_to_num(grids["cover"], nan=1.0), 3) < CLEARING_COVER
        lab, _ = label(clear)
        size = np.bincount(lab.ravel())
        big = (lab > 0) & np.isin(lab, np.flatnonzero(size >= CLEARING_MIN_PX))
        ok &= binary_erosion(big, iterations=DECOY_R_PX)       # the whole footprint sits inside the clearing
        print(f"clearings of at least {CLEARING_MIN_PX * 25} m2: {int((size[1:] >= CLEARING_MIN_PX).sum())} of {int(lab.max())} open patches", flush=True)
    cand = np.flatnonzero(ok.ravel())
    print(f"{len(cand)} candidate decoy pixels", flush=True)

    # footprint of target k placed on centre pixels: the target's own offsets (SHAPE) or the nb-pixel disc
    OFFA = np.zeros((len(rows), N_DISC, 2), int)
    VALID = np.zeros((len(rows), N_DISC), bool)
    for k, r in enumerate(rows):
        o = r[10] if SHAPE else disc[:r[9]]
        OFFA[k, :len(o)], VALID[k, :len(o)] = o, True
    NB = np.array([r[9] for r in rows])

    def fp_px(centres, k):
        """(n, nb) flat pixel indices of target k's footprint placed on each centre."""
        r, c = np.divmod(centres, shape[1])
        o = OFFA[k, :NB[k]]
        return (np.clip(r[:, None] + o[None, :, 0], 0, shape[0] - 1) * shape[1]
                + np.clip(c[:, None] + o[None, :, 1], 0, shape[1] - 1))

    def vals_at(f, centres, pids, OFFA, VALID, NB):
        """Median of f over each centre's own footprint (the footprint of target pids[i])."""
        r, c = np.divmod(centres, shape[1])
        o = OFFA[pids]
        v = f[np.clip(r[:, None] + o[:, :, 0], 0, shape[0] - 1) * shape[1] + np.clip(c[:, None] + o[:, :, 1], 0, shape[1] - 1)]
        v[~VALID[pids]] = np.nan
        out = np.nanmedian(v, 1)
        out[np.isfinite(v).sum(1) < np.minimum(4, NB[pids])] = np.nan      # same finite-support rule as the targets
        return out

    mkeys = ["cover", "slope", "rough"] + inc_keys

    def prep(cand_arr):
        """Candidate pixels with their map coordinates and, per footprint size, the mean of each matching variable over the disc."""
        x_, y_ = rasterio.transform.xy(tf, *np.divmod(cand_arr, shape[1]))
        st_ = {}
        for nb in sorted({r[9] for r in rows}):
            rr_, cc_ = np.divmod(cand_arr, shape[1])
            ix = (np.clip(rr_[:, None] + disc[None, :nb, 0], 0, shape[0] - 1) * shape[1]
                  + np.clip(cc_[:, None] + disc[None, :nb, 1], 0, shape[1] - 1))
            st_[nb] = [np.nanmean(G[k].ravel()[ix], 1) for k in mkeys]
            del ix
        return dict(cand=cand_arr, cx=np.asarray(x_), cy=np.asarray(y_), cstat=st_)

    P0 = prep(cand)
    cx, cy = P0["cx"], P0["cy"]
    tol_rou = 0.25 * np.nanstd([r[5] for r in rows])      # a quarter of the spread of target roughness

    def match_pool(k, cov0, slo0, rou0, inc0, centre_xy, lo_m, hi_m, P=None):
        """Indices into P["cand"] (default: the decoy candidates) whose footprint matches target k's cover and slope
        (and roughness, incidence gain), lo_m to hi_m from centre_xy (hi_m 0 = anywhere)."""
        P = P or P0
        cand_, cx_, cy_ = P["cand"], P["cx"], P["cy"]
        pool = np.arange(len(cand_))
        if hi_m:
            d = np.hypot(cx_ - centre_xy[0], cy_ - centre_xy[1])
            pool = pool[(d >= lo_m) & (d <= hi_m)]
        st = P["cstat"][NB[k]]
        if not SHAPE:
            ok = (np.abs(st[0][pool] - cov0) <= TOL_COVER) & (np.abs(st[1][pool] - slo0) <= TOL_SLOPE_DEG)
            if MATCH_ROUGH:
                ok &= np.abs(st[2][pool] - rou0) <= tol_rou
            for j in range(len(inc_keys)):
                ok &= np.abs(st[3 + j][pool] - inc0[j]) <= TOL_INC_DB
            return pool[ok]
        pre = pool[(np.abs(st[0][pool] - cov0) <= 4 * TOL_COVER) & (np.abs(st[1][pool] - slo0) <= 4 * TOL_SLOPE_DEG)]
        if len(pre) > PREFILTER_CAP:
            pre = rng.choice(pre, PREFILTER_CAP, replace=False)
        if not len(pre):
            return pre
        ix = fp_px(cand_[pre], k)
        fs = [np.nanmean(G[key].ravel()[ix], 1) for key in mkeys]
        ok = (np.abs(fs[0] - cov0) <= TOL_COVER) & (np.abs(fs[1] - slo0) <= TOL_SLOPE_DEG)
        if MATCH_ROUGH:
            ok &= np.abs(fs[2] - rou0) <= tol_rou
        for j in range(len(inc_keys)):
            ok &= np.abs(fs[3 + j] - inc0[j]) <= TOL_INC_DB
        return pre[ok]

    if PLACEBO:
        # the "pad" is the pad's footprint moved 150 to 300 m onto matched ground; targets with no such ground drop out
        # pads sit beside roads and other pads, so the ring ground only keeps 50 m clear of pads, pits and wells and 15 m of roads
        loose = unary_union([pads.union_all(), pits.union_all(), wells.union_all()]).buffer(50.0).union(roads.union_all().buffer(15.0))
        excl_pl = rasterize([(loose, 1)], out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        ok_pl = np.isfinite(grids["cover"]) & np.isfinite(grids["slope"]) & ~excl_pl & anyvalid
        ok_pl[:DECOY_R_PX + 1] = ok_pl[-DECOY_R_PX - 1:] = False
        ok_pl[:, :DECOY_R_PX + 1] = ok_pl[:, -DECOY_R_PX - 1:] = False
        P_pl = prep(np.flatnonzero(ok_pl.ravel()))
        keep, newrows = [], []
        for k, r in enumerate(rows):
            p = match_pool(k, r[1], r[2], r[5], r[11], (r[7], r[8]), SHIFT_M[0], SHIFT_M[1], P=P_pl)
            if not len(p):
                continue
            c = int(rng.choice(p))
            near = fp_px(P_pl["cand"][[c]], k)[0]
            gm = lambda key: float(np.nanmean(G[key].ravel()[near]))  # noqa: E731
            newrows.append((r[0], gm("cover"), gm("slope"), near, r[4], gm("rough"), r[6], P_pl["cx"][c], P_pl["cy"][c], r[9], r[10],
                            np.array([gm(key) for key in inc_keys])))
            keep.append(k)
        print(f"placebo: {len(keep)} of {len(rows)} targets have matched ground 150 to 300 m away", flush=True)
        rows = newrows
        OFFA, VALID, NB = OFFA[keep], VALID[keep], NB[keep]
    dec_m, dec_pad = [], []
    for k, r in enumerate(rows):
        p = match_pool(k, r[1], r[2], r[5], r[11], (r[7], r[8]), 100.0 if LOCAL_M else 0.0, LOCAL_M)
        if PLACEBO:
            p = p[np.hypot(cx[p] - r[7], cy[p] - r[8]) >= 60.0]       # a decoy is never the placebo's own spot
        if len(p) >= K_DECOY:
            dec_m += list(cand[rng.choice(p, K_DECOY, replace=False)])
            dec_pad += [k] * K_DECOY
    dec_m, dec_pad = np.array(dec_m), np.array(dec_pad)
    print(f"{len(set(dec_pad))} of {len(rows)} pads have matched decoys", flush=True)
    dec_u = rng.choice(cand, len(rows) * K_DECOY)
    du_pad = np.repeat(np.arange(len(rows)), K_DECOY)
    vals = lambda f, centres, pids: vals_at(f, centres, pids, OFFA, VALID, NB)  # noqa: E731

    dec_nb = np.array([rows[k][9] for k in dec_pad])
    pad_cover = np.array([r[1] for r in rows])
    pad_dist = np.array([r[4] for r in rows])
    out, store = [], {}
    for name, a in feats.items():
        f = a.ravel()
        pv = np.array([np.nanmedian(f[r[3]]) if np.isfinite(f[r[3]]).sum() >= 4 else np.nan for r in rows])
        dmv, duv = vals(f, dec_m, dec_pad), vals(f, dec_u, du_pad)
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
    pr, pc = rasterio.transform.rowcol(tf, [r[7] for r in rows], [r[8] for r in rows])   # block of the centroid, not a median of flat pixel indices
    pad_block = (np.clip(pr, 0, shape[0] - 1) * 5 // 500) * 100000 + (np.clip(pc, 0, shape[1] - 1) * 5 // 500)
    names = list(store)
    np.savez_compressed(C.FEAT_DIR / f"nisar_{TARGET}_samples_{C.A.TAG}{SUFFIX}.npz", names=names,
                        pad=np.stack([store[n][0] for n in names]), dec=np.stack([store[n][1] for n in names]),
                        dec_pad=dec_pad, pad_block=pad_block, dec_block=blk(dec_m),
                        pad_n=np.array([r[9] for r in rows]), dec_n=dec_nb,
                        pad_cover=pad_cover, pad_dist=pad_dist, pad_area=np.array([r[6] for r in rows]),
                        pad_xy=np.array([[r[7], r[8]] for r in rows]),
                        dec_xy=np.array(rasterio.transform.xy(tf, *np.divmod(dec_m, shape[1]))).T,
                        # footprints, so that a new raster can be read on exactly the same pixels (C.sample_values)
                        pad_near=np.array([np.r_[r[3], np.full(N_DISC - len(r[3]), -1)] for r in rows]), dec_ctr=dec_m,
                        off_a=OFFA, valid_a=VALID, grid_shape=np.array(shape))
    res["q"] = bh(res.p.values)
    res["dev"] = (res.auc_matched - 0.5).abs()
    res = res.sort_values("dev", ascending=False).drop(columns="dev")
    path = C.OUT / f"nisar_{TARGET}_feature_auc_per_band_{C.A.TAG}{SUFFIX}.csv"
    res.to_csv(path, index=False)
    json.dump(dict(n_bands=len(res), n_pads=len(rows), n_candidate_px=int(len(cand)),
                   n_q_lt_0p05=int((res.q < 0.05).sum()), core_shrink_m=CORE_SHRINK_M, excl_m=EXCL_M,
                   decoy_r_px=DECOY_R_PX, k_decoy=K_DECOY, match_rough=MATCH_ROUGH, local_m=LOCAL_M),
              open(C.OUT / f"nisar_{TARGET}_feature_auc_summary_{C.A.TAG}{SUFFIX}.json", "w"), indent=2)
    pd.set_option("display.width", 220)
    print(res.head(25).to_string(index=False))
    print("bands with q < 0.05:", int((res.q < 0.05).sum()), "of", len(res))


if __name__ == "__main__":
    main()
