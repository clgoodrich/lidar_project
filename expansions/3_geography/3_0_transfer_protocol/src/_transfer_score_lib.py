"""3.0 core. The one reference scorer for recall at K per km2 on 9t and on every target area.

Purpose
    Probability raster + scored footprint + blocks + annotated features in, recall at K with a block
    bootstrap, density, a density-scaled secondary, calibration and per-block counts out. The same functions
    score 9t and targets, and 3.1 / 3.2 call them in memory (`extract`, `score_tables`). Settings come from
    `ek.policy_for(task)` and the policy dict and its hash are stamped into every output. `module_sha256()`
    lets every run record the code it used (3.0 QC).

Steps (fw_3_0 S1, fw_00 section 4, policy fw00_s4_20261105)
    1. Grid check (`assert_metric_crs`, `assert_same_grid`). Projected CRS in metres whose horizontal part is
       EPSG:6346 (a compound CRS passes), the full affine transform, no rotation, equal shapes.
    2. Eligible blocks. Complete blocks inside the footprint. An edge block touches the data boundary. That is
       a cell outside the raster, or a nodata cell connected to the raster's outer nodata region. Nodata cells
       inside the data count toward the block void fraction with the void raster. A block whose void fraction
       exceeds the cap is dropped (fw_3_0 "edge blocks that touch the data boundary or have void fraction above
       a preregistered cap"). The cap comes from the preregistration, else config `void_cap_default`.
       One interior NaN pixel no longer drops a block (review G-05).
    3. Extraction on the whole raster (`extract`). Cut at the task cutoff of the policy (pit 0.35, pad 0.525),
       label connected blobs once, drop blobs under 4 m2, score by mean probability. This is `polygonize` from
       `notebooks/wellsight_v2/s5_eval/_threshold_common.py`. One physical blob gives one candidate whatever the
       block layout (review F03). 0.10 is the sensitivity cutoff (`mode="sensitivity"`).
    4. Keep candidates whose centroid lies in an eligible block. Truth features likewise by centroid.
    5. Greedy one-to-one matching at IoU 0.3 over all kept candidates, pairs in candidate score order (the
       policy's match_order). `order="iou"` is the sensitivity.
    6. Dedupe. An unmatched candidate whose centroid is inside a matched truth feature is a second piece of one
       feature. It is dropped before ranking. This rule reads truth, so it is a scoring rule, not a deployment
       rule (`dedupe="none"` turns it off).
    7. Rank by score, ties by larger area then lower candidate id. Keep the top K. K = round(k_per_km2 * area)
       pooled (`k_rule="global"`), or floor(k_per_km2 * group area) per group (`k_rule="per_group"`, the
       archival sweep's per-fold rule).
    8. Recall = matched truth features in the kept set over all eligible truth features. Hits are credited to
       the truth feature's block. Block bootstrap of pooled counts (B = 2000), percentile 95% interval.
       Fewer than 15 blocks also gets a sign-flip interval and a warning. Fewer than 2 blocks with truth gives
       "not identifiable" instead, because the residual about the pooled ratio is then zero by construction.
    9. Secondary. K2 = c * truth density per km2, c from the preregistration.
    10. Calibration. Pixel level and candidate level (ek.calibration).

Inputs
    any probability raster (float 0-1, or uint8 DN / 254 with 255 nodata), blocks GeoPackage (layer `blocks`,
    column `block_id`), truth layer, optional footprint polygon and void-fraction raster

Outputs
    None. Library only. `_transfer_score_run.py` writes the files. `read_ref_tables` reads the 3.0 reference
    tables in both the old (blocks only) and the new (blocks + "policy" + "meta") schema.

Run
    Not a script. `python -m pytest -q -p no:cacheprovider expansions/3_geography/3_0_transfer_protocol/src/test_3_0.py`
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402
sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2" / "s5_eval"))

_CFG = json.loads((HERE.parent / "config_3_0.json").read_text(encoding="utf-8"))
# CUTOFF is the fw_00 SENSITIVITY cutoff (0.10). It is never the primary. The primary is policy_for(task)["cutoff"].
CUTOFF = float(ek.PROPOSAL_POLICY["sensitivity_cutoff"])
MIN_AREA, IOU = float(ek.PROPOSAL_POLICY["min_area_m2"]), float(ek.PROPOSAL_POLICY["iou"])
VOID_CAP_DEFAULT = float(_CFG["scoring_defaults"]["void_cap_default"])
CFG_CUTOFF_BY_TASK = dict(_CFG["scoring_defaults"]["cutoff_by_task"])   # read-only mirror, tested equal to policy_for
POLICY_KEYS = ("cutoff", "min_area_m2", "iou", "match_order", "blob_score", "k_per_km2", "version")


def module_sha256() -> str:
    return hashlib.sha256(HERE.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- policy
def policy(task: str, mode: str = "primary", **override) -> dict:
    """ek.policy_for(task, mode), with optional overrides (cutoff, min_area_m2, iou, match_order, k_per_km2).
    An override that changes a value marks the dict mode 'custom' and rehashes it, so assert_same_policy
    against a primary reference fails loudly."""
    p = dict(ek.policy_for(task, mode))
    changed = {k: v for k, v in override.items() if v is not None and p.get(k) != v}
    if changed:
        p.update(changed)
        p["mode"] = "custom"
        p.pop("policy_hash", None)
        p["policy_hash"] = ek.config_hash(p)
    return p


def same_number(a, b) -> bool:
    """40 equals 40.0. Strings that parse as numbers compare as numbers."""
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


# ----------------------------------------------------------------------------- grid contract (review F11)
def assert_metric_crs(crs, expected: str = ek.DST_CRS) -> None:
    """Projected CRS in metres whose horizontal part is EPSG:6346. Compound CRS passes on its horizontal part.
    Degrees and feet raise."""
    from pyproj import CRS
    if crs is None:
        raise AssertionError("raster or layer has no CRS")
    c = CRS.from_user_input(crs)
    horiz = c.sub_crs_list[0] if c.is_compound and c.sub_crs_list else c
    if not horiz.is_projected:
        raise AssertionError(f"CRS {horiz.name} is not projected (angular units). Reproject to {expected}")
    for ax in horiz.axis_info:
        if abs(float(ax.unit_conversion_factor) - 1.0) > 1e-9:
            raise AssertionError(f"CRS {horiz.name} axis unit {ax.unit_name} is not metres")
    ek.assert_crs(c, expected)


def assert_same_grid(a: dict, b: dict, label: str = "rasters") -> None:
    """a, b = {'crs', 'transform', 'shape'}. Same metric CRS, all six affine terms, no rotation, same shape."""
    for g in (a, b):
        assert_metric_crs(g["crs"])
        t = g["transform"]
        if abs(t.b) > 0 or abs(t.d) > 0:
            raise ValueError(f"{label}: rotated transform {t}")
    from pyproj import CRS
    ha, hb = (CRS.from_user_input(g["crs"]) for g in (a, b))
    ha = ha.sub_crs_list[0] if ha.is_compound else ha
    hb = hb.sub_crs_list[0] if hb.is_compound else hb
    if ha != hb:
        raise ValueError(f"{label}: CRS differ ({ha.name} vs {hb.name})")
    ta, tb = a["transform"], b["transform"]
    tol = 1e-9 * max(abs(ta.a), 1.0)
    if any(abs(x - y) > tol for x, y in zip(tuple(ta)[:6], tuple(tb)[:6])):
        raise ValueError(f"{label} must have identical CRS, shape and pixel transform: {tuple(ta)[:6]} vs {tuple(tb)[:6]}")
    if tuple(a["shape"]) != tuple(b["shape"]):
        raise ValueError(f"{label}: shape {a['shape']} vs {b['shape']}")


def grid_of(path: Path) -> dict:
    import rasterio
    with rasterio.open(path) as r:
        return {"crs": r.crs, "transform": r.transform, "shape": (r.height, r.width)}


# ----------------------------------------------------------------------------- reading
def decode_prob(a: np.ndarray, nodata, scale: str = "auto") -> np.ndarray:
    """Raster band -> float32 probability with NaN nodata. uint8 is DN / 254 with 255 (or nodata) as nodata."""
    if a.dtype == np.uint8 and scale in ("auto", "dn254"):
        valid = a != (255 if nodata is None else int(nodata))
        return np.where(valid, a.astype(np.float32) / 254.0, np.nan).astype(np.float32)
    p = a.astype(np.float32)
    if nodata is not None and np.isfinite(nodata):
        p[p == nodata] = np.nan
    return p


def read_prob(path: Path, scale: str = "auto"):
    """Returns (prob float32 with NaN nodata, transform, crs). uint8 rasters are DN / 254, 255 nodata."""
    import rasterio
    with rasterio.open(path) as r:
        assert_metric_crs(r.crs)
        if abs(r.transform.b) > 0 or abs(r.transform.d) > 0:
            raise ValueError(f"{path}: rotated transform")
        a = r.read(1)
        nd = r.nodata
        tf, crs = r.transform, r.crs
    p = decode_prob(a, nd, scale)
    if not (a.dtype == np.uint8 and scale in ("auto", "dn254")):
        if np.isfinite(p).any() and (np.nanmax(p) > 1.0 + 1e-6 or np.nanmin(p) < -1e-6):
            raise AssertionError(f"{path}: probabilities outside [0, 1]")
    return p, tf, crs


def read_truth(spec: str, crs, id_col: str | None = None):
    """spec 'path.gpkg:layer'. Multi-part features with one id are dissolved into one feature."""
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
    from _common import read_layer
    path, layer = spec.rsplit(":", 1) if ":" in Path(spec).name else (spec, None)
    g = read_layer(Path(path), layer) if layer else __import__("geopandas").read_file(path)
    g = g.to_crs(crs)
    if id_col and id_col in g.columns:
        g = g[[id_col, "geometry"]].dissolve(by=id_col).reset_index().rename(columns={id_col: "truth_id"})
    else:
        g = g[["geometry"]].reset_index(drop=True)
        g["truth_id"] = np.arange(len(g))
    return g[g.geometry.notna() & ~g.geometry.is_empty].reset_index(drop=True)


# ----------------------------------------------------------------------------- footprint
def exterior_nodata(nan: np.ndarray) -> np.ndarray:
    """Nodata cells 4-connected to the raster border. This is the data boundary."""
    if not nan.any():
        return np.zeros(nan.shape, bool)
    from scipy import ndimage as ndi
    lbl, _ = ndi.label(nan)
    border = np.unique(np.concatenate([lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]]))
    border = border[border > 0]
    return np.isin(lbl, border) if len(border) else np.zeros(nan.shape, bool)


def eligible_blocks(blocks, prob, tf, footprint=None, void=None, void_cap: float | None = None,
                    drop_edge: bool = True):
    """blocks with columns block_id, area_km2, edge, nodata_frac, void_frac, eligible. Complete blocks only.

    edge       a cell outside the raster, or a nodata cell joined to the raster's outer nodata region
    void_frac  (sum of the void raster over valid cells + interior nodata cells) / block cells
    eligible   in footprint, not edge (when drop_edge), void_frac <= cap. cap = void_cap or VOID_CAP_DEFAULT.
    """
    from rasterio.features import rasterize
    b = blocks.copy()
    b["block_id"] = b.block_id.astype(int)
    lab = rasterize([(g, i + 1) for i, g in enumerate(b.geometry)], out_shape=prob.shape, transform=tf,
                    fill=0, dtype="int32")
    cell = abs(tf.a * tf.e)
    flat = lab.ravel()
    nb = len(b) + 1
    n_cells = np.bincount(flat, minlength=nb)[1:]
    nan = ~np.isfinite(prob)
    ext = exterior_nodata(nan)
    n_valid = np.bincount(flat, weights=(~nan).ravel(), minlength=nb)[1:]
    n_ext = np.bincount(flat, weights=ext.ravel(), minlength=nb)[1:]
    n_int = np.bincount(flat, weights=(nan & ~ext).ravel(), minlength=nb)[1:]
    expect = (b.geometry.area / cell).to_numpy()
    b["coverage"] = n_valid / np.maximum(expect, 1)
    b["edge"] = (n_cells < 0.999 * expect) | (n_ext > 0)
    b["nodata_frac"] = (n_cells - n_valid) / np.maximum(n_cells, 1)
    vsum = np.zeros(len(b))
    if void is not None:
        vv = np.where(nan, 0.0, np.nan_to_num(void, nan=0.0))
        vsum = np.bincount(flat, weights=vv.ravel(), minlength=nb)[1:]
    b["void_frac"] = (vsum + n_int) / np.maximum(n_cells, 1)
    inside = np.ones(len(b), bool)
    if footprint is not None:
        fu = footprint.to_crs(b.crs).geometry.union_all()
        inside = np.array([fu.buffer(1e-6).contains(g) for g in b.geometry])
    b["in_footprint"] = inside
    cap = VOID_CAP_DEFAULT if void_cap is None else float(void_cap)
    b["void_cap"] = cap
    b["eligible"] = inside & ((~b.edge) if drop_edge else True) & (b.void_frac <= cap)
    b["area_km2"] = b.geometry.area / 1e6
    return b


def assign_blocks(gdf, blocks):
    """block_id of each geometry's centroid (NaN outside). Centroid is the 9t sweep's rule.
    A centroid exactly on a seam goes to the lower block id, so it is never lost (it was with 'within')."""
    import geopandas as gpd
    if not len(gdf):
        return pd.Series([], dtype=float)
    c = gpd.GeoDataFrame(geometry=gdf.geometry.centroid, crs=gdf.crs)
    j = gpd.sjoin(c, blocks[["block_id", "geometry"]], how="left", predicate="intersects")
    j = j.assign(_o=np.arange(len(j))).sort_values(["block_id", "_o"], kind="mergesort")
    j = j[~j.index.duplicated(keep="first")]
    return j["block_id"].reindex(gdf.index)


# ----------------------------------------------------------------------------- candidates and matching
def candidates(prob, tf, crs, cutoff: float | None = None, min_area: float = MIN_AREA, *, policy: dict | None = None):
    """Connected blobs of prob >= cutoff, mean-probability score. Give cutoff or a policy dict."""
    from _threshold_common import polygonize
    if policy is not None:
        if cutoff is not None and not same_number(cutoff, policy["cutoff"]):
            raise ValueError(f"cutoff {cutoff} disagrees with policy cutoff {policy['cutoff']}")
        cutoff, min_area = policy["cutoff"], policy["min_area_m2"]
    if cutoff is None:
        raise ValueError("candidates needs an explicit cutoff or a policy (ek.policy_for(task))")
    c = polygonize(np.nan_to_num(prob, nan=0.0), tf, crs, float(cutoff), float(min_area))
    c["area_m2"] = c.geometry.area
    c["cand_id"] = np.arange(len(c))
    return c


def extract(prob, tf, crs, policy: dict):
    """Candidates over the whole array at the policy's cutoff and minimum area."""
    return candidates(prob, tf, crs, policy=policy)


def match_greedy(truth, cands, iou: float = IOU, order: str = "score"):
    """1:1 greedy. Returns (truth_id matched per candidate or None, set of matched truth ids)."""
    if order not in ("score", "iou"):
        raise ValueError(f"order must be score or iou, got {order}")
    pairs = []
    if len(truth) and len(cands):
        sidx = cands.sindex
        sc = cands["score"].to_numpy()
        for gi, g in enumerate(truth.geometry):
            for pj in sidx.intersection(g.bounds):
                p = cands.geometry.iloc[pj]
                inter = g.intersection(p).area
                if inter <= 0:
                    continue
                u = g.area + p.area - inter
                v = inter / u if u > 0 else 0.0
                if v >= iou:
                    pairs.append((gi, int(pj), v, float(sc[pj])))
    key = (lambda p: (-p[3], -p[2], p[1])) if order == "score" else (lambda p: (-p[2], -p[3], p[1]))
    tm, cm = set(), {}
    tid = truth["truth_id"].to_numpy() if len(truth) else np.array([])
    for gi, pj, _, _ in sorted(pairs, key=key):
        if gi in tm or pj in cm:
            continue
        tm.add(gi)
        cm[pj] = tid[gi]
    out = [cm.get(j) for j in range(len(cands))]
    return out, {tid[g] for g in tm}


def dedupe_mask(cands, truth, matched: list) -> np.ndarray:
    """True for an unmatched candidate whose centroid lies inside a matched truth feature."""
    mt = set(m for m in matched if not pd.isna(m))
    if not mt or not len(cands):
        return np.zeros(len(cands), bool)
    mg = truth[truth.truth_id.isin(mt)]
    import geopandas as gpd
    cen = gpd.GeoDataFrame(geometry=cands.geometry.centroid, crs=cands.crs)
    j = gpd.sjoin(cen, mg[["geometry"]], how="inner", predicate="within")
    inside = np.zeros(len(cands), bool)
    inside[np.unique(j.index.to_numpy())] = True
    return inside & np.array([bool(pd.isna(m)) for m in matched])


# ----------------------------------------------------------------------------- scoring
def rank_keep(df: pd.DataFrame, k_per_km2: float, area_km2: float, k_rule: str = "global",
              group_area: dict | None = None) -> np.ndarray:
    """Boolean keep mask over df rows (columns score, area_m2, cand_id, [group])."""
    keep = np.zeros(len(df), bool)
    if not len(df):
        return keep
    if k_rule == "global":
        o = np.lexsort((df.cand_id.to_numpy(), -df.area_m2.to_numpy(), -df.score.to_numpy()))
        keep[o[: int(round(k_per_km2 * area_km2))]] = True
        return keep
    for g, a in (group_area or {}).items():
        idx = np.where(df["group"].to_numpy() == g)[0]
        sub = df.iloc[idx]
        o = np.lexsort((sub.cand_id.to_numpy(), -sub.area_m2.to_numpy(), -sub.score.to_numpy()))
        keep[idx[o[: int(np.floor(k_per_km2 * a))]]] = True
    return keep


def per_block_counts(cands: pd.DataFrame, keep: np.ndarray, truth: pd.DataFrame, blocks: pd.DataFrame) -> pd.DataFrame:
    """Per eligible block. kept candidates, truth features, matched truth among kept (credited to truth block)."""
    eb = blocks[blocks.eligible]
    hit_ids = set(m for m, k in zip(cands["matched"], keep) if k and not pd.isna(m))
    t = truth.assign(hit=truth.truth_id.isin(hit_ids))
    g = t.groupby("block_id").agg(n_truth=("truth_id", "size"), hits=("hit", "sum"))
    kc = pd.Series(cands["block_id"].to_numpy()[keep]).value_counts()
    out = pd.DataFrame({"block_id": eb.block_id.astype(int).to_numpy(), "area_km2": eb.area_km2.to_numpy()})
    out["n_truth"] = out.block_id.map(g.n_truth).fillna(0).astype(int)
    out["hits"] = out.block_id.map(g.hits).fillna(0).astype(int)
    out["kept"] = out.block_id.map(kc).fillna(0).astype(int)
    return out


def score_tables(cands, truth, blocks, policy: dict, *, k_per_km2: float | None = None, dedupe: str = "truth_matched",
                 k_rule: str = "global", group_of_block: dict | None = None) -> dict:
    """In-memory core shared by `score` and 3.1 / 3.2. blocks must hold block_id, geometry, eligible.
    cands from `extract` (score, area_m2, cand_id, geometry). truth with truth_id, geometry.
    Returns dict(ranked, keep, tab, truth, cands_all, area_km2, group_area, policy)."""
    b = blocks.copy()
    if "eligible" not in b:
        b["eligible"] = True
    if "area_km2" not in b:
        b["area_km2"] = b.geometry.area / 1e6
    b["block_id"] = b.block_id.astype(int)
    el = b[b.eligible.astype(bool)]
    if not len(el):
        raise AssertionError("no eligible blocks in the footprint")
    area = float(el.area_km2.sum())
    k = float(policy["k_per_km2"] if k_per_km2 is None else k_per_km2)
    t = truth.copy()
    ek.assert_unique(t, "truth_id")
    t["block_id"] = assign_blocks(t, el) if len(t) else pd.Series(dtype=float)
    t = t[t.block_id.notna()].copy()
    t["block_id"] = t.block_id.astype(int)
    c = cands.copy()
    if "cand_id" not in c:
        c["cand_id"] = np.arange(len(c))
    if "area_m2" not in c:
        c["area_m2"] = c.geometry.area
    c["block_id"] = assign_blocks(c, el) if len(c) else pd.Series(dtype=float)
    c = c[c.block_id.notna()].reset_index(drop=True)
    c["block_id"] = c.block_id.astype(int)
    c["matched"], _ = match_greedy(t, c, policy["iou"], policy["match_order"])
    c["duplicate"] = dedupe_mask(c, t, list(c["matched"])) if dedupe == "truth_matched" else False
    ranked = c[~c.duplicate].reset_index(drop=True)
    garea = None
    if k_rule == "per_group":
        if not group_of_block:
            raise ValueError("k_rule per_group needs group_of_block")
        ranked["group"] = ranked.block_id.map(group_of_block)
        garea = el.assign(g=el.block_id.map(group_of_block)).groupby("g").area_km2.sum().to_dict()
    keep = rank_keep(ranked, k, area, k_rule, garea)
    tab = per_block_counts(ranked, keep, t, b)
    return {"ranked": ranked, "keep": keep, "tab": tab, "truth": t, "cands_all": c, "area_km2": area,
            "group_area": garea, "k_per_km2": k, "k_rule": k_rule, "policy": policy, "dedupe": dedupe,
            "blocks": b}


def pooled_recall(tab: pd.DataFrame):
    def stat(rows):
        rows = list(rows)
        n = sum(r[1] for r in rows)
        return sum(r[0] for r in rows) / n if n else float("nan")
    return stat


def bootstrap(tab: pd.DataFrame, B: int, seed: int) -> dict:
    rows = list(zip(tab.hits, tab.n_truth))
    point, lo, hi, draws = ek.block_bootstrap(pooled_recall(tab), rows, B=B, seed=seed)
    out = {"recall": point, "lo": lo, "hi": hi, "B": B, "seed": seed, "n_blocks": len(rows),
           "undefined_share": ek.undefined_share(draws)}
    if len(rows) < 15:
        out["warning"] = "fewer than 15 blocks. The bootstrap is unreliable. See the sign-flip interval."
        out["signflip"] = signflip_interval(tab, B, seed)
    return out


NOT_IDENTIFIABLE = "not identifiable (fewer than 2 blocks with truth)"


def signflip_interval(tab: pd.DataFrame, B: int, seed: int):
    """Interval for pooled recall from random sign flips of block residuals about the pooled ratio.
    Under 2 blocks with truth the residual is zero by construction, so the interval is not identifiable."""
    if int((tab.n_truth > 0).sum()) < 2:
        return NOT_IDENTIFIABLE
    r = tab.hits.sum() / max(tab.n_truth.sum(), 1)
    e = (tab.hits - r * tab.n_truth).to_numpy(float)
    n = max(tab.n_truth.sum(), 1)
    rng = np.random.default_rng(seed)
    d = np.array([(e * rng.choice([-1, 1], len(e))).sum() / n for _ in range(B)])
    lo, hi = np.percentile(d, [2.5, 97.5])
    return [float(r + lo), float(r + hi)]


def calibration_pixels(prob, truth_gdf, tf, valid_mask, n: int = 2_000_000, seed: int = 0) -> dict:
    from rasterio.features import rasterize
    y = rasterize([(g, 1) for g in truth_gdf.geometry], out_shape=prob.shape, transform=tf, fill=0,
                  dtype="uint8") if len(truth_gdf) else np.zeros(prob.shape, np.uint8)
    idx = np.flatnonzero(valid_mask & np.isfinite(prob))
    if not len(idx):
        return {}
    if len(idx) > n:
        idx = np.random.default_rng(seed).choice(idx, n, replace=False)
    return {**ek.calibration(y.ravel()[idx], prob.ravel()[idx]), "n_pixels": int(len(idx))}


def score(prob_path: Path, blocks_path: Path, truth_spec: str, k_per_km2: float = 40.0, *, truth_id: str | None = None,
          footprint_path: Path | None = None, void_path: Path | None = None, void_cap: float | None = None,
          cutoff: float | None = None, min_area: float | None = None, iou: float | None = None, order: str | None = None,
          dedupe: str = "truth_matched", k_rule: str = "global", group_of_block: dict | None = None,
          density_c: float | None = None, B: int = 2000, seed: int = 0, k_curve=(10, 20, 30, 40, 50, 60, 70, 80),
          calib_pixels: int = 2_000_000, drop_edge: bool = True, task: str = "pit", mode: str = "primary",
          checkpoint: dict | None = None) -> dict:
    """Full S1 scoring. Returns dict(summary, blocks, candidates). The policy is ek.policy_for(task, mode)
    with explicit overrides (a changed value makes the policy 'custom')."""
    import geopandas as gpd
    pol = policy(task, mode, cutoff=cutoff, min_area_m2=min_area, iou=iou, match_order=order, k_per_km2=float(k_per_km2))
    prob, tf, crs = read_prob(prob_path)
    blocks = gpd.read_file(blocks_path, layer="blocks") if str(blocks_path).endswith(".gpkg") else gpd.read_file(blocks_path)
    assert_metric_crs(blocks.crs)
    ek.assert_unique(blocks, "block_id")
    fp = gpd.read_file(footprint_path) if footprint_path else None
    void = None
    if void_path:
        void, void_tf, void_crs = read_prob(void_path, scale="none")
        assert_same_grid({"crs": crs, "transform": tf, "shape": prob.shape},
                         {"crs": void_crs, "transform": void_tf, "shape": void.shape}, "void and probability rasters")
    eb = eligible_blocks(blocks, prob, tf, fp, void, void_cap, drop_edge)
    el = eb[eb.eligible]
    if not len(el):
        raise AssertionError("no eligible blocks in the footprint")
    area = float(el.area_km2.sum())
    if not np.isclose(area, el.geometry.area.sum() / 1e6):
        raise AssertionError("footprint area differs from the sum of block areas")
    truth = read_truth(truth_spec, crs, truth_id)
    c = extract(prob, tf, crs, pol)
    core = score_tables(c, truth, eb, pol, k_per_km2=k_per_km2, dedupe=dedupe, k_rule=k_rule,
                        group_of_block=group_of_block)
    ranked, keep, tab, truth, garea = core["ranked"], core["keep"], core["tab"], core["truth"], core["group_area"]
    boot = bootstrap(tab, B, ek.child_seed(seed, 0, 0))
    n_truth = int(tab.n_truth.sum())
    dens = n_truth / area
    rk = None
    if k_rule == "global":   # independent check with the shared expkit implementation
        rk = ek.recall_at_k(ranked.score, ranked.matched, ranked.block_id, dict(zip(tab.block_id, tab.n_truth)),
                            area, k_per_km2, areas=ranked.area_m2, cand_ids=ranked.cand_id,
                            eligible_truth=set(truth.truth_id))
        if rk["hits"] != int(tab.hits.sum()):
            raise AssertionError(f"expkit recall_at_k hits {rk['hits']} != scorer hits {int(tab.hits.sum())}")
    curve = []
    for kk in k_curve:
        kp = rank_keep(ranked, kk, area, k_rule, garea)
        t2 = per_block_counts(ranked, kp, truth, eb)
        curve.append({"k_per_km2": kk, "recall": float(t2.hits.sum() / max(n_truth, 1)), "kept": int(kp.sum())})
    sec = None
    if density_c is not None:
        k2 = density_c * dens
        kp = rank_keep(ranked, k2, area, k_rule, garea)
        t2 = per_block_counts(ranked, kp, truth, eb)
        sec = {"c": density_c, "k_per_km2": k2, **bootstrap(t2, B, ek.child_seed(seed, 0, 1))}
    from rasterio.features import rasterize
    valid = rasterize([(g, 1) for g in el.geometry], out_shape=prob.shape, transform=tf, fill=0, dtype="uint8").astype(bool)
    cdup = core["cands_all"]
    summary = {
        "k_per_km2": k_per_km2, "k_rule": k_rule, "k_total": int(keep.sum()),
        "k_expected": int(round(k_per_km2 * area)) if k_rule == "global" else None,
        "eligible_area_km2": area, "n_blocks_eligible": int(len(el)), "n_blocks_total": int(len(eb)),
        "edge_blocks": sorted(eb[eb.edge].block_id.astype(int).tolist()),
        "void_capped_blocks": sorted(eb[(~eb.edge) & (eb.void_frac > eb.void_cap)].block_id.astype(int).tolist()),
        "n_truth": n_truth, "truth_density_per_km2": dens, "n_candidates": int(len(cdup)),
        "n_duplicates_dropped": int(cdup.duplicate.sum()), "hits": int(tab.hits.sum()),
        "primary": boot, "recall_at_k_expkit": rk, "secondary_density_scaled": sec, "recall_vs_k": curve,
        "calibration_pixels": calibration_pixels(prob, truth, tf, valid, calib_pixels, seed),
        "calibration_candidates": ek.calibration(ranked.matched.notna().astype(float), ranked.score) if len(ranked) else {},
        "policy": pol, "policy_hash": pol["policy_hash"],
        "scorer": {"dedupe": dedupe, "k_rule": k_rule, "block_point": "centroid", "edge_rule": "data_boundary",
                   "void_cap": float(eb.void_cap.iloc[0]), "void_cap_source": "given" if void_cap is not None else "config default",
                   "drop_edge": drop_edge},
        "footprint": {"blocks": "all eligible blocks in the blocks layer", "n_blocks_with_truth": int((tab.n_truth > 0).sum()),
                      "n_blocks_without_truth": int((tab.n_truth == 0).sum())},
        "checkpoint": checkpoint,
        "params": {"cutoff": pol["cutoff"], "min_area_m2": pol["min_area_m2"], "iou": pol["iou"],
                   "order": pol["match_order"], "dedupe": dedupe, "void_cap": float(eb.void_cap.iloc[0]),
                   "drop_edge": drop_edge, "B": B, "seed": seed},
        "module_sha256": module_sha256(),
    }
    return {"summary": summary,
            "blocks": tab.merge(eb[["block_id", "edge", "nodata_frac", "void_frac", "coverage"]], on="block_id"),
            "candidates": ranked.assign(kept=keep)}


# ----------------------------------------------------------------------------- reference tables (3.0 -> 3.4 to 3.8)
def read_ref_tables(path: Path) -> tuple[dict, dict | None, dict]:
    """(blocks {block_id str: {cands, n_truth, km2, [fold]}}, policy dict or None, meta dict).
    Works on the old schema (blocks only, policy None) and the new one ("policy" and "meta" keys)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    pol, meta = doc.get("policy"), doc.get("meta") or {}
    blocks = {k: v for k, v in doc.items() if k not in ("policy", "meta")}
    return blocks, pol, meta


def ref_block_counts(blocks: dict, k_per_km2: float, k_rule: str = "global") -> pd.DataFrame:
    """Per-block hits at K from reference tables. Same ranking rule as the scorer. per_group needs 'fold'."""
    rows = [{"block_id": int(b), "score": c["score"], "area_m2": c["area_m2"], "cand_id": c["blob_id"],
             "matched": c["truth_id"]} for b, v in blocks.items() for c in v["cands"]]
    df = pd.DataFrame(rows, columns=["block_id", "score", "area_m2", "cand_id", "matched"])
    area = sum(v["km2"] for v in blocks.values())
    garea = None
    if k_rule == "per_group":
        fold = {int(b): v.get("fold") for b, v in blocks.items()}
        if any(f is None for f in fold.values()):
            raise ValueError("per_group reference counts need a fold per block (new table schema)")
        df["group"] = df.block_id.map(fold)
        garea = {}
        for b, v in blocks.items():
            garea[v["fold"]] = garea.get(v["fold"], 0.0) + v["km2"]
    keep = rank_keep(df, k_per_km2, area, k_rule, garea)
    hit = df[keep & df.matched.notna()].groupby("block_id").matched.nunique()
    out = pd.DataFrame({"block_id": [int(b) for b in blocks], "n_truth": [int(v["n_truth"]) for v in blocks.values()],
                        "area_km2": [float(v["km2"]) for v in blocks.values()]})
    out["hits"] = out.block_id.map(hit).fillna(0).astype(int)
    return out


# ----------------------------------------------------------------------------- checkpoint lineage (review F08)
def checkpoint_record(model_dir: Path, policy_name: str, task: str, *, provisional_reasons: list[str] | None = None) -> dict:
    """Lineage of the model that made a probability raster. lineage 'isolated' only for P1 isolated trainers
    (directory name holds 'iso'). Any reason makes it provisional. Historical CV5 is always provisional."""
    md = Path(model_dir)
    family = f"{md.parent.name}/{md.name}"
    lineage = "isolated" if "iso" in md.name else "historical_cv5"
    reasons = list(provisional_reasons or [])
    if lineage != "isolated":
        reasons.append("original CV5 sampler, not P1 isolated (protocol section 3)")
    folds = sorted(int(p.parent.name[4:]) for p in md.glob("fold*/best.pt"))
    if policy_name.startswith("single_fold:"):
        folds = [int(policy_name.split(":")[1])]
    sha = {str(k): ek.sha256(md / f"fold{k}" / "best.pt") for k in folds if (md / f"fold{k}" / "best.pt").exists()}
    return {"task": task, "family": family, "model_dir": str(md), "policy": policy_name, "lineage": lineage,
            "provisional": bool(reasons), "provisional_reasons": reasons, "sha256": sha}


def confirmatory_ok(reference_ckpt: dict | None, target_ckpt: dict | None) -> tuple[bool, list[str]]:
    """A transfer verdict needs an isolated, non-provisional reference and target of the same family."""
    why = []
    for name, c in (("reference", reference_ckpt), ("target", target_ckpt)):
        if not c:
            why.append(f"{name} has no checkpoint lineage record")
            continue
        if c.get("lineage") != "isolated":
            why.append(f"{name} checkpoint lineage is {c.get('lineage')}, not isolated")
        if c.get("provisional"):
            why.append(f"{name} checkpoint is provisional ({'; '.join(c.get('provisional_reasons') or [])})")
    if reference_ckpt and target_ckpt and reference_ckpt.get("family") != target_ckpt.get("family"):
        why.append(f"model family differs: reference {reference_ckpt.get('family')} vs target {target_ckpt.get('family')}")
    return not why, why


# ----------------------------------------------------------------------------- preregistration
PREREG_RE = re.compile(r"```json prereg\s*\n(.*?)\n```", re.S)


def read_prereg(md_path: Path) -> dict:
    """The machine-readable block of a filled preregistration (written by `_transfer_prereg_fill.py`)."""
    txt = Path(md_path).read_text(encoding="utf-8")
    m = PREREG_RE.search(txt)
    if not m:
        raise ValueError(f"{md_path}: no ```json prereg``` block. Fill it with _transfer_prereg_fill.py")
    return json.loads(m.group(1))


def prereg_policy(pr: dict) -> tuple[dict, str, dict | None]:
    """(declared policy dict, declared dedupe, declared checkpoint) from a preregistration block.
    Every scoring setting must be declared. A missing one raises (review G-06)."""
    sc = pr.get("scoring") or {}
    task = sc.get("task") or pr.get("task")
    miss = [k for k in ("cutoff", "iou", "dedupe", "k") if sc.get(k) is None]
    if not task:
        miss.append("task")
    if miss:
        raise ValueError(f"preregistration does not declare scoring.{miss}. Add them before scoring.")
    pol = policy(task, sc.get("mode", "primary"), cutoff=float(sc["cutoff"]), iou=float(sc["iou"]),
                 min_area_m2=float(sc["min_area_m2"]) if sc.get("min_area_m2") is not None else None,
                 match_order=sc.get("order"), k_per_km2=float(sc["k"]))
    return pol, str(sc["dedupe"]), pr.get("checkpoint")


def check_prereg_against(pr: dict, run_policy: dict, run_dedupe: str, run_ckpt: dict | None, label: str) -> None:
    """Declared cutoff, IoU, dedupe, K and checkpoint must equal what a run used. Raises on any difference."""
    pol, dd, ck = prereg_policy(pr)
    if run_policy is None:
        raise AssertionError(f"{label} carries no policy stamp. Re-score it with the current scorer.")
    ek.assert_same_policy(pol, run_policy, keys=POLICY_KEYS)
    if dd != run_dedupe:
        raise AssertionError(f"dedupe declared {dd}, {label} used {run_dedupe}")
    if ck is not None:
        if not run_ckpt:
            raise AssertionError(f"{label} has no checkpoint record, preregistration declares one")
        for k in ("family", "lineage"):
            if ck.get(k) is not None and ck.get(k) != run_ckpt.get(k):
                raise AssertionError(f"checkpoint {k} declared {ck.get(k)}, {label} has {run_ckpt.get(k)}")
        if ck.get("sha256") and run_ckpt.get("sha256") and ck["sha256"] != run_ckpt["sha256"]:
            raise AssertionError(f"checkpoint hashes declared in the preregistration differ from {label}")
