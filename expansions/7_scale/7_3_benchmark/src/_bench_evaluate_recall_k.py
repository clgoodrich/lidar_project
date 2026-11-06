"""Official scorer of the terrain-feature benchmark (7.3 S2). Shipped in the release as evaluate.py.

Purpose
    Score probability rasters against drawn feature polygons with the shared rules of
    expansions/_shared/fw_00_common.md section 4. Every scoring setting comes from ONE versioned policy
    (expkit.policy_for(task), review F02 / 7.3-01). The policy dict and its hash are stamped into the JSON.
    1. Threshold at the task's proposal cutoff (pit 0.35, pad 0.525; 0.10 only in --mode sensitivity),
       connected blobs (8-neighbour), drop blobs under min_area_m2 (4 m2).
    2. Score each blob by its mean probability.
    3. Greedy one-to-one match at IoU >= 0.3, in score order (primary) or IoU order (sensitivity).
       A candidate matches only truth in its own block (both by centroid), review 7.3-02.
       A second blob inside a matched feature is a duplicate.
    4. Rank every candidate in the scored footprint. Keep the top K per km2 (K = 40).
       Ties break by larger area, then by candidate id.
    5. Recall = matched truth features / all truth features in the footprint (complete blocks).
       Only truth inside the denominator can be a hit (eligible_truth). Recall above 1 raises.
    6. Block-bootstrap 95% interval (B = 2000) and calibration (Brier, log loss, ECE). An undefined draw
       (a resample with no truth) is counted, never dropped. Any undefined draw makes the interval null.
    Deterministic. Same inputs give byte-identical JSON.

    Where the policy comes from
        In a release, scoring_policy.json next to this file (written by the export from expkit.policy_for).
        In the repo, expkit.policy_for directly. A fresh checkout has no expkit, so the module keeps a local
        copy of recall_at_k and block_bootstrap that the tests assert equal to expkit's. When expkit is
        importable, expkit's functions are used.

Inputs
    --pred      one or more prediction specs "path[:block_id,block_id,...]". A float probability raster
                in metres. Values below 0 or equal to nodata are invalid. With --dn-scale 254 a uint8
                mosaic is read as DN / 254 and 255 is nodata (protocol section 2 rule 2).
                Block ids after the colon restrict that raster to those blocks (out-of-fold use).
    --task      pit_floor, pit_full or pad. Selects the policy (cutoff). --layer defaults to the task.
    --mode      primary (default) or sensitivity.
    --labels    GeoPackage of drawn features (layer --layer). Any CRS, reprojected to the blocks CRS.
    --blocks    GeoPackage of complete scored blocks with an integer column block_id.
Outputs
    --out             JSON summary (policy, recall, interval, k, hits, n_truth, area, density, calibration).
    --blocks-out      optional CSV, one row per scored block (block_id, n_truth, area_km2).
    --candidates-out  optional CSV, one row per candidate (cand_id, block_id, score, area_m2, matched_truth,
                      truth_block_id, is_dup, cx, cy). The validity and leaderboard scripts read this file.

Run
    python expansions/7_scale/7_3_benchmark/src/_bench_evaluate_recall_k.py --task pit_floor \
        --pred pred.tif --labels labels_devtest.gpkg --blocks blocks_devtest.gpkg \
        --out score.json --candidates-out cands.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCORER_VERSION = "terrain_v1_scorer_1.1"
DEFAULTS = dict(B=2000, seed=0, alpha=0.05)
POLICY_FILE = "scoring_policy.json"
TASKS = ("pit_floor", "pit_full", "pad")


def _find_expkit():
    """expkit when this file sits inside the repo, else None (fresh checkout of a release)."""
    for d in Path(__file__).resolve().parents:
        src = d / "expansions" / "_shared" / "src"
        if (src / "expkit.py").exists():
            if str(src) not in sys.path:
                sys.path.insert(0, str(src))
            try:
                import expkit
                return expkit
            except Exception:  # noqa: BLE001 - a broken repo import falls back to the local copy
                return None
    return None


_EK = _find_expkit()


def load_policy(task: str, mode: str = "primary", policy_file: Path | None = None) -> dict:
    """The scoring policy. The release's scoring_policy.json wins (frozen with the release), else expkit."""
    pf = Path(policy_file) if policy_file else Path(__file__).resolve().parent / POLICY_FILE
    if pf.exists():
        doc = json.loads(pf.read_text(encoding="utf-8"))
        if task not in doc.get(mode, {}):
            raise KeyError(f"{pf}: no {mode} policy for task '{task}'. Known: {sorted(doc.get(mode, {}))}")
        return dict(doc[mode][task])
    if _EK is None:
        raise FileNotFoundError(f"no {POLICY_FILE} next to the scorer and no expkit. Cannot score.")
    return _EK.policy_for(task, mode)


# ----------------------------------------------------------------------------- candidates
def extract_candidates(prob: np.ndarray, transform, *, thr: float, min_area_m2: float,
                       valid: np.ndarray | None = None, crs=None, id_prefix: str = "c"):
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
def match_greedy_iou(cands, truth, iou_thr: float = 0.3, truth_id_col: str = "truth_id",
                     order: str = "score", block_col: str | None = None):
    """One-to-one greedy IoU match. Returns (matched_truth list, is_dup bool array).

    order "score" (primary, fw_00 section 4): pairs by candidate score descending, then IoU descending,
    then candidate id, then truth id. order "iou" (sensitivity): IoU descending, then ids.
    block_col: when given, a candidate may match only truth with the same block id (review 7.3-02).
    A candidate whose centroid falls inside an already-matched truth feature, and which is itself
    unmatched, is a duplicate (fw_00 section 4).
    """
    if order not in ("score", "iou"):
        raise ValueError(f"match order must be score or iou, got {order}")
    n = len(cands)
    matched = [None] * n
    dup = np.zeros(n, bool)
    if n == 0 or len(truth) == 0:
        return matched, dup
    tids = truth[truth_id_col].tolist()
    tgeom = truth.geometry.values
    tblk = truth[block_col].to_numpy() if block_col else None
    cblk = cands[block_col].to_numpy() if block_col else None
    sidx = truth.sindex
    pairs = []
    cgeom = cands.geometry.values
    cid = cands["cand_id"].tolist()
    csc = cands["score"].to_numpy(float) if "score" in cands else np.zeros(n)
    for i, g in enumerate(cgeom):
        for j in sidx.query(g, predicate="intersects"):
            if block_col and int(cblk[i]) != int(tblk[j]):
                continue
            inter = g.intersection(tgeom[j]).area
            if inter <= 0:
                continue
            iou = inter / (g.area + tgeom[j].area - inter)
            if iou >= iou_thr:
                key = (-csc[i], -iou) if order == "score" else (-iou,)
                pairs.append((*key, cid[i], str(tids[j]), i, j))
    pairs.sort()
    used_c, used_t = set(), set()
    for *_, i, j in pairs:
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
def _recall_at_k_local(scores, matched_truth, n_truth_by_block: dict, area_km2: float, k_per_km2: float,
                       areas, cand_ids, eligible_truth=None):
    """Copy of expkit.recall_at_k for a fresh checkout. test_7_3.py asserts the two agree."""
    df = pd.DataFrame({"s": np.asarray(scores, float), "t": list(matched_truth),
                       "a": np.asarray(areas, float), "i": np.asarray(cand_ids)})
    df = df.sort_values(["s", "a", "i"], ascending=[False, False, True], kind="mergesort")
    k = int(round(k_per_km2 * area_km2))
    t = df.head(k)["t"].dropna()
    if eligible_truth is not None:
        t = t[t.isin(set(eligible_truth))]
    hits = t.nunique()
    n_truth = int(sum(n_truth_by_block.values()))
    if hits > n_truth:
        raise AssertionError(f"recall_at_k: {hits} hits > {n_truth} truth")
    return {"recall": hits / n_truth if n_truth else float("nan"), "k": k, "hits": int(hits), "n_truth": n_truth}


def recall_at_k_table(cand: pd.DataFrame, n_truth_by_block: dict, area_km2: float, k_per_km2: float,
                      eligible_truth=None):
    """cand has score, area_m2, cand_id, matched_truth, block_id. Ties: score desc, area desc, id asc.
    expkit.recall_at_k when importable, else the local copy."""
    args = (cand["score"].to_numpy(float), list(cand["matched_truth"]))
    if _EK is not None:
        return _EK.recall_at_k(*args, cand["block_id"].tolist(), n_truth_by_block, area_km2, k_per_km2=k_per_km2,
                               areas=cand["area_m2"].to_numpy(float), cand_ids=cand["cand_id"].astype(str).to_numpy(),
                               eligible_truth=eligible_truth)
    return _recall_at_k_local(*args, n_truth_by_block, area_km2, k_per_km2, cand["area_m2"].to_numpy(float),
                              cand["cand_id"].astype(str).to_numpy(), eligible_truth)


PAYLOAD_COLS = ["score", "area_m2", "cand_id", "matched_truth", "block_id"]


def block_tables(cand: pd.DataFrame, truth: pd.DataFrame, block_ids, block_area_km2: dict):
    """Per-block payload for the bootstrap: (candidate rows, n truth, area, truth ids in the block)."""
    out = []
    for b in block_ids:
        c = cand[cand["block_id"] == b][PAYLOAD_COLS]
        tb = truth[truth["block_id"] == b]
        out.append((c, int(len(tb)), float(block_area_km2[b]), frozenset(tb["truth_id"].astype(str))))
    return out


def pooled_recall(blocks_payload, k_per_km2: float) -> float:
    """Pool a list of block payloads (replicates allowed) and compute recall at K.
    Each replicate r prefixes its candidate and truth ids with r, and only its own truth is eligible."""
    parts, nt_by, area, elig = [], {}, 0.0, set()
    if any(p[3] is None for p in blocks_payload):
        elig = None                      # legacy payload: no eligibility filter (recall > 1 still raises)
    for r, (c, nt, a, tids) in enumerate(blocks_payload):
        if len(c):
            c = c.copy()
            c["matched_truth"] = [None if m is None or (isinstance(m, float) and np.isnan(m)) else f"{r}|{m}"
                                  for m in c["matched_truth"]]
            c["cand_id"] = f"{r}|" + c["cand_id"].astype(str)
            parts.append(c)
        nt_by[r] = nt
        area += a
        if elig is not None:
            elig |= {f"{r}|{t}" for t in tids}
    cand = pd.concat(parts) if parts else pd.DataFrame(columns=PAYLOAD_COLS)
    return recall_at_k_table(cand, nt_by, area, k_per_km2, eligible_truth=elig)["recall"]


def _bootstrap_local(stat_fn, blocks, B, seed, alpha):
    """Copy of expkit.block_bootstrap with max_undefined=0 (any undefined draw -> null interval)."""
    rng = np.random.default_rng(seed)
    n = len(blocks)
    point = stat_fn(blocks)
    draws = np.array([stat_fn([blocks[j] for j in rng.integers(0, n, n)]) for _ in range(B)], dtype=float)
    if draws.size == 0 or not np.isfinite(draws).all():
        return float(point), float("nan"), float("nan"), draws
    lo, hi = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(point), float(lo), float(hi), draws


def bootstrap_blocks(payload, k_per_km2, B, seed, alpha):
    """Returns (lo, hi, undefined_share)."""
    fn = lambda bl: pooled_recall(bl, k_per_km2)  # noqa: E731
    if _EK is not None:
        _, lo, hi, draws = _EK.block_bootstrap(fn, payload, B=B, seed=seed, alpha=alpha)
    else:
        _, lo, hi, draws = _bootstrap_local(fn, payload, B, seed, alpha)
    und = float(np.mean(~np.isfinite(draws))) if draws.size else 1.0
    return float(lo), float(hi), und


def calibration(y, p, bins: int = 10):
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-7, 1 - 1e-7)
    if len(y) == 0:
        return {"brier": float("nan"), "log_loss": float("nan"), "ece": float("nan")}
    order = np.argsort(p, kind="stable")
    ece = sum(len(ix) / len(p) * abs(y[ix].mean() - p[ix].mean()) for ix in np.array_split(order, bins) if len(ix))
    return {"brier": float(np.mean((p - y) ** 2)),
            "log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))), "ece": float(ece)}


# ----------------------------------------------------------------------------- top level
def legacy_policy(thr, min_area_m2, iou_thr, k_per_km2) -> dict:
    """A policy dict from loose settings (callers written before review F02). It is marked as not the
    shared policy, so it can never pass ek.assert_same_policy against expkit.policy_for by accident."""
    return {"task": None, "mode": "caller_supplied", "version": "caller_supplied_not_shared_policy",
            "cutoff": float(thr), "min_area_m2": float(min_area_m2), "iou": float(iou_thr), "match_order": "score",
            "blob_score": "mean", "k_per_km2": float(k_per_km2), "policy_hash": None}


def evaluate(pred_specs, truth, blocks, *, policy: dict | None = None, B=DEFAULTS["B"], seed=DEFAULTS["seed"],
             alpha=DEFAULTS["alpha"], dn_scale=None, block_col="block_id", keep_geometry=False,
             thr=None, min_area_m2=None, iou_thr=None, k_per_km2=None):
    """pred_specs: list of (path_or_(prob, transform), block_ids or None). Returns (summary, cand_df).

    policy is the dict from load_policy / expkit.policy_for. It sets cutoff, min_area_m2, iou, match_order
    and k_per_km2, and is stamped into the summary. keep_geometry=True returns cand_df as a GeoDataFrame.
    thr / min_area_m2 / iou_thr / k_per_km2 are the pre-F02 keywords, kept so 7.1 and 7.2 still run. They
    build a policy marked caller_supplied. Passing them together with policy is an error.
    """
    import geopandas as gpd
    legacy = (thr, min_area_m2, iou_thr, k_per_km2)
    if policy is None:
        if any(v is None for v in legacy):
            raise TypeError("evaluate needs policy=load_policy(task) (or all four legacy keywords)")
        policy = legacy_policy(*legacy)
    elif any(v is not None for v in legacy):
        raise TypeError("pass either policy or the legacy keywords, not both")
    for key in ("cutoff", "min_area_m2", "iou", "match_order", "k_per_km2", "blob_score"):
        if key not in policy:
            raise KeyError(f"scoring policy lacks '{key}'")
    if policy["blob_score"] != "mean":
        raise ValueError(f"blob_score {policy['blob_score']} not implemented")
    thr, min_area_m2, iou_thr, k_per_km2 = policy["cutoff"], policy["min_area_m2"], policy["iou"], policy["k_per_km2"]
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
    truth = truth[truth["block_id"].isin(scored)].reset_index(drop=True)
    cand = cand[cand["block_id"].isin(scored)].reset_index(drop=True)
    matched, dup = match_greedy_iou(cand, truth, iou_thr, order=policy["match_order"], block_col="block_id")
    cand["matched_truth"] = matched
    cand["is_dup"] = dup
    tblock = dict(zip(truth["truth_id"], truth["block_id"]))
    area_km2 = {int(b): float(g.area) / 1e6 for b, g in zip(blocks[block_col], blocks.geometry)}
    tot_area = sum(area_km2[b] for b in scored)
    nt_by = truth["block_id"].value_counts().to_dict()
    res = recall_at_k_table(cand, {b: int(nt_by.get(b, 0)) for b in scored}, tot_area, k_per_km2,
                            eligible_truth=set(truth["truth_id"]))
    payload = block_tables(cand, truth, scored, area_km2)
    if B:
        lo, hi, und = bootstrap_blocks(payload, k_per_km2, B, seed, alpha)
    else:
        lo, hi, und = float("nan"), float("nan"), None
    cal = calibration(pd.notna(cand["matched_truth"]).to_numpy(), cand["score"].to_numpy())
    summary = {
        "scorer_version": SCORER_VERSION, "policy": dict(policy),
        "params": dict(B=B, seed=seed, alpha=alpha, match_scope="within block"),
        "n_blocks": len(scored), "area_km2": round(tot_area, 10),
        "truth_density_per_km2": round(len(truth) / tot_area, 10) if tot_area else None,
        "n_candidates": int(len(cand)), "n_duplicates": int(dup.sum()),
        **res, "ci95": [lo, hi], "bootstrap_undefined_share": und,
        "bootstrap_unreliable": len(scored) < 15, "calibration": cal,
    }
    cent = cand.geometry.centroid if len(cand) else gpd.GeoSeries([])
    out = pd.DataFrame({"cand_id": cand["cand_id"], "block_id": cand["block_id"], "score": cand["score"],
                        "area_m2": cand["area_m2"], "matched_truth": cand["matched_truth"],
                        "truth_block_id": [tblock.get(m) if m is not None else None for m in cand["matched_truth"]],
                        "is_dup": cand["is_dup"],
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


def payload_from_files(cands: pd.DataFrame, blocks_tab: pd.DataFrame, block_ids=None, strict: bool = False):
    """Rebuild the bootstrap payload from a candidates CSV and a blocks CSV (validity, leaderboard).

    Eligible truth of a block is the matched truth whose truth_block_id is that block. A candidates CSV
    without truth_block_id came from scorer 1.0 (cross-block matching). strict=True refuses it (7.3 uses
    this). strict=False (kept for 7.1 and 7.2 until they rescore) warns and applies no eligibility filter,
    so recall above 1 still raises inside recall_at_k."""
    legacy = "truth_block_id" not in cands.columns
    if legacy:
        msg = ("candidates CSV has no truth_block_id column. It was written by scorer 1.0, which matched "
               "across blocks. Rescore it with the current scorer.")
        if strict:
            raise ValueError(msg)
        import warnings
        warnings.warn(msg, stacklevel=2)
    cands = cands.copy()
    cands["matched_truth"] = [None if pd.isna(m) else str(m) for m in cands["matched_truth"]]
    cands["cand_id"] = cands["cand_id"].astype(str)
    bt = blocks_tab.set_index("block_id")
    ids = sorted(bt.index) if block_ids is None else sorted(block_ids)
    out = []
    for b in ids:
        c = cands[cands["block_id"] == b]
        if legacy:
            elig = None
        else:
            elig = frozenset(c.loc[pd.notna(c["truth_block_id"]) & (c["truth_block_id"] == b), "matched_truth"])
        out.append((c[PAYLOAD_COLS], int(bt.loc[b, "n_truth"]), float(bt.loc[b, "area_km2"]), elig))
    return out


def parse_pred(spec: str):
    # Windows drive letters contain a colon, so split on the LAST colon only when what follows is ids.
    head, sep, tail = spec.rpartition(":")
    if sep and tail and all(t.strip().lstrip("-").isdigit() for t in tail.split(",")):
        return head, [int(t) for t in tail.split(",")]
    return spec, None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pred", nargs="+", required=True)
    ap.add_argument("--task", required=True, choices=TASKS)
    ap.add_argument("--mode", default="primary", choices=("primary", "sensitivity"))
    ap.add_argument("--labels", required=True)
    ap.add_argument("--layer", default=None, help="default: the task name")
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
    policy = load_policy(a.task, a.mode)
    truth = gpd.read_file(a.labels, layer=a.layer or a.task)
    blocks = gpd.read_file(a.blocks, layer=a.blocks_layer)
    summary, cands = evaluate([parse_pred(s) for s in a.pred], truth, blocks, policy=policy,
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
