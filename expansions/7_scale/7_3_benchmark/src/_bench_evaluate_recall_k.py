"""Official scorer of the terrain-feature benchmark (7.3 S2). Shipped in the release as evaluate.py.

Purpose
    Score probability rasters against drawn feature polygons with the shared rules of
    expansions/_shared/fw_00_common.md section 4.
    1. Threshold at the proposal cutoff (0.10), connected blobs (8-neighbour), drop blobs under 4 m2.
    2. Score each blob by its mean probability.
    3. Greedy one-to-one match by IoU >= 0.3. A second blob inside a matched feature is a duplicate.
    4. Rank every candidate in the scored footprint. Keep the top K per km2 (K = 40).
       Ties break by larger area, then by candidate id.
    5. Recall = matched truth features / all truth features in the footprint (complete blocks).
    6. Block-bootstrap 95% interval (B = 2000) and calibration (Brier, log loss, ECE).
    Deterministic. Same inputs give byte-identical JSON.

    The file is self-contained on purpose. A fresh checkout of the release has no repo and no
    expkit, so this module depends only on numpy, scipy, pandas, rasterio, shapely and geopandas.
    test_7_3.py asserts that its recall equals expkit.recall_at_k on the same candidates.

Inputs
    --pred      one or more prediction specs "path[:block_id,block_id,...]". A float probability raster
                in metres. Values below 0 or equal to nodata are invalid. With --dn-scale 254 a uint8
                mosaic is read as DN / 254 and 255 is nodata (protocol section 2 rule 2).
                Block ids after the colon restrict that raster to those blocks (out-of-fold use).
    --labels    GeoPackage of drawn features (layer --layer). Any CRS, reprojected to the blocks CRS.
    --blocks    GeoPackage of complete scored blocks with an integer column block_id.
Outputs
    --out             JSON summary (recall, interval, k, hits, n_truth, area, density, calibration).
    --blocks-out      optional CSV, one row per scored block (block_id, n_truth, area_km2).
    --candidates-out  optional CSV, one row per candidate (cand_id, block_id, score, area_m2, matched_truth,
                      is_dup, cx, cy). The validity and leaderboard scripts read this file.

Run
    python expansions/7_scale/7_3_benchmark/src/_bench_evaluate_recall_k.py \
        --pred pred.tif --labels labels_devtest.gpkg --layer pit_inside --blocks blocks_devtest.gpkg \
        --out score.json --candidates-out cands.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCORER_VERSION = "terrain_v1_scorer_1.0"
DEFAULTS = dict(thr=0.10, min_area_m2=4.0, iou_thr=0.3, k_per_km2=40.0, B=2000, seed=0, alpha=0.05)


# ----------------------------------------------------------------------------- candidates
def extract_candidates(prob: np.ndarray, transform, *, thr: float = DEFAULTS["thr"],
                       min_area_m2: float = DEFAULTS["min_area_m2"], valid: np.ndarray | None = None,
                       crs=None, id_prefix: str = "c"):
    """Probability array -> GeoDataFrame of blobs (geometry, score, area_m2, cand_id).

    score is the mean probability over the blob's pixels. 8-connectivity. Deterministic order
    (label order of scipy.ndimage.label, which scans row-major).
    """
    import geopandas as gpd
    from rasterio.features import shapes
    from scipy import ndimage as ndi
    from shapely.geometry import shape
    from shapely.ops import unary_union

    prob = np.asarray(prob, dtype=np.float64)
    ok = np.isfinite(prob) & (prob >= 0)
    if valid is not None:
        ok &= valid.astype(bool)
    fg = ok & (prob >= thr)
    lab, n = ndi.label(fg, structure=np.ones((3, 3), int))
    px_area = abs(transform.a * transform.e)
    cols = {"cand_id": [], "score": [], "area_m2": [], "geometry": []}
    if n == 0:
        return gpd.GeoDataFrame(cols, geometry="geometry", crs=crs)
    idx = np.arange(1, n + 1)
    counts = ndi.sum(np.ones_like(prob), lab, idx)
    means = ndi.mean(np.where(fg, prob, 0.0), lab, idx)
    keep = counts * px_area >= min_area_m2
    lab32 = lab.astype(np.int32)
    geoms: dict[int, list] = {}
    for g, v in shapes(lab32, mask=lab32 > 0, transform=transform, connectivity=8):
        v = int(v)
        if keep[v - 1]:
            geoms.setdefault(v, []).append(shape(g))
    for v in sorted(geoms):
        cols["cand_id"].append(f"{id_prefix}{v:07d}")
        cols["score"].append(float(means[v - 1]))
        cols["area_m2"].append(float(counts[v - 1] * px_area))
        parts = geoms[v]
        cols["geometry"].append(parts[0] if len(parts) == 1 else unary_union(parts))
    return gpd.GeoDataFrame(cols, geometry="geometry", crs=crs)


def read_prob(path: Path, dn_scale: float | None = None):
    """Read band 1. Returns (prob float64 with NaN for invalid, transform, crs)."""
    import rasterio
    with rasterio.open(path) as r:
        a = r.read(1).astype(np.float64)
        nod = r.nodata
        tf, crs = r.transform, r.crs
    if dn_scale:
        bad = a == 255 if nod is None else (a == nod) | (a == 255)
        a = a / dn_scale
        a[bad] = np.nan
    elif nod is not None and np.isfinite(nod):
        a[a == nod] = np.nan
    a[a < 0] = np.nan
    return a, tf, crs


# ----------------------------------------------------------------------------- matching
def match_greedy_iou(cands, truth, iou_thr: float = DEFAULTS["iou_thr"], truth_id_col: str = "truth_id"):
    """One-to-one greedy IoU match. Returns (matched_truth list, is_dup bool array).

    Pairs are sorted by IoU descending, then candidate id, then truth id. A candidate whose
    centroid falls inside an already-matched truth feature, and which is itself unmatched,
    is a duplicate (fw_00 section 4).
    """
    n = len(cands)
    matched = [None] * n
    dup = np.zeros(n, bool)
    if n == 0 or len(truth) == 0:
        return matched, dup
    tids = truth[truth_id_col].tolist()
    tgeom = truth.geometry.values
    sidx = truth.sindex
    pairs = []
    cgeom = cands.geometry.values
    cid = cands["cand_id"].tolist()
    for i, g in enumerate(cgeom):
        for j in sidx.query(g, predicate="intersects"):
            inter = g.intersection(tgeom[j]).area
            if inter <= 0:
                continue
            iou = inter / (g.area + tgeom[j].area - inter)
            if iou >= iou_thr:
                pairs.append((-iou, cid[i], str(tids[j]), i, j))
    pairs.sort()
    used_c, used_t = set(), set()
    for _, _, _, i, j in pairs:
        if i in used_c or j in used_t:
            continue
        used_c.add(i); used_t.add(j)
        matched[i] = tids[j]
    if used_t:
        mt = truth.iloc[sorted(used_t)]
        cent = cands.geometry.centroid
        for i in range(n):
            if matched[i] is None and mt.contains(cent.iloc[i]).any():
                dup[i] = True
    return matched, dup


def assign_block(geoms, blocks, block_col: str = "block_id"):
    """Block id of the block holding each geometry's centroid (NaN if none)."""
    import geopandas as gpd
    cent = gpd.GeoDataFrame(geometry=geoms.centroid.values, crs=blocks.crs)
    j = gpd.sjoin(cent, blocks[[block_col, "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    return j[block_col].to_numpy()


# ----------------------------------------------------------------------------- recall at K
def recall_at_k_table(cand: pd.DataFrame, n_truth: int, area_km2: float, k_per_km2: float):
    """cand has score, area_m2, cand_id, matched_truth. Ties: score desc, area desc, id asc."""
    k = int(round(k_per_km2 * area_km2))
    if len(cand):
        order = cand.sort_values(["score", "area_m2", "cand_id"], ascending=[False, False, True])
        hits = int(order.head(k)["matched_truth"].dropna().nunique())
    else:
        hits = 0
    return {"recall": hits / n_truth if n_truth else float("nan"), "k": k, "hits": hits, "n_truth": int(n_truth)}


def block_tables(cand: pd.DataFrame, truth_blocks: pd.Series, block_ids, block_area_km2: dict):
    """Per-block payload for the bootstrap: (candidate rows, n truth, area)."""
    out = []
    tb = truth_blocks.value_counts()
    for b in block_ids:
        c = cand[cand["block_id"] == b][["score", "area_m2", "cand_id", "matched_truth"]]
        out.append((c, int(tb.get(b, 0)), float(block_area_km2[b])))
    return out


def pooled_recall(blocks_payload, k_per_km2: float) -> float:
    """Pool a list of block payloads (replicates allowed) and compute recall at K."""
    parts, n_truth, area = [], 0, 0.0
    for r, (c, nt, a) in enumerate(blocks_payload):
        if len(c):
            c = c.copy()
            c["matched_truth"] = [None if m is None or (isinstance(m, float) and np.isnan(m)) else f"{r}|{m}"
                                  for m in c["matched_truth"]]
            c["cand_id"] = f"{r}|" + c["cand_id"].astype(str)
            parts.append(c)
        n_truth += nt; area += a
    cand = pd.concat(parts) if parts else pd.DataFrame(columns=["score", "area_m2", "cand_id", "matched_truth"])
    return recall_at_k_table(cand, n_truth, area, k_per_km2)["recall"]


def bootstrap_blocks(payload, k_per_km2, B, seed, alpha):
    rng = np.random.default_rng(seed)
    n = len(payload)
    draws = np.array([pooled_recall([payload[j] for j in rng.integers(0, n, n)], k_per_km2) for _ in range(B)])
    lo, hi = np.nanpercentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def calibration(y, p, bins: int = 10):
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-7, 1 - 1e-7)
    if len(y) == 0:
        return {"brier": float("nan"), "log_loss": float("nan"), "ece": float("nan")}
    order = np.argsort(p, kind="stable")
    ece = sum(len(ix) / len(p) * abs(y[ix].mean() - p[ix].mean()) for ix in np.array_split(order, bins) if len(ix))
    return {"brier": float(np.mean((p - y) ** 2)),
            "log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))), "ece": float(ece)}


# ----------------------------------------------------------------------------- top level
def evaluate(pred_specs, truth, blocks, *, thr=DEFAULTS["thr"], min_area_m2=DEFAULTS["min_area_m2"],
             iou_thr=DEFAULTS["iou_thr"], k_per_km2=DEFAULTS["k_per_km2"], B=DEFAULTS["B"],
             seed=DEFAULTS["seed"], alpha=DEFAULTS["alpha"], dn_scale=None, block_col="block_id",
             keep_geometry=False):
    """pred_specs: list of (path_or_(prob, transform), block_ids or None). Returns (summary, cand_df).

    keep_geometry=True returns cand_df as a GeoDataFrame with the blob polygons (review packages).
    """
    import geopandas as gpd
    blocks = blocks.copy()
    blocks[block_col] = blocks[block_col].astype(int)
    if blocks[block_col].duplicated().any():
        raise AssertionError("duplicate block_id in the scored footprint")
    truth = truth.to_crs(blocks.crs).reset_index(drop=True)
    if "truth_id" not in truth.columns:
        truth["truth_id"] = [f"t{i:06d}" for i in range(len(truth))]
    truth["block_id"] = assign_block(truth.geometry, blocks, block_col)
    truth = truth[pd.notna(truth["block_id"])].copy()
    truth["block_id"] = truth["block_id"].astype(int)

    all_c = []
    for si, (src, bids) in enumerate(pred_specs):
        if isinstance(src, (str, Path)):
            prob, tf, crs = read_prob(Path(src), dn_scale)
            from pyproj import CRS
            if crs is None or CRS.from_user_input(crs.to_wkt()) != CRS.from_user_input(blocks.crs):
                raise AssertionError(f"CRS of {src} ({crs}) != blocks CRS ({blocks.crs})")
        else:
            prob, tf = src
        c = extract_candidates(prob, tf, thr=thr, min_area_m2=min_area_m2, crs=blocks.crs, id_prefix=f"s{si}_")
        c["block_id"] = assign_block(c.geometry, blocks, block_col) if len(c) else []
        c = c[pd.notna(c["block_id"])].copy()
        c["block_id"] = c["block_id"].astype(int)
        if bids is not None:
            c = c[c["block_id"].isin(set(int(b) for b in bids))]
        all_c.append(c)
    cand = pd.concat(all_c, ignore_index=True) if all_c else gpd.GeoDataFrame()
    cand = gpd.GeoDataFrame(cand, geometry="geometry", crs=blocks.crs)
    if cand["cand_id"].duplicated().any():
        raise AssertionError("duplicate candidate ids")
    if any(b is None for _, b in pred_specs):
        scored = sorted(set(int(x) for x in blocks[block_col]))
    else:
        scored = sorted(set().union(*[set(int(x) for x in b) for _, b in pred_specs]))
    missing = set(scored) - set(int(x) for x in blocks[block_col])
    if missing:
        raise AssertionError(f"pred spec names blocks absent from the footprint: {sorted(missing)[:5]}")
    truth = truth[truth["block_id"].isin(scored)]
    cand = cand[cand["block_id"].isin(scored)].reset_index(drop=True)
    matched, dup = match_greedy_iou(cand, truth, iou_thr)
    cand["matched_truth"] = matched
    cand["is_dup"] = dup
    area_km2 = {int(b): float(g.area) / 1e6 for b, g in zip(blocks[block_col], blocks.geometry)}
    tot_area = sum(area_km2[b] for b in scored)
    res = recall_at_k_table(cand, len(truth), tot_area, k_per_km2)
    payload = block_tables(cand, truth["block_id"], scored, area_km2)
    lo, hi = bootstrap_blocks(payload, k_per_km2, B, seed, alpha) if B else (float("nan"), float("nan"))
    cal = calibration(pd.notna(cand["matched_truth"]).to_numpy(), cand["score"].to_numpy())
    summary = {
        "scorer_version": SCORER_VERSION, "params": dict(thr=thr, min_area_m2=min_area_m2, iou_thr=iou_thr,
                                                         k_per_km2=k_per_km2, B=B, seed=seed, alpha=alpha),
        "n_blocks": len(scored), "area_km2": round(tot_area, 10),
        "truth_density_per_km2": round(len(truth) / tot_area, 10) if tot_area else None,
        "n_candidates": int(len(cand)), "n_duplicates": int(dup.sum()),
        **res, "ci95": [lo, hi], "bootstrap_unreliable": len(scored) < 15, "calibration": cal,
    }
    cent = cand.geometry.centroid if len(cand) else gpd.GeoSeries([])
    out = pd.DataFrame({"cand_id": cand["cand_id"], "block_id": cand["block_id"], "score": cand["score"],
                        "area_m2": cand["area_m2"], "matched_truth": cand["matched_truth"], "is_dup": cand["is_dup"],
                        "cx": cent.x.round(3) if len(cand) else [], "cy": cent.y.round(3) if len(cand) else []})
    if keep_geometry:
        out = gpd.GeoDataFrame(out, geometry=cand.geometry.values, crs=blocks.crs)
    summary["_blocks"] = pd.DataFrame({"block_id": scored, "n_truth": [p[1] for p in payload],
                                       "area_km2": [p[2] for p in payload]})
    return summary, out


def _round(o):
    if isinstance(o, float):
        return None if not np.isfinite(o) else round(o, 10)
    if isinstance(o, dict):
        return {k: _round(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v) for v in o]
    return o


def write_json(summary: dict, path: Path) -> None:
    s = {k: v for k, v in summary.items() if not k.startswith("_")}
    Path(path).write_text(json.dumps(_round(s), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def payload_from_files(cands: pd.DataFrame, blocks_tab: pd.DataFrame, block_ids=None):
    """Rebuild the bootstrap payload from a candidates CSV and a blocks CSV (validity, leaderboard)."""
    cands = cands.copy()
    cands["matched_truth"] = [None if pd.isna(m) else str(m) for m in cands["matched_truth"]]
    cands["cand_id"] = cands["cand_id"].astype(str)
    bt = blocks_tab.set_index("block_id")
    ids = sorted(bt.index) if block_ids is None else sorted(block_ids)
    return [(cands[cands["block_id"] == b][["score", "area_m2", "cand_id", "matched_truth"]],
             int(bt.loc[b, "n_truth"]), float(bt.loc[b, "area_km2"])) for b in ids]


def parse_pred(spec: str):
    # Windows drive letters contain a colon, so split on the LAST colon only when what follows is ids.
    head, sep, tail = spec.rpartition(":")
    if sep and tail and all(t.strip().lstrip("-").isdigit() for t in tail.split(",")):
        return head, [int(t) for t in tail.split(",")]
    return spec, None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pred", nargs="+", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--layer", default=None)
    ap.add_argument("--blocks", required=True)
    ap.add_argument("--blocks-layer", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidates-out", default=None)
    ap.add_argument("--blocks-out", default=None, help="CSV block_id, n_truth, area_km2 (bootstrap payload)")
    ap.add_argument("--dn-scale", type=float, default=None)
    for k, v in DEFAULTS.items():
        ap.add_argument(f"--{k.replace('_', '-')}", type=type(v), default=v)
    a = ap.parse_args(argv)
    import geopandas as gpd
    for p in [a.labels, a.blocks] + [parse_pred(s)[0] for s in a.pred]:
        if not Path(p).exists():
            print(f"missing input: {p}", file=sys.stderr)
            return 2
    truth = gpd.read_file(a.labels, layer=a.layer)
    blocks = gpd.read_file(a.blocks, layer=a.blocks_layer)
    summary, cands = evaluate([parse_pred(s) for s in a.pred], truth, blocks, thr=a.thr,
                              min_area_m2=a.min_area_m2, iou_thr=a.iou_thr, k_per_km2=a.k_per_km2,
                              B=a.B, seed=a.seed, alpha=a.alpha, dn_scale=a.dn_scale)
    write_json(summary, Path(a.out))
    if a.candidates_out:
        cands.to_csv(a.candidates_out, index=False, float_format="%.10g", lineterminator="\n")
    if a.blocks_out:
        summary["_blocks"].to_csv(a.blocks_out, index=False, float_format="%.10g", lineterminator="\n")
    print(json.dumps({k: summary[k] for k in ("recall", "ci95", "k", "hits", "n_truth", "n_blocks")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
