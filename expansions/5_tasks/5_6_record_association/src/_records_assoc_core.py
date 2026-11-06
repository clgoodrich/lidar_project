"""Record-association core for 5.6 (and reused by 5.3, 5.4). Library, not a script.

Purpose
    Pure functions behind the corrected association analysis of protocol section 4.
    - dedupe(): prediction-only geometric dedupe of the full detector output (no truth read, review F15)
    - assign_det_ids(): seeded random det_id, pit from 1, pad from 1000001 (review 5.6-01)
    - nn_rates(), pad_rates(): share of records with a feature within r
    - shift_null(): translate the whole record set as one, redraw shifts that lose records
    - excess(): normalised excess association over the null, with a null-based interval. Not PPV.
    - assign(): global one-to-one Hungarian across statuses, or per-status competing proposals
    - mde(): minimum detectable excess (power report, S3)
    - link_ppv_bounds(): link PPV from a blinded, weighted adjudication sample, ambiguous kept in the gap

Definitions (fw_5_6 section 3)
    normalised excess = (observed - null mean) / (1 - null mean). 0 is chance, 1 is every record matched beyond chance.
    Its interval uses the null's 2.5 and 97.5 percentiles. It is not link precision.

Inputs / outputs
    None. Numpy arrays and GeoDataFrames in, dicts and arrays out.
Run
    Not runnable. Tested by expansions/5_tasks/5_6_record_association/src/test_5_6.py.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

BIG = 1e9


# ----------------------------------------------------------------------------- input contract
DET_ID_BASE = {"pit": 1, "pad": 1_000_001}
DET_ID_POLICY = ("det_id = base + seeded random permutation of a prediction-only canonical order "
                 "(cx, cy, score, area). pit base 1, pad base 1000001. Encodes neither match status nor score "
                 "(review 5.6-01).")


def _union_find(n: int, pairs) -> np.ndarray:
    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, j in pairs:
        ri, rj = find(int(i)), find(int(j))
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)
    roots = np.array([find(i) for i in range(n)], int)
    return np.unique(roots, return_inverse=True)[1] if n else roots


def canonical_order(df) -> np.ndarray:
    """Row order from prediction-only keys: cx, cy, then score descending, then area descending.
    No truth column is read, so the order is invariant to annotations."""
    area = df["area_m2"].to_numpy(float) if "area_m2" in df else (
        df.geometry.area.to_numpy() if hasattr(df, "geometry") else np.zeros(len(df)))
    if "cx" in df:
        x, y = df["cx"].to_numpy(float), df["cy"].to_numpy(float)
    else:
        c = df.geometry.centroid
        x, y = np.round(c.x.to_numpy(), 2), np.round(c.y.to_numpy(), 2)
    return np.lexsort((-area, -df["score"].to_numpy(float), y, x))


def dedupe(gdf, rule: str = "geometric", gap_m: float = 2.0):
    """Prediction-only dedupe of the full detector output (review F15).

    geometric  blobs whose polygons lie within gap_m of each other form one cluster (single linkage). The
               cluster keeps its highest-scoring member (ties by larger area, then canonical order). Only the
               predicted geometry and score are read. No truth layer or truth-derived flag is consulted.
    keep_all   keep every row (sensitivity).
    'deployment' (the old rule on dup_on_pit) read already-drawn pit truth and is refused.
    Adds n_merged (cluster size) to the kept rows.
    """
    if rule == "deployment":
        raise ValueError("dedupe rule 'deployment' read the truth-derived dup_on_pit flag (review F15). "
                         "Use 'geometric' (prediction-only) or 'keep_all'.")
    if rule == "keep_all":
        out = gdf.copy()
        out["n_merged"] = 1
        return out
    if rule != "geometric":
        raise ValueError(f"unknown dedupe rule {rule!r}")
    g = gdf.reset_index(drop=True)
    n = len(g)
    if n == 0:
        out = g.copy()
        out["n_merged"] = []
        return out
    geoms = g.geometry.values
    from shapely import STRtree
    i, j = STRtree(geoms).query(geoms, predicate="dwithin", distance=float(gap_m))
    k = i < j
    lab = _union_find(n, zip(i[k], j[k]))
    canon_rank = np.empty(n, int)
    canon_rank[canonical_order(g)] = np.arange(n)
    area = g["area_m2"].to_numpy(float) if "area_m2" in g else g.geometry.area.to_numpy()
    order = np.lexsort((canon_rank, -area, -g["score"].to_numpy(float), lab))
    first = np.r_[True, lab[order][1:] != lab[order][:-1]]
    keep = order[first]
    sizes = np.bincount(lab)
    out = g.iloc[np.sort(keep)].copy()
    out["n_merged"] = sizes[lab[np.sort(keep)]]
    return out


def assign_det_ids(df, kind: str, seed: int) -> np.ndarray:
    """det_id for each row of one detector file (review 5.6-01).
    Canonical prediction-only order, then a seeded random permutation, plus the kind's base."""
    if kind not in DET_ID_BASE:
        raise ValueError(kind)
    n = len(df)
    rank = np.empty(n, int)
    rank[canonical_order(df)] = np.arange(n)
    perm = np.random.default_rng(int(seed)).permutation(n)
    return DET_ID_BASE[kind] + perm[rank]


# ----------------------------------------------------------------------------- rates
def nn_dist(rec_xy: np.ndarray, det_xy: np.ndarray) -> np.ndarray:
    if len(det_xy) == 0:
        return np.full(len(rec_xy), np.inf)
    d, _ = cKDTree(det_xy).query(rec_xy)
    return d


def nn_rates(rec_xy: np.ndarray, det_xy: np.ndarray, radii) -> dict:
    """Share of records with any detection within r (many-to-one, the chance-matching rate)."""
    if len(rec_xy) == 0:
        return {r: float("nan") for r in radii}
    d = nn_dist(rec_xy, det_xy)
    return {r: float((d <= r).mean()) for r in radii}


def pad_rate_fn(pad_geoms, radii):
    """Rate function with the polygon tree built once (used inside the null loop)."""
    from shapely import STRtree
    tree = STRtree(np.asarray(pad_geoms))
    return lambda xy: pad_rates(xy, None, radii, tree=tree)


def pit_rate_fn(det_xy, radii):
    tree = cKDTree(det_xy) if len(det_xy) else None

    def f(xy):
        if len(xy) == 0:
            return {r: float("nan") for r in radii}
        d = tree.query(xy)[0] if tree is not None else np.full(len(xy), np.inf)
        return {r: float((d <= r).mean()) for r in radii}
    return f


def pad_rates(rec_xy: np.ndarray, pad_geoms, radii, tree=None) -> dict:
    """Share of records inside (r = 0) or within r of a pad polygon. Many records may share one pad."""
    from shapely import STRtree, points
    if len(rec_xy) == 0:
        return {r: float("nan") for r in radii}
    tree = tree if tree is not None else STRtree(np.asarray(pad_geoms))
    pts = points(rec_xy)
    out = {}
    for r in radii:
        if r == 0:
            idx = tree.query(pts, predicate="intersects")
        else:
            idx = tree.query(pts, predicate="dwithin", distance=r)
        out[r] = float(len(np.unique(idx[0])) / len(rec_xy))
    return out


# ----------------------------------------------------------------------------- null
def shift_null(rec_xy: np.ndarray, eligible, rate_fn, n_shift: int = 300, dmin: float = 200.0,
               dmax: float = 500.0, max_loss: float = 0.10, rng=None, max_tries: int = 20, wrap_bbox=None):
    """Translate the whole record set as one (protocol section 4 rule 4).

    eligible(xy) -> bool mask, the same rule as the observed records (footprint and tile).
    rate_fn(xy)  -> dict radius -> rate.
    wrap_bbox    (x0, y0, x1, y1). When given the shift is toroidal. A record pushed past one edge re-enters at
                 the opposite edge, so no record leaves the tile and every direction is accepted equally
                 (review 5.6-02). Records then drop only where the footprint has holes inside the tile.
    A shift that drops more than max_loss of the records is rejected and redrawn (up to max_tries per draw).
    Returns dict(draws, retained, rejected, n_records, angles_tried, accepted_tried, direction).
    direction holds the acceptance share per 45 degree sector of every attempted shift. Unequal shares mean the
    accepted shifts favour some directions, which biases the null.
    What it conditions on: the record set's internal clustering and size. Gradients in oil development and
    road density are only partly preserved by a 200 to 500 m move. A toroidal wrap also joins opposite edges.
    """
    rng = rng if rng is not None else np.random.default_rng(0)
    rec_xy = np.asarray(rec_xy, float).reshape(-1, 2)
    n = len(rec_xy)
    draws, retained, rejected, tried, acc = [], [], 0, [], []
    for _ in range(n_shift):
        for _t in range(max_tries):
            a = rng.uniform(0, 2 * np.pi)
            m = rng.uniform(dmin, dmax)
            sh = rec_xy + np.array([m * np.cos(a), m * np.sin(a)])
            if wrap_bbox is not None:
                x0, y0, x1, y1 = wrap_bbox
                sh[:, 0] = x0 + np.mod(sh[:, 0] - x0, x1 - x0)
                sh[:, 1] = y0 + np.mod(sh[:, 1] - y0, y1 - y0)
            ok = eligible(sh)
            tried.append(a)
            if n and (1 - ok.mean()) <= max_loss:
                draws.append(rate_fn(sh[ok]))
                retained.append(int(ok.sum()))
                acc.append(True)
                break
            acc.append(False)
            rejected += 1
    return {"draws": draws, "retained": retained, "rejected": rejected, "n_records": n,
            "direction": direction_balance(tried, acc)}


def direction_balance(angles, accepted, n_sector: int = 8) -> dict:
    """Acceptance share per sector of attempted shift directions, and the max-min spread."""
    a = np.asarray(angles, float)
    ok = np.asarray(accepted, bool)
    if not len(a):
        return dict(sector_accept=[], spread=float("nan"), n_tried=0)
    sec = np.minimum((a / (2 * np.pi) * n_sector).astype(int), n_sector - 1)
    share = [float(ok[sec == k].mean()) if (sec == k).any() else float("nan") for k in range(n_sector)]
    fin = [x for x in share if np.isfinite(x)]
    return dict(sector_accept=[round(x, 4) for x in share], spread=float(max(fin) - min(fin)) if fin else float("nan"),
                n_tried=int(len(a)))


def excess(observed: float, null_vals, alpha: float = 0.05) -> dict:
    """Normalised excess association over the null with a null-based interval. Not PPV."""
    v = np.asarray([x for x in null_vals if np.isfinite(x)], float)
    if not len(v) or not np.isfinite(observed):
        return dict(observed=observed, null_mean=float("nan"), null_lo=float("nan"), null_hi=float("nan"),
                    excess=float("nan"), excess_lo=float("nan"), excess_hi=float("nan"),
                    norm_excess=float("nan"), norm_lo=float("nan"), norm_hi=float("nan"), n_null=int(len(v)))
    mu = float(v.mean())
    lo, hi = np.percentile(v, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    den = max(1 - mu, 1e-9)
    return dict(observed=float(observed), null_mean=mu, null_lo=float(lo), null_hi=float(hi),
                excess=float(observed - mu), excess_lo=float(observed - hi), excess_hi=float(observed - lo),
                norm_excess=float((observed - mu) / den), norm_lo=float((observed - hi) / den),
                norm_hi=float((observed - lo) / den), n_null=int(len(v)))


def mde(n_records: int, null_vals, power_z: float = 0.8416, alpha: float = 0.05) -> float:
    """Minimum detectable excess. The rate an observed set needs so its lower bound clears the null's upper
    percentile with the stated power (binomial noise on the observed rate). NaN when there are no records."""
    v = np.asarray(null_vals, float)
    if n_records == 0 or not len(v):
        return float("nan")
    mu = float(v.mean())
    hi = float(np.percentile(v, 100 * (1 - alpha / 2)))
    p = min(max(hi, 1e-6), 1 - 1e-6)
    return float((hi - mu) + power_z * np.sqrt(p * (1 - p) / n_records))


# ----------------------------------------------------------------------------- assignment
def hungarian(rec_xy: np.ndarray, det_xy: np.ndarray, gate: float):
    """One-to-one assignment on distance with a gate. Returns (rec_idx, det_idx, dist).

    Memory-bounded (review 5.6 memory). A KD-tree finds the pairs within the gate. The bipartite graph of those
    pairs splits into connected components, and each component gets its own small Hungarian. Pairs beyond the
    gate can never be assigned, so the per-component solutions together equal the dense gated solution."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    e = np.array([], int)
    if len(rec_xy) == 0 or len(det_xy) == 0:
        return e, e, np.array([], float)
    rec_xy, det_xy = np.asarray(rec_xy, float), np.asarray(det_xy, float)
    hits = cKDTree(det_xy).query_ball_point(rec_xy, r=float(gate))
    ri = np.repeat(np.arange(len(rec_xy)), [len(h) for h in hits]).astype(int)
    dj = np.array([b for h in hits for b in h], int)
    if not len(ri):
        return e, e, np.array([], float)
    nr, nd = len(rec_xy), len(det_xy)
    A = coo_matrix((np.ones(len(ri)), (ri, nr + dj)), shape=(nr + nd, nr + nd))
    _, comp = connected_components(A, directed=False)
    pair_comp = comp[ri]
    out_i, out_j = [], []
    for c in np.unique(pair_comp):
        sel = pair_comp == c
        rs, ds = np.unique(ri[sel]), np.unique(dj[sel])
        D = np.hypot(rec_xy[rs, None, 0] - det_xy[None, ds, 0], rec_xy[rs, None, 1] - det_xy[None, ds, 1])
        C = np.where(D <= gate, D, BIG)
        a, b = linear_sum_assignment(C)
        ok = C[a, b] < BIG
        out_i.append(rs[a[ok]])
        out_j.append(ds[b[ok]])
    i, j = np.concatenate(out_i), np.concatenate(out_j)
    o = np.argsort(i, kind="stable")
    i, j = i[o], j[o]
    return i, j, np.hypot(rec_xy[i, 0] - det_xy[j, 0], rec_xy[i, 1] - det_xy[j, 1])


def assign(rec_xy: np.ndarray, rec_group: np.ndarray, det_xy: np.ndarray, gate: float, mode: str = "global"):
    """global      one Hungarian over every record of every status. A detection gets at most one record.
    per_status  one Hungarian per status. Outputs are labelled competing proposals (a detection may appear twice).
    Returns list of dict rows (rec_idx, det_idx, dist_m, group, proposal_type)."""
    rows = []
    if mode == "global":
        i, j, d = hungarian(rec_xy, det_xy, gate)
        for a, b, c in zip(i, j, d):
            rows.append(dict(rec_idx=int(a), det_idx=int(b), dist_m=float(c), group=rec_group[a],
                             proposal_type="global_one_to_one"))
    elif mode == "per_status":
        for g in np.unique(rec_group):
            sel = np.flatnonzero(rec_group == g)
            i, j, d = hungarian(rec_xy[sel], det_xy, gate)
            for a, b, c in zip(i, j, d):
                rows.append(dict(rec_idx=int(sel[a]), det_idx=int(b), dist_m=float(c), group=g,
                                 proposal_type="competing_per_status"))
    else:
        raise ValueError(mode)
    return rows


# ----------------------------------------------------------------------------- adjudication
def link_ppv_bounds(outcome, weight=None, alpha: float = 0.05) -> dict:
    """Link PPV from a blinded adjudication sample (protocol section 4 rule 5, section 6 bounds).

    outcome  per sampled link: 'correct', 'wrong' or 'ambiguous' (inaccessible counts as ambiguous)
    weight   inverse inclusion probabilities (1 when the sample is simple random)
    lower = correct weight / total, upper = 1 - wrong weight / total. Ambiguous sits in the gap.
    Sampling uncertainty by Clopper-Pearson on the effective n (Kish) around each bound.
    """
    from scipy.stats import beta
    o = np.asarray(outcome, dtype=object)
    w = np.ones(len(o)) if weight is None else np.asarray(weight, float)
    bad = set(o) - {"correct", "wrong", "ambiguous"}
    if bad:
        raise ValueError(f"unknown adjudication outcomes {bad}")
    W = w.sum()
    if W == 0:
        return dict(n=0)
    lower = float(w[o == "correct"].sum() / W)
    upper = float(1 - w[o == "wrong"].sum() / W)
    n_eff = W ** 2 / (w ** 2).sum()

    def cp(p, lo_side):
        k = p * n_eff
        if lo_side:
            return 0.0 if k <= 0 else float(beta.ppf(alpha / 2, k, n_eff - k + 1))
        return 1.0 if k >= n_eff else float(beta.ppf(1 - alpha / 2, k + 1, n_eff - k))
    return dict(n=int(len(o)), n_eff=float(n_eff), ppv_lower=lower, ppv_upper=upper,
                ppv_lower_ci_lo=cp(lower, True), ppv_upper_ci_hi=cp(upper, False),
                share_ambiguous=float(w[o == "ambiguous"].sum() / W))
