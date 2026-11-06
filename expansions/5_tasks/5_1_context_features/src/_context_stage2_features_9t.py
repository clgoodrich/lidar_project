"""5.1 S4. Stage-2 context features per pit candidate, built from out-of-fold maps (tile 9t).

Purpose
    Build the candidate table the stage-2 learner reads. Candidates come from the pit out-of-fold raster
    (fw_00 section 4). Threshold at the lowest sweep cutoff (0.10), connected blobs (4-connectivity), drop blobs
    under 4 m2, score = mean probability. Each candidate is matched to annotated floors (pit_inside) greedily by
    IoU >= 0.3, one to one. A second blob on a matched floor is a duplicate, not a detection.
    The coordinate-free sweep object table (cv5_sweep_objects_pit_*.csv.gz) cannot place candidates, so it is
    not used. Candidates are re-extracted from the raster instead (decision logged in docs/decisions_5_1.md).

    Features per (outer fold k, candidate). Each is read from the upstream model allowed for that row
    (stacking_mode in config).
        stage1          mean pit probability inside the blob (upstream pit model)
        road_dist_m     distance from centroid to the nearest road pixel with prob > 0.5, capped at road_search_m
        pad_mean_25m, pad_mean_50m, pad_mean_100m   mean pad probability in a disc
        n_pit_50m, n_pit_100m   other candidates with centroid within r
        slope           mean of the frozen stack's slope band in a 5 m disc (not a model output)
        area_m2         blob area
    Every raster read is logged in a usage file (outer fold, block fold, role, raster path). S6 audits it.

Inputs (config_5_1.json)
    upstream_rasters.<role>.<mode>  pit, pad, road probability rasters. nested and outer are ASSUMED (S3, GPU).
                                    provisional = data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif,
                                    data/9t/models/pad/unet_cv5_iso/fold{k}/pad_prob_cvfold{k}_9t_05.tif,
                                    data/9t/models/road/unet_1m_recall_relabeled20260806/road_prob.tif (in-sample)
    inputs.shared_folds (or the provisional file), inputs.pit_blocks, inputs.pad_assign, inputs.annotations,
    inputs.features (band 'slope')
Outputs
    outputs.stage2_features        -> expansions/5_tasks/5_1_context_features/data/processed/stage2_features_9t.parquet
    outputs.stage2_usage           -> .../data/processed/stage2_upstream_usage_9t.json
    outputs.stage2_candidates_gpkg -> .../data/interim/stage2_candidates_9t.gpkg (candidate polygons, for renders)
Run
    python expansions/5_tasks/5_1_context_features/src/_context_stage2_features_9t.py               (stacking_mode from config)
    python expansions/5_tasks/5_1_context_features/src/_context_stage2_features_9t.py --mode provisional
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

ek = th.ek


def repo_rel(p) -> str:
    """Repo-relative POSIX path for outputs. Never an absolute path."""
    p = Path(p)
    try:
        return p.resolve().relative_to(ek.REPO.resolve()).as_posix()
    except ValueError:
        return p.name
FEATURES = ["stage1", "road_dist_m", "pad_mean_25m", "pad_mean_50m", "pad_mean_100m",
            "n_pit_50m", "n_pit_100m", "slope", "area_m2"]


# ----------------------------------------------------------------------------- candidates
def to_prob(a: np.ndarray, dn_scale: float = 254.0, nodata_dn: int = 255, nodata=None) -> np.ndarray:
    """uint8 DN/254 (255 nodata) or float with nodata -> float32 probability with NaN."""
    if a.dtype == np.uint8:
        p = a.astype(np.float32) / dn_scale
        p[a == nodata_dn] = np.nan
        return p
    p = a.astype(np.float32)
    if nodata is not None:
        p[a == nodata] = np.nan
    p[(p < 0) | (p > 1)] = np.nan
    return p


def extract_candidates(prob: np.ndarray, transform, cutoff: float = 0.10, min_area_m2: float = 4.0, crs=th.CRS):
    """Connected blobs of prob >= cutoff, area >= min_area, score = mean prob. GeoDataFrame in project CRS."""
    import geopandas as gpd
    from rasterio.features import shapes
    from shapely.geometry import shape
    from shapely.ops import unary_union
    res = abs(transform.a)
    fg = np.nan_to_num(prob, nan=0.0) >= cutoff
    lab, n = ndi.label(fg)
    if n == 0:
        return gpd.GeoDataFrame({"cand_id": [], "score": [], "area_m2": []}, geometry=[], crs=crs)
    idx = np.arange(1, n + 1)
    npx = ndi.sum(fg, lab, idx)
    keep = idx[npx * res * res >= min_area_m2]
    mean = dict(zip(idx, ndi.mean(np.nan_to_num(prob), lab, idx)))
    lab = np.where(np.isin(lab, keep), lab, 0).astype(np.int32)
    parts: dict[int, list] = {}
    for geom, v in shapes(lab, mask=lab > 0, transform=transform):
        parts.setdefault(int(v), []).append(shape(geom))
    ids = sorted(parts)
    geoms = [unary_union(parts[i]) for i in ids]
    g = gpd.GeoDataFrame({"blob": ids, "score": [float(mean[i]) for i in ids]}, geometry=geoms, crs=crs)
    g["area_m2"] = g.geometry.area
    g["cx"], g["cy"] = g.geometry.centroid.x, g.geometry.centroid.y
    g = g.sort_values(["score", "area_m2", "blob"], ascending=[False, False, True]).reset_index(drop=True)
    g["cand_id"] = np.arange(len(g))
    return g


def greedy_iou_match(cands, truth, iou_thr: float = 0.30, truth_id: str = "truth_id"):
    """fw_00 matching. Pairs with IoU >= thr, greedy by IoU, one to one. Returns (matched_truth, is_dup) arrays.
    is_dup marks an unmatched blob whose centroid sits on an already matched floor."""
    n = len(cands)
    mt = np.full(n, None, dtype=object)
    dup = np.zeros(n, bool)
    if n == 0 or len(truth) == 0:
        return mt, dup
    pairs = []
    sidx = truth.sindex
    for i, g in enumerate(cands.geometry):
        for j in sidx.intersection(g.bounds):
            t = truth.geometry.iloc[j]
            inter = g.intersection(t).area
            if inter <= 0:
                continue
            iou = inter / (g.area + t.area - inter)
            if iou >= iou_thr:
                pairs.append((iou, i, j))
    used_c, used_t = set(), set()
    for iou, i, j in sorted(pairs, key=lambda p: (-p[0], p[1], p[2])):
        if i in used_c or j in used_t:
            continue
        used_c.add(i)
        used_t.add(j)
        mt[i] = truth[truth_id].iloc[j]
    if used_t:
        matched_union = truth.iloc[sorted(used_t)].geometry.union_all()
        cen = cands.geometry.centroid
        for i in range(n):
            if mt[i] is None and cen.iloc[i].within(matched_union):
                dup[i] = True
    return mt, dup


# ----------------------------------------------------------------------------- raster sampling
def read_padded(ds, band: int, row0: int, col0: int, h: int, w: int, fill):
    """Read a window that may run off the raster, padding with fill. Avoids rasterio boundless reads (slow VRT)."""
    from rasterio.windows import Window
    out = np.full((h, w), fill, dtype=ds.dtypes[band - 1])
    r0, c0 = max(row0, 0), max(col0, 0)
    r1, c1 = min(row0 + h, ds.height), min(col0 + w, ds.width)
    if r1 > r0 and c1 > c0:
        out[r0 - row0:r1 - row0, c0 - col0:c1 - col0] = ds.read(band, window=Window(c0, r0, c1 - c0, r1 - r0))
    return out


def _disc(res: float, r: float):
    h = int(np.ceil(r / res))
    yy, xx = np.mgrid[-h:h + 1, -h:h + 1]
    d = np.hypot(xx, yy) * res
    return h, d, d <= r


def disc_stats(ds, xy: np.ndarray, r: float, stat: str = "mean", thr: float | None = None,
               dn_scale: float = 254.0, nodata_dn: int = 255, cap: float | None = None, band: int = 1) -> np.ndarray:
    """Per point, a statistic of the raster in a disc of radius r (fixed pixel stencil, one read per point).
    stat mean -> NaN-aware mean of probability. raw -> mean of raw values. mindist -> distance to the nearest
    pixel > thr (cap when none)."""
    res = abs(ds.transform.a)
    h, d, inside = _disc(res, r)
    out = np.full(len(xy), np.nan)
    fill = ds.nodata if ds.nodata is not None else 0
    for i, (x, y) in enumerate(xy):
        row, col = ds.index(x, y)
        a = read_padded(ds, band, row - h, col - h, 2 * h + 1, 2 * h + 1, fill)
        if stat == "raw":
            p = a.astype(np.float32)
            if ds.nodata is not None:
                p[a == ds.nodata] = np.nan
        else:
            p = to_prob(a, dn_scale, nodata_dn, ds.nodata)
        if stat in ("mean", "raw"):
            v = p[inside & np.isfinite(p)]
            out[i] = float(v.mean()) if v.size else np.nan
        elif stat == "mindist":
            hit = inside & (np.nan_to_num(p) > thr)
            out[i] = float(d[hit].min()) if hit.any() else (cap if cap is not None else r)
        else:
            raise ValueError(stat)
    return out


def polygon_mean(ds, geoms, dn_scale=254.0, nodata_dn=255) -> np.ndarray:
    """Mean probability inside each polygon (stage-1 score from a given upstream raster)."""
    from affine import Affine
    from rasterio.features import geometry_mask
    out = np.full(len(geoms), np.nan)
    fill = ds.nodata if ds.nodata is not None else 0
    for i, g in enumerate(geoms):
        x0, y0, x1, y1 = g.bounds
        r0, c0 = ds.index(x0, y1)
        r1, c1 = ds.index(x1, y0)
        h, w = r1 - r0 + 1, c1 - c0 + 1
        a = to_prob(read_padded(ds, 1, r0, c0, h, w, fill), dn_scale, nodata_dn, ds.nodata)
        tf = ds.transform * Affine.translation(c0, r0)
        m = ~geometry_mask([g], out_shape=a.shape, transform=tf, all_touched=True)
        v = a[m & np.isfinite(a)]
        out[i] = float(v.mean()) if v.size else np.nan
    return out


def neighbour_counts(xy: np.ndarray, radii) -> dict:
    t = cKDTree(xy)
    return {r: np.array([len(t.query_ball_point(p, r)) - 1 for p in xy]) for r in radii}


# ----------------------------------------------------------------------------- upstream choice
def raster_for(cfg: dict, role: str, mode: str, k: int, block_fold: int, pad_fold: int | None = None) -> tuple[Path, str]:
    """Which upstream raster a row may read. Returns (path, kind)."""
    pats = cfg["upstream_rasters"][role]
    if mode == "provisional":
        kk = pad_fold if (role == "pad" and pad_fold is not None) else 0
        return th.resolve(pats["provisional"].format(k=kk)), "historical"
    if mode == "outer" or block_fold == k:
        return th.resolve(pats["outer"].format(k=k)), f"outer{k}"
    if mode == "nested":
        return th.resolve(pats["nested"].format(k=k, j=block_fold)), f"outer{k}_inner{block_fold}"
    raise ValueError(mode)


def build_features(cfg: dict, cands, block_fold: np.ndarray, pad_fold: np.ndarray, mode: str):
    """Long table. One row per (outer fold, candidate). Also returns the usage log."""
    import rasterio
    k_n = int(cfg["n_folds"])
    s2, cand = cfg["stage2"], cfg["candidate"]
    xy = np.c_[cands["cx"].to_numpy(), cands["cy"].to_numpy()]
    block_id = cands["block_id"].to_numpy()
    nb = neighbour_counts(xy, s2["pit_radii_m"])
    with rasterio.open(th.inp(cfg, "features")) as fs:
        names = list(fs.descriptions)
        band = names.index("slope") + 1 if "slope" in names else 3
        slope = disc_stats(fs, xy, s2["slope_radius_m"], "raw", band=band)
    rows, usage = [], []
    for k in range(k_n):
        feats = pd.DataFrame({"outer_fold": k, "cand_id": cands.cand_id.to_numpy(), "block_fold": block_fold})
        for c in ("stage1", "road_dist_m", *[f"pad_mean_{r}m" for r in s2["pad_radii_m"]]):
            feats[c] = np.nan
        groups = pd.DataFrame({"bf": block_fold, "pf": pad_fold}).groupby(["bf", "pf"], dropna=False).indices
        for (bf, pf), ii in groups.items():
            ii = np.asarray(ii)
            pfi = None if pd.isna(pf) else int(pf)
            for role in ("pit", "pad", "road"):
                p, kind = raster_for(cfg, role, mode, k, int(bf), pfi)
                if not p.exists():
                    raise th.MissingInput(f"upstream_rasters.{role}.{mode}", p, cfg["upstream_rasters"]["note"])
                usage.append(dict(outer_fold=k, block_fold=int(bf), pad_fold=pfi, role=role, raster=repo_rel(p), kind=kind,
                                  n_rows=int(len(ii)), blocks=sorted({int(b) for b in block_id[ii]})))
                with rasterio.open(p) as ds:
                    ek.assert_crs(ds)
                    if role == "pit":
                        feats.loc[ii, "stage1"] = polygon_mean(ds, cands.geometry.iloc[ii].to_list(),
                                                               cand["prob_dn_scale"], cand["prob_nodata_dn"])
                    elif role == "pad":
                        for r in s2["pad_radii_m"]:
                            feats.loc[ii, f"pad_mean_{r}m"] = disc_stats(ds, xy[ii], r, "mean")
                    else:
                        feats.loc[ii, "road_dist_m"] = disc_stats(ds, xy[ii], s2["road_search_m"], "mindist",
                                                                  thr=s2["road_thr"], cap=s2["road_search_m"])
        for r in s2["pit_radii_m"]:
            feats[f"n_pit_{r}m"] = nb[r]
        feats["slope"] = slope
        feats["area_m2"] = cands.area_m2.to_numpy()
        rows.append(feats)
        if mode == "provisional":   # historical rasters do not depend on k, so one pass is the same for all
            for kk in range(1, k_n):
                rows.append(feats.assign(outer_fold=kk))
                usage += [dict(u, outer_fold=kk) for u in usage if u["outer_fold"] == 0]
            break
    return pd.concat(rows, ignore_index=True), usage


def main(argv=None) -> int:
    import geopandas as gpd
    import rasterio
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--mode", choices=("nested", "outer", "provisional"))
    ap.add_argument("--max-cands", type=int, default=0, help="keep the top N candidates by score (pilot only)")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    mode = a.mode or cfg["stacking_mode"]
    cand = cfg["candidate"]

    sf_path = th.outp(cfg, "shared_folds_provisional") if mode == "provisional" else th.inp(cfg, "shared_folds")
    if not sf_path.exists():
        raise th.MissingInput("shared_folds", sf_path, "run _context_shared_folds_9t.py")
    sf = json.loads(sf_path.read_text())
    b2f = {int(b): int(f) for b, f in sf["block_to_fold"].items()}

    # candidates and their extraction raster. Provisional uses the historical OOF mosaic. Nested and outer use the
    # shared-scheme pit OOF mosaic (each block from the model that excluded its fold), built after S3.
    pit_src = (th.resolve(cfg["upstream_rasters"]["pit"]["provisional"]) if mode == "provisional"
               else th.inp(cfg, "shared_pit_oof"))
    with rasterio.open(pit_src) as ds:
        ek.assert_crs(ds)
        prob = to_prob(ds.read(1), cand["prob_dn_scale"], cand["prob_nodata_dn"], ds.nodata)
        cands = extract_candidates(prob, ds.transform, cand["cutoff"], cand["min_area_m2"])
    del prob
    blocks = th.read_vector(th.inp(cfg, "pit_blocks"), layer="blocks")
    xy = np.c_[cands["cx"].to_numpy(), cands["cy"].to_numpy()]
    cands["block_id"] = th.block_id_of(xy, blocks)
    cands = cands[cands.block_id.isin(list(b2f))].reset_index(drop=True)
    if a.max_cands:
        cands = cands.head(a.max_cands).reset_index(drop=True)
    truth = th.read_vector(th.inp(cfg, "annotations"), layer="pit_inside")
    truth = truth.explode(index_parts=False).dissolve(by="pit_inside_id").reset_index()
    truth["truth_id"] = truth["pit_inside_id"].astype(int)
    mt, dup = greedy_iou_match(cands, truth, cand["match_iou"])
    cands["matched_truth"], cands["is_dup"] = mt, dup
    cands["y"] = pd.notna(cands.matched_truth).astype(int)
    pad_assign = pd.read_csv(th.inp(cfg, "pad_assign")).dropna(subset=["block_id", "fold"])
    pad_map = dict(pad_assign.drop_duplicates("block_id")[["block_id", "fold"]].astype(int).itertuples(index=False, name=None))
    bf = cands.block_id.map(b2f).to_numpy().astype(int)
    pf = cands.block_id.map(pad_map).to_numpy()
    feats, usage = build_features(cfg, cands, bf, pf, mode)
    base = cands[["cand_id", "block_id", "score", "area_m2", "cx", "cy", "matched_truth", "is_dup", "y"]].copy()
    base["matched_truth"] = base.matched_truth.astype("object").where(base.matched_truth.notna(), None)
    table = feats.drop(columns=["area_m2"]).merge(base, on="cand_id", how="left", validate="many_to_one")
    ek.assert_rows(table, len(cands) * int(cfg["n_folds"]), "one row per outer fold and candidate")
    table["matched_truth"] = table.matched_truth.astype(str).replace("None", "")
    table["mode"] = mode
    table["evidence_level"] = "a"
    # truth per block (complete blocks, including those with no candidate)
    tc = truth.geometry.centroid
    truth["block_id"] = th.block_id_of(np.c_[tc.x, tc.y], blocks)
    n_truth = truth[truth.block_id.isin(list(b2f))].groupby("block_id").size()
    out = th.outp(cfg, "stage2_features")
    table.to_parquet(out, index=False)
    gp = th.outp(cfg, "stage2_candidates_gpkg")
    cands.assign(matched_truth=cands.matched_truth.astype(str)).to_file(gp, layer="candidates", driver="GPKG")
    th.write_json(th.outp(cfg, "stage2_usage"), dict(mode=mode, shared_folds=repo_rel(sf_path), provisional=sf.get("provisional"),
                                                     n_candidates=len(cands), n_truth_by_block={str(b): int(n_truth.get(b, 0)) for b in sorted(b2f)},
                                                     block_to_fold=sf["block_to_fold"], usage=usage))
    print(f"{len(cands)} candidates, {int(cands.y.sum())} matched, {int(cands.is_dup.sum())} duplicates, "
          f"{int(n_truth.sum())} floors in footprint")
    print(f"wrote {out}\nwrote {gp}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except th.MissingInput as e:
        print(e.args[0], file=sys.stderr)
        sys.exit(2)
