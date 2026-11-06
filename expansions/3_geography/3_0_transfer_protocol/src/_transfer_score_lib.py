"""3.0 core. One deterministic scorer for recall at K per km2 on 9t and on every target area.

Purpose
    Probability raster + scored footprint + blocks + annotated features in, recall at K with a block
    bootstrap, density, a density-scaled secondary, calibration and per-block counts out. The same functions
    score 9t and targets. `module_sha256()` lets every run record the code it used (3.0 QC).

Steps (fw_3_0 S1, fw_00 section 4)
    1. Read blocks and footprint, assert EPSG:6346. Eligible blocks are complete blocks inside the footprint,
       minus edge blocks (any part outside valid raster data) and blocks whose void fraction exceeds the cap.
    2. Polygonise the raster at the proposal cutoff, drop blobs under 4 m2, score by mean probability. The
       harness default is the sweep's cutoff per task (config_3_0.json cutoff_by_task, pit 0.35). fw_00's 0.10
       is a sensitivity. It merges blobs and fails IoU matching (decisions_3_0.md).
       This is `polygonize` from `notebooks/wellsight_v2/s5_eval/_threshold_common.py`, imported.
    3. Keep candidates whose centroid lies in an eligible block. Truth features likewise by centroid.
    4. Greedy 1:1 IoU matching at 0.3 over all kept candidates. Pair order is by candidate score, as in
       `_cv5_pr_sweep_records_pit_pad_9t.match_objects` that produced the 9t reference (`order="score"`).
       `order="iou"` follows the fw_00 wording and is a sensitivity (decisions_3_0.md).
    5. Dedupe. An unmatched candidate whose centroid is inside a matched truth feature is a second piece of one
       feature. It is dropped before ranking. This rule reads truth, so it is a scoring rule, not a deployment
       rule (`dedupe="none"` turns it off).
    6. Rank by score, ties by larger area then lower candidate id. Keep the top K. K = round(k_per_km2 * area)
       pooled (`k_rule="global"`), or floor(k_per_km2 * group area) per group (`k_rule="per_group"`, the
       archival sweep's per-fold rule).
    7. Recall = matched truth features in the kept set over all eligible truth features. Hits are credited to
       the truth feature's block. Block bootstrap of pooled counts (B = 2000), percentile 95% interval.
       Fewer than 15 blocks also gets a permutation-style sign-flip interval and a warning.
    8. Secondary. K2 = c * truth density per km2, c from the preregistration.
    9. Calibration. Pixel level (raw probability against the rasterised truth, sampled) and candidate level
       (score against matched). Brier, log loss, ECE with 10 equal-mass bins (ek.calibration).

Inputs
    any probability raster (float 0-1, or uint8 DN / 254 with 255 nodata), blocks GeoPackage (layer `blocks`,
    column `block_id`), truth layer, optional footprint polygon and void-fraction raster

Outputs
    None. Library only. `_transfer_score_run.py` writes the files.

Run
    Not a script. `python -m pytest -q expansions/3_geography/3_0_transfer_protocol/src/test_3_0.py -p no:cacheprovider`
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

CUTOFF, MIN_AREA, IOU = 0.10, 4.0, 0.3


def module_sha256() -> str:
    return hashlib.sha256(HERE.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- reading
def read_prob(path: Path, scale: str = "auto"):
    """Returns (prob float32 with NaN nodata, transform, crs). uint8 rasters are DN / 254, 255 nodata."""
    import rasterio
    with rasterio.open(path) as r:
        ek.assert_crs(r)
        a = r.read(1)
        nd = r.nodata
        tf, crs = r.transform, r.crs
    if a.dtype == np.uint8 and scale in ("auto", "dn254"):
        valid = a != (255 if nd is None else int(nd))
        p = np.where(valid, a.astype(np.float32) / 254.0, np.nan).astype(np.float32)
    else:
        p = a.astype(np.float32)
        if nd is not None:
            p[p == nd] = np.nan
        if np.nanmax(p) > 1.0 + 1e-6 or np.nanmin(p) < -1e-6:
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
def eligible_blocks(blocks, prob, tf, footprint=None, void=None, void_cap: float | None = None,
                    drop_edge: bool = True):
    """blocks with columns block_id, area_km2, edge, void_frac, eligible. Complete blocks only."""
    from rasterio.features import rasterize
    b = blocks.copy()
    b["block_id"] = b.block_id.astype(int)
    lab = rasterize([(g, i + 1) for i, g in enumerate(b.geometry)], out_shape=prob.shape, transform=tf,
                    fill=0, dtype="int32")
    cell = abs(tf.a * tf.e)
    n_cells = np.bincount(lab.ravel(), minlength=len(b) + 1)[1:]
    n_valid = np.bincount(lab.ravel(), weights=np.isfinite(prob).ravel(), minlength=len(b) + 1)[1:]
    expect = (b.geometry.area / cell).to_numpy()
    b["coverage"] = n_valid / np.maximum(expect, 1)
    b["edge"] = (n_cells < 0.999 * expect) | (n_valid < n_cells)
    if void is not None:
        vsum = np.bincount(lab.ravel(), weights=np.nan_to_num(void).ravel(), minlength=len(b) + 1)[1:]
        b["void_frac"] = vsum / np.maximum(n_cells, 1)
    else:
        b["void_frac"] = np.nan
    inside = np.ones(len(b), bool)
    if footprint is not None:
        fu = footprint.to_crs(b.crs).geometry.union_all()
        inside = np.array([fu.buffer(1e-6).contains(g) for g in b.geometry])
    b["in_footprint"] = inside
    b["eligible"] = inside & (~b.edge if drop_edge else True)
    if void_cap is not None and void is not None:
        b["eligible"] &= b.void_frac <= void_cap
    b["area_km2"] = b.geometry.area / 1e6
    return b


def assign_blocks(gdf, blocks):
    """block_id of each geometry's centroid (NaN outside)."""
    import geopandas as gpd
    if not len(gdf):
        return pd.Series([], dtype=float)
    c = gpd.GeoDataFrame(geometry=gdf.geometry.centroid, crs=gdf.crs)
    j = gpd.sjoin(c, blocks[["block_id", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    return j["block_id"].reindex(gdf.index)


# ----------------------------------------------------------------------------- candidates and matching
def candidates(prob, tf, crs, cutoff: float = CUTOFF, min_area: float = MIN_AREA):
    from _threshold_common import polygonize
    c = polygonize(np.nan_to_num(prob, nan=0.0), tf, crs, cutoff, min_area)
    c["area_m2"] = c.geometry.area
    c["cand_id"] = np.arange(len(c))
    return c


def match_greedy(truth, cands, iou: float = IOU, order: str = "score"):
    """1:1 greedy. Returns (truth_id matched per candidate or None, set of matched truth ids)."""
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
    mt = set(m for m in matched if m is not None)
    if not mt or not len(cands):
        return np.zeros(len(cands), bool)
    mg = truth[truth.truth_id.isin(mt)]
    import geopandas as gpd
    cen = gpd.GeoDataFrame(geometry=cands.geometry.centroid, crs=cands.crs)
    j = gpd.sjoin(cen, mg[["geometry"]], how="inner", predicate="within")
    inside = np.zeros(len(cands), bool)
    inside[np.unique(j.index.to_numpy())] = True
    return inside & np.array([m is None for m in matched])


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
    hit_ids = set(m for m, k in zip(cands["matched"], keep) if k and m is not None)
    t = truth.assign(hit=truth.truth_id.isin(hit_ids))
    g = t.groupby("block_id").agg(n_truth=("truth_id", "size"), hits=("hit", "sum"))
    kc = pd.Series(cands["block_id"].to_numpy()[keep]).value_counts()
    out = pd.DataFrame({"block_id": eb.block_id.astype(int).to_numpy(), "area_km2": eb.area_km2.to_numpy()})
    out["n_truth"] = out.block_id.map(g.n_truth).fillna(0).astype(int)
    out["hits"] = out.block_id.map(g.hits).fillna(0).astype(int)
    out["kept"] = out.block_id.map(kc).fillna(0).astype(int)
    return out


def pooled_recall(tab: pd.DataFrame):
    def stat(rows):
        rows = list(rows)
        n = sum(r[1] for r in rows)
        return sum(r[0] for r in rows) / n if n else float("nan")
    return stat


def bootstrap(tab: pd.DataFrame, B: int, seed: int) -> dict:
    rows = list(zip(tab.hits, tab.n_truth))
    point, lo, hi, _ = ek.block_bootstrap(pooled_recall(tab), rows, B=B, seed=seed)
    out = {"recall": point, "lo": lo, "hi": hi, "B": B, "seed": seed, "n_blocks": len(rows)}
    if len(rows) < 15:
        out["warning"] = "fewer than 15 blocks. The bootstrap is unreliable. See the sign-flip interval."
        out["signflip"] = signflip_interval(tab, B, seed)
    return out


def signflip_interval(tab: pd.DataFrame, B: int, seed: int) -> list[float]:
    """Interval for pooled recall from random sign flips of block residuals about the pooled ratio."""
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
          cutoff: float = CUTOFF, min_area: float = MIN_AREA, iou: float = IOU, order: str = "score",
          dedupe: str = "truth_matched", k_rule: str = "global", group_of_block: dict | None = None,
          density_c: float | None = None, B: int = 2000, seed: int = 0, k_curve=(10, 20, 30, 40, 50, 60, 70, 80),
          calib_pixels: int = 2_000_000, drop_edge: bool = True) -> dict:
    """Full S1 scoring. Returns dict(summary, blocks, candidates)."""
    import geopandas as gpd
    prob, tf, crs = read_prob(prob_path)
    blocks = gpd.read_file(blocks_path, layer="blocks") if str(blocks_path).endswith(".gpkg") else gpd.read_file(blocks_path)
    ek.assert_crs(blocks)
    ek.assert_unique(blocks, "block_id")
    fp = gpd.read_file(footprint_path) if footprint_path else None
    void = None
    if void_path:
        void, void_tf, void_crs = read_prob(void_path, scale="none")
        if void.shape != prob.shape or void_tf != tf or void_crs != crs:
            raise ValueError("void and probability rasters must have identical CRS, shape and pixel transform")
    eb = eligible_blocks(blocks, prob, tf, fp, void, void_cap, drop_edge)
    el = eb[eb.eligible]
    area = float(el.area_km2.sum())
    if not len(el):
        raise AssertionError("no eligible blocks in the footprint")
    if not np.isclose(area, el.geometry.area.sum() / 1e6):
        raise AssertionError("footprint area differs from the sum of block areas")
    truth = read_truth(truth_spec, crs, truth_id)
    truth["block_id"] = assign_blocks(truth, el)
    truth = truth[truth.block_id.notna()].copy()
    truth["block_id"] = truth.block_id.astype(int)
    ek.assert_unique(truth, "truth_id")
    c = candidates(prob, tf, crs, cutoff, min_area)
    c["block_id"] = assign_blocks(c, el)
    c = c[c.block_id.notna()].reset_index(drop=True)
    c["block_id"] = c.block_id.astype(int)
    c["matched"], _ = match_greedy(truth, c, iou, order)
    c["duplicate"] = dedupe_mask(c, truth, list(c["matched"])) if dedupe == "truth_matched" else False
    ranked = c[~c.duplicate].reset_index(drop=True)
    if k_rule == "per_group":
        ranked["group"] = ranked.block_id.map(group_of_block)
        garea = el.assign(g=el.block_id.map(group_of_block)).groupby("g").area_km2.sum().to_dict()
    else:
        garea = None
    keep = rank_keep(ranked, k_per_km2, area, k_rule, garea)
    tab = per_block_counts(ranked, keep, truth, eb)
    boot = bootstrap(tab, B, ek.child_seed(seed, 0, 0))
    n_truth = int(tab.n_truth.sum())
    dens = n_truth / area
    rk = None
    if k_rule == "global":   # independent check with the shared expkit implementation
        rk = ek.recall_at_k(ranked.score, ranked.matched, ranked.block_id, dict(zip(tab.block_id, tab.n_truth)),
                            area, k_per_km2, areas=ranked.area_m2, cand_ids=ranked.cand_id)
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
    summary = {
        "k_per_km2": k_per_km2, "k_rule": k_rule, "k_total": int(keep.sum()),
        "k_expected": int(round(k_per_km2 * area)) if k_rule == "global" else None,
        "eligible_area_km2": area, "n_blocks_eligible": int(len(el)), "n_blocks_total": int(len(eb)),
        "edge_blocks": sorted(eb[eb.edge].block_id.astype(int).tolist()),
        "n_truth": n_truth, "truth_density_per_km2": dens, "n_candidates": int(len(c)),
        "n_duplicates_dropped": int(c.duplicate.sum()), "hits": int(tab.hits.sum()),
        "primary": boot, "recall_at_k_expkit": rk, "secondary_density_scaled": sec, "recall_vs_k": curve,
        "calibration_pixels": calibration_pixels(prob, truth, tf, valid, calib_pixels, seed),
        "calibration_candidates": ek.calibration(ranked.matched.notna().astype(float), ranked.score) if len(ranked) else {},
        "params": {"cutoff": cutoff, "min_area_m2": min_area, "iou": iou, "order": order, "dedupe": dedupe,
                   "void_cap": void_cap, "drop_edge": drop_edge, "B": B, "seed": seed},
        "module_sha256": module_sha256(),
    }
    return {"summary": summary, "blocks": tab.merge(eb[["block_id", "edge", "void_frac", "coverage"]], on="block_id"),
            "candidates": ranked.assign(kept=keep)}


# ----------------------------------------------------------------------------- preregistration
PREREG_RE = re.compile(r"```json prereg\s*\n(.*?)\n```", re.S)


def read_prereg(md_path: Path) -> dict:
    """The machine-readable block of a filled preregistration (written by `_transfer_prereg_fill.py`)."""
    txt = Path(md_path).read_text(encoding="utf-8")
    m = PREREG_RE.search(txt)
    if not m:
        raise ValueError(f"{md_path}: no ```json prereg``` block. Fill it with _transfer_prereg_fill.py")
    return json.loads(m.group(1))
