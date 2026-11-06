"""5.5 geometry and statistics helpers for pad area agreement. Library, not a script.

Purpose
    - load_pred / load_drawn: model pad polygons and annotated pads under one boundary definition (pits removed from
      both when subtract_pits is set, so model and reference follow the same rule, fw_5_5 QC 5)
    - match_one_to_one: greedy one-to-one match by descending model score (policy match_order). Rule
      overlap_any (primary since 2026-11-06, review 5.5-01) accepts any positive overlap, so it never truncates
      the area error. Rule iou_gate (IoU >= policy iou, 0.3) is the sensitivity. An IoU gate caps
      |ln(A_hat / A_ref)| at ln(1 / 0.3) = 1.204 for nested shapes, so it drops exactly the pads with large area error.
    - per_pad: per-pad A_hat, A_ref, IoU, log ratio, merged and split flags under one match rule
    - road_length: annotated access-road length within road_window_m of each pad edge (L_road of the cost model)
    - boundary_dist: mean symmetric boundary distance and its 95th percentile (Hausdorff 95)
    - median_r_interval: block bootstrap of the median log ratio (pads in one block are one cluster)
    - area_decision: the fw_5_5 section 8 decision on the median interval and P90 |r|
Inputs / outputs
    None. GeoDataFrames in, DataFrames and dicts out.
Run
    Not runnable. Tested by expansions/5_tasks/5_5_polygon_area_cost/src/test_5_5.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

ek = th.ek


def clean(g):
    g = g.copy()
    g["geometry"] = g.geometry.buffer(0)
    return g[~g.geometry.is_empty & g.geometry.notna()].reset_index(drop=True)


def remove_pits(g, pits):
    if pits is None or not len(pits):
        return g
    u = pits.geometry.union_all()
    g = g.copy()
    g["geometry"] = g.geometry.difference(u)
    return clean(g)


def load_pred(cfg):
    ent = cfg["inputs"]["pad_products"]
    pred = clean(th.read_vector(th.inp(cfg, "pad_products"), layer=ent.get("layer", "model_geometry") if isinstance(ent, dict) else "model_geometry"))
    th.require_columns(pred, ["score"], "pad products")
    want = float(ek.policy_for("pad")["cutoff"])              # 0.525, user accepted 2026-11-06
    if "thr_used" not in pred.columns:
        raise SystemExit("CUTOFF UNKNOWN [pad products]: no thr_used column. Use the 5.6 policy re-cut "
                         "(_records_policy_recut_9t.py)")
    got = sorted(set(np.round(pred["thr_used"].astype(float), 6)))
    if got != [round(want, 6)]:
        raise SystemExit(f"CUTOFF MISMATCH [pad products]: cut at {got}, policy cutoff is {want}")
    return pred


def load_roads(cfg):
    """Annotated road lines, or None when the annotation file has no roads layer. road_scope all_mapped (the only
    rule, user accepted 2026-11-06) keeps every mapped road, through roads included. No road is filtered out."""
    import pyogrio
    if cfg.get("road_scope", "all_mapped") != "all_mapped":
        raise SystemExit(f"road_scope {cfg.get('road_scope')!r} is not implemented. Only all_mapped is.")
    ann = th.inp(cfg, "annotations")
    if "roads" not in [r[0] for r in pyogrio.list_layers(ann)]:
        return None
    return th.read_vector(ann, layer="roads")


def rel(p) -> str:
    """Repo-relative path for outputs (no absolute paths in written files)."""
    p = Path(p).resolve()
    try:
        return p.relative_to(ek.REPO.resolve()).as_posix()
    except ValueError:
        return p.name


def load_drawn(cfg):
    ann = th.inp(cfg, "annotations")
    plat = clean(th.read_vector(ann, layer="plat"))
    pits = clean(th.read_vector(ann, layer="pit_inside")) if cfg.get("subtract_pits") else None
    return plat, pits


MATCH_RULES = ("overlap_any", "iou_gate")


def match_one_to_one(pred, ref, rule: str = "overlap_any", iou_min: float = 0.3):
    """Greedy one-to-one, model polygons in descending score (ties by larger area, then row). Each takes the unused
    reference pad with the highest IoU among those it overlaps with positive area. iou_gate also needs IoU >= iou_min.
    Returns (ref row or -1, IoU) per model row."""
    if rule not in MATCH_RULES:
        raise ValueError(f"unknown match rule {rule!r}, expected one of {MATCH_RULES}")
    sidx = ref.sindex
    rg = ref.geometry.values
    area = pred.geometry.area.to_numpy()
    order = np.lexsort((np.arange(len(pred)), -area, -pred["score"].to_numpy()))
    used = set()
    tid = np.full(len(pred), -1, int)
    best = np.zeros(len(pred))
    for i in order:
        g = pred.geometry.iloc[i]
        cands = []
        for j in sidx.query(g, predicate="intersects"):
            if int(j) in used:
                continue
            inter = g.intersection(rg[j]).area
            if inter <= 0:
                continue
            iou = inter / (g.area + rg[j].area - inter)
            if rule == "iou_gate" and iou < iou_min:
                continue
            cands.append((iou, -int(j)))
        if cands:
            iou, nj = max(cands)
            used.add(-nj)
            tid[i], best[i] = -nj, iou
    return tid, best


def road_length(ref, roads, window_m: float) -> np.ndarray:
    """Length (m) of annotated road lines inside the ring from each pad edge out to window_m (fw_5_5 L_road,
    'access road within 30 m of the pad edge'). NaN for every pad when no road layer is held."""
    if roads is None:
        return np.full(len(ref), np.nan)
    if not len(roads):
        return np.zeros(len(ref))
    rs = roads.sindex
    rgeo = roads.geometry.values
    out = np.zeros(len(ref))
    for k, g in enumerate(ref.geometry):
        ring = g.buffer(window_m).difference(g)
        idx = rs.query(ring, predicate="intersects")
        out[k] = float(sum(rgeo[j].intersection(ring).length for j in idx))
    return out


def per_pad(pred, ref, ref_id: str = "pad_id", iou_min: float = 0.3, merge_frac: float = 0.2,
            rule: str = "overlap_any") -> pd.DataFrame:
    """One row per reference pad. Matched pads carry A_hat from their one-to-one model polygon."""
    tid, iou = match_one_to_one(pred, ref, rule, iou_min)
    mp = {int(j): i for i, j in enumerate(tid) if j >= 0}
    # merged: a model polygon covering >= merge_frac of two or more reference pads
    # split:  a reference pad covered >= merge_frac by two or more model polygons (each share of the model polygon)
    rsx, psx = ref.sindex, pred.sindex
    n_ref_hit = np.zeros(len(pred), int)
    for i, g in enumerate(pred.geometry):
        for j in rsx.query(g, predicate="intersects"):
            if g.intersection(ref.geometry.iloc[j]).area >= merge_frac * ref.geometry.iloc[j].area:
                n_ref_hit[i] += 1
    rows = []
    for j, g in enumerate(ref.geometry):
        n_pred = sum(1 for i in psx.query(g, predicate="intersects")
                     if pred.geometry.iloc[i].intersection(g).area >= merge_frac * pred.geometry.iloc[i].area)
        i = mp.get(j)
        a_ref = g.area
        a_hat = pred.geometry.iloc[i].area if i is not None else np.nan
        rows.append(dict(pad_id=ref[ref_id].iloc[j] if ref_id in ref else j, ref_row=j,
                         pred_row=i if i is not None else -1, A_ref=a_ref, A_hat=a_hat,
                         iou=float(iou[i]) if i is not None else 0.0,
                         log_ratio=float(np.log(a_hat / a_ref)) if i is not None and a_ref > 0 else np.nan,
                         merged=int(i is not None and n_ref_hit[i] > 1), split=int(n_pred > 1),
                         matched=int(i is not None), match_rule=rule))
    T = pd.DataFrame(rows)
    T["abs_pct_err"] = (T.A_hat - T.A_ref).abs() / T.A_ref
    return T


def _boundary_points(geom, step):
    b = geom.boundary
    L = b.length
    if L == 0:
        return np.empty((0, 2))
    d = np.arange(0, L, step)
    pts = [b.interpolate(x) for x in d]
    return np.array([[p.x, p.y] for p in pts])


def boundary_dist(a, b, step: float = 1.0) -> tuple[float, float]:
    """Mean symmetric boundary distance and its 95th percentile (Hausdorff 95), in metres."""
    from shapely import points, distance
    pa, pb = _boundary_points(a, step), _boundary_points(b, step)
    if not len(pa) or not len(pb):
        return float("nan"), float("nan")
    da = distance(points(pa), b.boundary)
    db = distance(points(pb), a.boundary)
    allv = np.r_[da, db]
    return float(np.mean(allv)), float(np.percentile(allv, 95))


def median_r_interval(T: pd.DataFrame, B: int, seed: int):
    x = T.dropna(subset=["log_ratio"])
    blocks = sorted(x.block_id.unique())
    by = {b: x.loc[x.block_id == b, "log_ratio"].to_numpy() for b in blocks}

    def med(bl):
        v = np.concatenate([by[b] for b in bl]) if bl else np.array([])
        return float(np.median(v)) if len(v) else float("nan")

    def p90(bl):
        v = np.concatenate([by[b] for b in bl]) if bl else np.array([])
        return float(np.percentile(np.abs(v), 90)) if len(v) else float("nan")
    m = ek.block_bootstrap(med, blocks, B=B, seed=seed)
    q = ek.block_bootstrap(p90, blocks, B=B, seed=seed + 1)
    return dict(median_r=m[0], median_lo=m[1], median_hi=m[2], p90_abs_r=q[0], p90_lo=q[1], p90_hi=q[2],
                n_pads=int(len(x)), n_blocks=len(blocks), few_blocks=len(blocks) < 15)


def delta_area(tol: float, f, fallback: float) -> float:
    """fw_5_5 section 8 proposal. delta = ln(1 + tol / f). Without f (no cost table) use the configured fallback."""
    if f is None or f <= 0:
        return float(fallback)
    return float(np.log(1 + tol / f))


def area_decision(s: dict, delta: float, tol: float) -> str:
    inside = s["median_lo"] > -delta and s["median_hi"] < delta
    p90_ok = s["p90_abs_r"] <= np.log(1 + tol)
    if inside and p90_ok:
        return "success"
    if s["median_lo"] > delta or s["median_hi"] < -delta:
        return "failure"
    return "inconclusive"
