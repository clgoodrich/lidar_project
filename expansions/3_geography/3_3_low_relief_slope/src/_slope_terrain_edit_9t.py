"""3.3 S3. Paired terrain-edit test on real low-relief 9t ground (pit edits against sham edits).

Purpose
    Question 2 of fw_3_3. Insert a real pit shape into real low-slope 9t ground, recompute every
    model channel from the edited DEM, and score it with a frozen model. Compare with sham
    edits (bump, ramp, flat cut) of the same footprint and amplitude at the same location, and
    with the unedited background. Report paired score and rank changes, never a half-score gate.

Algorithm
    1. Locations. Seeded uniform draws inside 9t. Kept when the 25 m mean slope is at or under
       the S1 lowest-tercile cut, the point lies at least the derived buffer from every
       annotated floor, rim and pad, it is outside audit blocks, it has the full context margin
       inside the tile, and it is at least min_spacing_m from earlier locations.
    2. Donors. Annotated floors with a rim. Donor patch = 0.5 m DEM around the rim plus a pad.
       A least-squares plane is fitted to cells outside the rim. Residual = patch minus plane.
       Weight = 1 inside the rim, fading to 0 over feather_px cells outside it.
    3. Variants at each location. background (unedited). pit (target + weight x donor residual).
       bump (+A x weight x paraboloid). ramp (A x weight x linear ramp, zero mean). flat_cut
       (weight blends the footprint to its minimum elevation, a terrace). A = donor depth below
       its plane.
    4. Channels. All seven model channels are recomputed from each variant DEM on a window with
       context_margin_m on every side, using the 9t builder helpers (disk_kernel,
       nanmean_filter, openness from s1_build/_build_derivatives.py). Derivative layers are
       never pasted. The background channels are recomputed the same way, so the comparison is
       paired. Outside the edit influence zone the edited and background channels must agree to
       float rounding (checked per location).
    5. Score. Frozen model on each window. Score = max floor probability inside the footprint.
       Rank = rank of the best overlapping blob among all blobs in the window at the frozen
       proposal cutoff. Detected = rank at or under round(40 x window km2).

Inputs
    held     data/9t/derived/05/dem_9t_05.tif, features_pit_9t_05.tif (channel order),
             data/9t/derived/1m/slope_9t_1m.tif, qgis/annotations/annotations_proj.gpkg,
             data/9t/derived/05/pit_blocks_9t.gpkg, 3.3 S1 run folder (slope cut, proposal cutoff)
    assumed  P1 isolated pit checkpoints and split file, P2 audit block list, P1 derived buffer
             (config_3_3.json "assumed"). --allow-cv5 scores with the CV5 fold whose held-out
             blocks hold the location, labelled provisional. --provisional-buffer and
             --no-audit-list allow a dry build before P1 and P2 exist, labelled provisional.

Outputs (run folder under expansions/3_geography/3_3_low_relief_slope/results/<run_id>/)
    slope_edit_locations_9t.csv        locations, donor, amplitude, seam statistics, diff check
    slope_edit_paired_scores_9t.csv    one row per location, score, rank, detected per variant
    slope_edit_paired_summary_9t.json  paired medians and bootstrap intervals over locations
    expansions/3_geography/3_3_low_relief_slope/data/interim/slope_edit_windows_9t/loc*.npz
                                       DEM windows of the first n_save locations (for S4 renders)

Run (expensive, needs the GPU and P1; not run by the build agent)
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_terrain_edit_9t.py --n 200
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_terrain_edit_9t.py --n 5 --no-score --provisional-buffer --no-audit-list
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
sys.path.insert(0, str(HERE.parents[2] / "3_1_warren_forest_mckean" / "src"))
import expkit as ek  # noqa: E402
import _geo_xfer_lib as xl  # noqa: E402

CFG = HERE.parent / "config_3_3.json"
VARIANTS = ("background", "pit", "bump", "ramp", "flat_cut")
CHANNELS = ("lrm_25", "lrm_5", "slope", "tpi_05", "openness_pos", "openness_neg", "roughness_11")


# ----------------------------------------------------------------------------- channels
def channels_from_dem(dem, res: float = 0.5):
    """The seven model channels from a DEM (shared recompute path in _geo_xfer_lib)."""
    return xl.channels_from_dem(dem, res)


def influence_px(res: float = 0.5) -> int:
    """Largest channel support radius in cells plus a margin. Openness walks L = 25 m along the
    diagonals too, so the reach is 25 m x sqrt(2) (a dry run with 25 m alone left 0.12 deg diffs)."""
    return int(np.ceil(25.0 / res * np.sqrt(2))) + 8


# ----------------------------------------------------------------------------- edits
def fit_plane(z, mask_out):
    yy, xx = np.mgrid[0:z.shape[0], 0:z.shape[1]]
    m = mask_out & np.isfinite(z)
    A = np.c_[xx[m], yy[m], np.ones(m.sum())]
    coef, *_ = np.linalg.lstsq(A, z[m], rcond=None)
    return coef[0] * xx + coef[1] * yy + coef[2]


def feather_weight(mask, feather_px: int):
    from scipy.ndimage import distance_transform_edt
    d = distance_transform_edt(~mask)
    return np.clip(1.0 - d / max(feather_px, 1), 0, 1).astype(np.float32) * (d <= feather_px)


def donor_residual(z, rim_mask, feather_px):
    """Residual of a donor patch about a plane fitted outside the rim, and its weight."""
    plane = fit_plane(z, ~rim_mask)
    res = (z - plane).astype(np.float32)
    w = feather_weight(rim_mask, feather_px)
    res = np.where(np.isfinite(res), res, 0)
    amp = float(-np.nanmin(res[rim_mask])) if rim_mask.any() else 0.0
    return res, w, max(amp, 0.0)


def make_variants(target, donor_res, w, amp, rng):
    """All variants for one location. Donor arrays are centred in the target window."""
    H, W = target.shape
    h, wd = donor_res.shape
    r0, c0 = (H - h) // 2, (W - wd) // 2
    full_w = np.zeros_like(target, dtype=np.float32)
    full_r = np.zeros_like(target, dtype=np.float32)
    full_w[r0:r0 + h, c0:c0 + wd] = w
    full_r[r0:r0 + h, c0:c0 + wd] = donor_res
    foot = full_w >= 1.0
    yy, xx = np.mgrid[0:H, 0:W]
    cy, cx = (yy[foot].mean(), xx[foot].mean()) if foot.any() else (H / 2, W / 2)
    rr = np.hypot(yy - cy, xx - cx)
    R = max(float(rr[full_w > 0].max()) if (full_w > 0).any() else 1.0, 1.0)
    theta = rng.uniform(0, 2 * np.pi)
    u = (xx - cx) * np.cos(theta) + (yy - cy) * np.sin(theta)
    um = full_w > 0
    span = (u[um].max() - u[um].min()) if um.any() else 1.0
    ramp = (u - u[um].mean()) / max(span, 1e-6) if um.any() else 0 * u
    zmin = float(np.nanmin(target[foot])) if foot.any() else float(np.nanmin(target))
    out = {
        "background": target.copy(),
        "pit": target + full_w * full_r,
        "bump": target + amp * full_w * np.clip(1 - (rr / R) ** 2, 0, 1),
        "ramp": target + amp * full_w * ramp,
        "flat_cut": target * (1 - full_w) + full_w * zmin,
    }
    return {k: v.astype(np.float32) for k, v in out.items()}, foot, full_w > 0


def laplacian_var(z, m):
    from scipy.ndimage import laplace
    L = laplace(np.where(np.isfinite(z), z, np.nanmean(z)).astype(np.float64))
    return float(np.var(L[m])) if m.any() else np.nan


def seam_stats(variant, background, foot, touched, ring_px=10):
    """Interpolation-texture statistic. inside_outside: var(Laplacian) inside the footprint over
    the ring outside it (fw_3_3 S4 text). seam_band: edited over background in the feather band."""
    from scipy.ndimage import binary_dilation
    ring = binary_dilation(touched, iterations=ring_px) & ~touched
    band = touched & ~foot
    from scipy.ndimage import gaussian_filter
    vi, vo = laplacian_var(variant, foot), laplacian_var(variant, ring)
    sb_e, sb_b = laplacian_var(variant, band), laplacian_var(background, band)
    hp_v = variant - gaussian_filter(variant, 3)
    hp_b = background - gaussian_filter(background, 3)
    tv, tb = laplacian_var(hp_v, foot), laplacian_var(hp_b, foot)
    return {"lapvar_in": vi, "lapvar_ring": vo, "ratio_inside_outside": vi / vo if vo else np.nan,
            "ratio_seam_band": sb_e / sb_b if sb_b else np.nan,
            "ratio_highpass_texture": tv / tb if tb else np.nan}


def outside_diff(ch_a, ch_b, touched, res=0.5):
    """Max channel difference farther than influence_px (Euclidean) from every edited cell."""
    from scipy.ndimage import distance_transform_edt
    out = distance_transform_edt(~touched) > influence_px(res)
    if not out.any():
        return np.nan
    d = np.abs(np.nan_to_num(ch_a) - np.nan_to_num(ch_b))[:, out]
    return float(d.max())


# ----------------------------------------------------------------------------- inputs
def provisional_or_need(spec_entry, flag, what):
    p = xl.resolve_path(spec_entry["spec"])
    if p is not None and p.exists():
        return p, False
    if flag:
        return None, True
    raise xl.MissingInput(f"MISSING INPUT: {what}\n  expected at: {p}\n  schema: {spec_entry['schema']}\n"
                          f"  from: {spec_entry['from']}\n  (a provisional flag exists for a dry build)")


def pick_locations(n, rng, slope_win, tf1, cut_deg, excl_geom, audit_geom, bounds, margin_m, min_spacing,
                   include_geom=None):
    from rasterio.transform import rowcol
    from shapely.geometry import Point
    x0, y0, x1, y1 = bounds
    pts, tries = [], 0
    while len(pts) < n and tries < 200 * n:
        tries += 1
        x, y = rng.uniform(x0 + margin_m, x1 - margin_m), rng.uniform(y0 + margin_m, y1 - margin_m)
        r, c = rowcol(tf1, x, y)
        if not (0 <= r < slope_win.shape[0] and 0 <= c < slope_win.shape[1]):
            continue
        s = slope_win[r, c]
        if not np.isfinite(s) or s > cut_deg:
            continue
        p = Point(x, y)
        if excl_geom is not None and excl_geom.contains(p):
            continue
        if audit_geom is not None and audit_geom.contains(p):
            continue
        if include_geom is not None and not include_geom.contains(p):
            continue
        if any((x - a) ** 2 + (y - b) ** 2 < min_spacing ** 2 for a, b in pts):
            continue
        pts.append((x, y))
    return pts, tries


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--s1-run", default=None, help="3.3 S1 run folder (default newest)")
    ap.add_argument("--n", type=int, default=None, help="number of locations (default config)")
    ap.add_argument("--no-score", action="store_true", help="build edits and channels, no model")
    ap.add_argument("--allow-cv5", action="store_true", help="score with CV5 folds (provisional)")
    ap.add_argument("--provisional-buffer", action="store_true", help="use edit.fallback_buffer_m")
    ap.add_argument("--no-audit-list", action="store_true", help="proceed without the P2 audit list")
    ap.add_argument("--n-save", type=int, default=20, help="DEM windows saved for S4 renders")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    E, I, A = cfg["edit"], cfg["inputs"], cfg["assumed"]
    n = a.n or E["n_locations"]
    seed = ek.child_seed(cfg["master_seed"], 0, 3)
    rng = np.random.default_rng(seed)
    import geopandas as gpd
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import Window, from_bounds
    from _common import read_layer
    sys.path.insert(0, str(HERE.parent))
    from _slope_recall_tercile_9t import local_relief, nan_uniform, read_masked  # noqa: F401

    s1 = Path(a.s1_run) if a.s1_run else sorted(ek.sub("3.3", "results").glob("*_slope_recall_*"))[-1]
    s1s = json.loads(xl.need(s1 / "slope_recall_summary_9t.json", "3.3 S1 summary").read_text())
    cut_deg = s1s["cut_points"]["feature_slope_deg"][0]
    prop_thr = s1s.get("frozen_target_proposal_thr", cfg["proposal_thr"])

    buf_p, buf_prov = provisional_or_need(A["derived_buffer"], a.provisional_buffer, "P1 derived buffer")
    buffer_m = json.loads(buf_p.read_text())["pit_buffer_m"] if buf_p else E["fallback_buffer_m"]
    aud_p, aud_prov = provisional_or_need(A["audit_blocks"], a.no_audit_list, "P2 audit block list")
    blocks = gpd.read_file(xl.need(xl.resolve_path(I["blocks"]), "9t blocks"), layer="blocks")
    audit_geom = None
    if aud_p:
        ids = pd.read_csv(aud_p).block_id.astype(int)
        audit_geom = blocks[blocks.block_id.isin(ids)].geometry.union_all()

    gp = xl.need(xl.resolve_path(I["truth_gpkg"]), "annotations")
    floors = read_layer(gp, I["truth_floor_layer"]).to_crs(ek.DST_CRS)
    rims = read_layer(gp, I["truth_rim_layer"]).to_crs(ek.DST_CRS)
    pads = read_layer(gp, I["truth_pad_layer"]).to_crs(ek.DST_CRS)
    excl = pd.concat([floors.geometry, rims.geometry, pads.geometry]).buffer(buffer_m).union_all()
    rims_d = rims[["pit_inside_id", "geometry"]].dissolve(by="pit_inside_id").reset_index()
    donors = rims_d.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    slope, tf1 = read_masked(xl.resolve_path(I["slope_1m"]))
    s_win = nan_uniform(slope, cfg["slope_window_m"])
    dem_p = xl.need(xl.resolve_path(I["dem_05"]), "9t 0.5 m DEM")
    with rasterio.open(dem_p) as rd:
        ek.assert_crs(rd)
        res = rd.res[0]
        bounds = tuple(rd.bounds)
    margin = E["context_margin_m"]
    fa = pd.read_csv(xl.resolve_path(I["fold_assignment"])).dropna(subset=["block_id", "fold"])
    fold_of_block = fa.groupby("block_id").fold.first().astype(int).to_dict()
    # scored locations must sit in a block that has a held-out fold model
    include = None if a.no_score else blocks[blocks.block_id.isin(list(fold_of_block))].geometry.union_all()
    pts, tries = pick_locations(n, rng, s_win, tf1, cut_deg, excl, audit_geom, bounds, margin + 20, E["min_spacing_m"],
                                include_geom=include)
    print(f"{len(pts)} locations after {tries} draws (slope <= {cut_deg:.2f} deg, buffer {buffer_m} m"
          f"{' PROVISIONAL' if buf_prov else ''}, audit list {'MISSING (provisional)' if aud_prov else 'applied'})")

    models = {}
    if not a.no_score:
        iso = xl.resolve_path(A["isolated_pit_ckpt"]["spec"])
        use_iso = iso is not None and Path(str(iso).format(k=0)).exists()
        if not use_iso and not a.allow_cv5:
            raise xl.MissingInput(f"MISSING INPUT: P1 isolated pit checkpoints\n  expected at: {iso}\n"
                                  f"  schema: {A['isolated_pit_ckpt']['schema']}\n  pass --allow-cv5 for a provisional run")
        for k in range(cfg["n_folds"]):
            ck = Path(str(iso).format(k=k)) if use_iso else xl.resolve_path(
                {**I["fold_ckpt"], "rel": I["fold_ckpt"]["rel"].format(k=k)})
            models[k] = xl.load_ckpt(xl.need(ck, f"fold {k} checkpoint"), E["n_classes"])
            if tuple(models[k][3]) != CHANNELS:
                raise AssertionError(f"checkpoint channel order {models[k][3]} != {CHANNELS}")

    run = ek.new_run("3.3", "slope_edit", {**cfg, "n": n, "score": not a.no_score, "cv5": a.allow_cv5,
                                             "buffer_m": buffer_m, "buffer_provisional": buf_prov,
                                             "audit_provisional": aud_prov}, why="S3 paired terrain edits.")
    save_dir = ek.sub("3.3", "data/interim") / "slope_edit_windows_9t"
    save_dir.mkdir(parents=True, exist_ok=True)
    half = int(round(margin / res))
    loc_rows, score_rows = [], []
    with rasterio.open(dem_p) as rd:
        for li, (x, y) in enumerate(pts):
            d = donors.iloc[li % len(donors)]
            pad = E["donor_pad_m"]
            g = d.geometry
            wd = from_bounds(*g.buffer(pad).bounds, transform=rd.transform).round_offsets().round_lengths()
            zd = rd.read(1, window=wd, boundless=True, fill_value=np.nan).astype(np.float32)
            rim_mask = ~geometry_mask([g], zd.shape, rd.window_transform(wd))
            dres, dw, amp = donor_residual(zd, rim_mask, E["feather_px"])
            r, c = rd.index(x, y)
            size = 2 * half + max(dres.shape)
            win = Window(c - size // 2, r - size // 2, size, size)
            tz = rd.read(1, window=win, boundless=True, fill_value=np.nan).astype(np.float32)
            if rd.nodata is not None:
                tz[tz == rd.nodata] = np.nan
            if not np.isfinite(tz).all():
                tz = np.where(np.isfinite(tz), tz, np.nanmedian(tz))
            lrng = np.random.default_rng(ek.child_seed(seed, li, 0))
            var, foot, touched = make_variants(tz, dres, dw, amp, lrng)
            chans = {k: channels_from_dem(v, res) for k, v in var.items()}
            od = max(outside_diff(chans[k], chans["background"], touched, res) for k in VARIANTS[1:])
            ss = {k: seam_stats(var[k], var["background"], foot, touched) for k in ("pit", "bump", "ramp", "flat_cut")}
            bid = None
            hit = blocks[blocks.contains(gpd.points_from_xy([x], [y])[0])]
            if len(hit):
                bid = int(hit.block_id.iloc[0])
            row = {"loc_id": li, "x": x, "y": y, "block_id": bid, "donor_pit_inside_id": int(d.pit_inside_id),
                   "amp_m": amp, "footprint_m2": float(foot.sum() * res * res), "seed": ek.child_seed(seed, li, 0),
                   "max_outside_channel_diff": od, "outside_diff_ok": bool(od <= 1e-3)}
            for k, s in ss.items():
                row.update({f"{k}_{m}": v for m, v in s.items()})
            loc_rows.append(row)
            if li < a.n_save:
                np.savez_compressed(save_dir / f"loc{li:03d}.npz", **var, foot=foot, touched=touched)
            if a.no_score:
                continue
            fold = fold_of_block.get(bid)
            if fold is None:
                score_rows.append({"loc_id": li, "skipped": "block has no fold"})
                continue
            model, mu, sd, _, _ = models[fold]
            tfw = rd.window_transform(win)
            srow = {"loc_id": li, "fold": fold}
            win_km2 = size * size * res * res / 1e6
            k_win = int(round(cfg["k_per_km2"] * win_km2))
            for v in VARIANTS:
                p = xl.predict_array(model, chans[v], mu, sd, patch=E["patch"], overlap=E["overlap"],
                                     n_classes=E["n_classes"])[E["floor_class"]]
                srow[f"score_{v}"] = float(p[foot].max())
                cands = xl.candidates_from_prob(p, tfw, ek.DST_CRS, thr=prop_thr, min_area=cfg["min_blob_m2"])
                fp_geom = gpd.GeoSeries.from_xy([x], [y], crs=ek.DST_CRS).buffer(np.sqrt(foot.sum() * res * res / np.pi)).iloc[0]
                rank = np.nan
                if len(cands):
                    cands = cands.sort_values(["score", "area_m2"], ascending=[False, False]).reset_index(drop=True)
                    over = cands.index[cands.intersects(fp_geom)]
                    if len(over):
                        rank = int(over.min()) + 1
                srow[f"rank_{v}"] = rank
                srow[f"det_{v}"] = bool(np.isfinite(rank) and rank <= k_win)
            score_rows.append(srow)
            print(f"  loc {li}: fold {fold} " + " ".join(f"{v}={srow[f'score_{v}']:.2f}" for v in VARIANTS))

    locs = pd.DataFrame(loc_rows)
    lcsv = run / "slope_edit_locations_9t.csv"
    locs.to_csv(lcsv, index=False)
    outs = [lcsv]
    summ = {"n_locations": len(locs), "slope_cut_deg": cut_deg, "buffer_m": buffer_m, "buffer_provisional": buf_prov,
            "audit_provisional": aud_prov, "outside_diff_fail": int((~locs.outside_diff_ok).sum()) if len(locs) else 0,
            "model": "none" if a.no_score else ("cv5 PROVISIONAL" if a.allow_cv5 else "P1 isolated")}
    if score_rows:
        sc = pd.DataFrame(score_rows)
        scsv = run / "slope_edit_paired_scores_9t.csv"
        sc.to_csv(scsv, index=False)
        outs.append(scsv)
        sc = sc.dropna(subset=["score_pit"]) if "score_pit" in sc else sc.iloc[0:0]
        idx = list(range(len(sc)))
        for v in ("background", "bump", "ramp", "flat_cut"):
            if not len(sc):
                break
            dd = (sc.score_pit - sc[f"score_{v}"]).to_numpy()
            p, lo, hi, _ = ek.block_bootstrap(lambda b, dd=dd: float(np.median(dd[b])), idx,
                                              B=cfg["bootstrap_B"], seed=seed)
            summ[f"median_score_pit_minus_{v}"] = {"median": p, "lo": lo, "hi": hi}
        if len(sc):
            summ["detect_rate_at_k"] = {v: float(sc[f"det_{v}"].mean()) for v in VARIANTS}
    js = run / "slope_edit_paired_summary_9t.json"
    js.write_text(json.dumps(summ, indent=2, default=float), encoding="utf-8")
    outs.append(js)
    ek.write_provenance(run, inputs=[dem_p, gp, s1 / "slope_recall_summary_9t.json"], outputs=outs,
                        params={"n": n, "buffer_m": buffer_m}, seeds={"edit": seed})
    print(json.dumps(summ, indent=2, default=float))
    print(f"outputs in {run}\nDEM windows in {save_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
