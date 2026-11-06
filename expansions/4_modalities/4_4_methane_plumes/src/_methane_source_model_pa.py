"""M3. Source-level model. Group plumes into persistent sources, apply the attribution rule, and estimate the rate
ratio of sources near wells against matched control points, with observation opportunity as an offset.

Purpose
    Plumes are observations of a source. Repeated overpasses of one source count once. A source is read as
    "well is the plausible source" only when a well lies inside its uncertainty radius, no active facility does,
    and at least two distinct dates agree. Otherwise it reads "plume near well" or less.
    The rate ratio is a Poisson regression of sources near a point on point type (well or control), with
    log(usable overpasses of the cell) as offset. Interval by cluster bootstrap over cells. Reported with and
    without cells holding an active facility. Controls never sit at candidate wells.

Inputs
    methane_overlay_by_plume.csv and methane_opportunity_by_cell.csv from the newest M2 run
        (expansions/4_modalities/4_4_methane_plumes/results/<YYYYMMDD>_methane_overlay_<hash7>/), or --overlay-dir
    wells, orphan list, candidates and facilities as in config_4_4.json section m2

Outputs (run folder expansions/4_modalities/4_4_methane_plumes/results/<YYYYMMDD>_methane_sources_<hash7>/)
    methane_sources_attribution.csv    one row per source with members, dates and the attribution reading
    methane_source_rate_ratio.json     rate ratio, intervals, gate verdict (all cells and facility-free cells)
    _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/4_modalities/4_4_methane_plumes/src/_methane_source_model_pa.py [--overlay-dir DIR] [--basin pennsylvania]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _methane_shared_io as io  # noqa: E402
from _methane_shared_io import ek  # noqa: E402
from _methane_plume_overlay_pa import read_points  # noqa: E402


# ----------------------------------------------------------------------------- sources
def link_sources(x: np.ndarray, y: np.ndarray, unc: np.ndarray) -> np.ndarray:
    """Union-find. Two plumes join when their centres lie within max(unc_i, unc_j)."""
    from scipy.spatial import cKDTree
    n = len(x)
    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    if n:
        tree = cKDTree(np.c_[x, y])
        for i, j in tree.query_pairs(float(np.max(unc))):
            if np.hypot(x[i] - x[j], y[i] - y[j]) <= max(unc[i], unc[j]):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
    roots = np.array([find(i) for i in range(n)])
    _, sid = np.unique(roots, return_inverse=True)
    return sid


def build_sources(pl: pd.DataFrame) -> pd.DataFrame:
    pl = pl.copy()
    pl["source_id"] = link_sources(pl.x_m.to_numpy(float), pl.y_m.to_numpy(float), pl.source_unc_m.to_numpy(float))
    pl["date"] = pd.to_datetime(pl.datetime_utc, utc=True).dt.date
    w = pl.emission_kg_h.clip(lower=1e-9)
    pl["wx"], pl["wy"] = pl.x_m * w, pl.y_m * w
    pl["w"] = w
    g = pl.groupby("source_id")
    S = pd.DataFrame({"x_m": g.wx.sum() / g.w.sum(), "y_m": g.wy.sum() / g.w.sum(),
                      "unc_m": g.source_unc_m.median(), "n_obs": g.size(), "n_dates": g.date.nunique(),
                      "mean_emission_kg_h": g.emission_kg_h.mean(),
                      "plume_ids": g.plume_id.apply(lambda s: ";".join(map(str, s))),
                      "instruments": g.instrument.apply(lambda s: ";".join(sorted(set(map(str, s)))))}).reset_index()
    return S


def attribute(S: pd.DataFrame, wells_xy: np.ndarray, fac_xy: np.ndarray | None, min_dates: int) -> pd.DataFrame:
    from scipy.spatial import cKDTree
    S = S.copy()
    pts = np.c_[S.x_m, S.y_m]
    tw = cKDTree(wells_xy) if len(wells_xy) else None
    tf = cKDTree(fac_xy) if fac_xy is not None and len(fac_xy) else None
    S["n_wells_in_radius"] = [len(tw.query_ball_point(p, r)) if tw else 0 for p, r in zip(pts, S.unc_m)]
    S["n_facilities_in_radius"] = [len(tf.query_ball_point(p, r)) if tf else 0 for p, r in zip(pts, S.unc_m)]
    S["facility_layer_present"] = tf is not None
    cond_w, cond_f, cond_r = S.n_wells_in_radius > 0, S.n_facilities_in_radius == 0, S.n_dates >= min_dates
    S["reading"] = np.select(
        [cond_w & cond_f & cond_r & (tf is not None), cond_w & ~cond_f, cond_w], [
            "well is the plausible source (pending ground check)", "plume near well and active facility",
            "plume near well"], "no well in radius")
    if tf is None:
        S.loc[cond_w, "reading"] = "plume near well (facility layer missing, attribution not allowed)"
    return S


# ----------------------------------------------------------------------------- rate ratio
def poisson_irls(X: np.ndarray, y: np.ndarray, offset: np.ndarray, iters: int = 50) -> np.ndarray:
    beta = np.zeros(X.shape[1])
    beta[0] = np.log(max(y.mean(), 1e-9)) - offset.mean()
    for _ in range(iters):
        eta = X @ beta + offset
        mu = np.exp(np.clip(eta, -30, 30))
        z = eta - offset + (y - mu) / np.maximum(mu, 1e-12)
        W = mu
        XtW = X.T * W
        new = np.linalg.solve(XtW @ X + 1e-9 * np.eye(X.shape[1]), XtW @ z)
        if np.max(np.abs(new - beta)) < 1e-10:
            beta = new
            break
        beta = new
    return beta


def make_points(wells_xy, excl_xy, opp: pd.DataFrame, cell_m: float, per_well: int, excl_m: float, rng):
    """Wells in observed cells plus random controls in the same cells, clear of every well and candidate."""
    from scipy.spatial import cKDTree
    obs = opp[opp.n_searched > 0]
    ci = np.floor(wells_xy / cell_m).astype(np.int64)
    key = {(int(np.floor(r.x0 / cell_m)), int(np.floor(r.y0 / cell_m))): r for r in obs.itertuples()}
    tree = cKDTree(excl_xy) if len(excl_xy) else None
    rows = []
    for (i, j), xy in zip(map(tuple, ci), wells_xy):
        r = key.get((i, j))
        if r is not None:
            rows.append((xy[0], xy[1], 1, r.cell_id, r.n_searched))
    wells_per_cell = pd.Series([c for *_, c, _ in rows]).value_counts() if rows else pd.Series(dtype=int)
    for cid, nw in wells_per_cell.items():
        r = obs[obs.cell_id == cid].iloc[0]
        need, tries = nw * per_well, 0
        while need and tries < 200 * nw * per_well:
            tries += 1
            p = (r.x0 + rng.uniform(0, cell_m), r.y0 + rng.uniform(0, cell_m))
            if tree is None or tree.query(p)[0] > excl_m:
                rows.append((p[0], p[1], 0, cid, r.n_searched))
                need -= 1
    return pd.DataFrame(rows, columns=["x", "y", "is_well", "cell_id", "n_searched"])


def count_near(P: pd.DataFrame, S: pd.DataFrame, radius: float | None) -> np.ndarray:
    from scipy.spatial import cKDTree
    if len(S) == 0:
        return np.zeros(len(P))
    t = cKDTree(np.c_[P.x, P.y])
    y = np.zeros(len(P))
    for sx, sy, su in zip(S.x_m, S.y_m, S.unc_m):
        for k in t.query_ball_point((sx, sy), radius or su):
            y[k] += 1
    return y


def exact_conditional_rr(P: pd.DataFrame, alpha: float = 0.05) -> dict:
    """Exact conditional rate ratio (wells over controls). Given the total count n, the well count is
    Binomial(n, p) with p = RR E_w / (RR E_w + E_c), E = summed overpasses. Clopper-Pearson on p gives the
    interval. It stays defined under separation (zero counts in one group give a 0 or infinite bound).
    It ignores clustering by cell, so it is reported beside the cluster bootstrap and not used for the verdict."""
    w = P.is_well == 1
    k, n = int(P.y[w].sum()), int(P.y.sum())
    e_w, e_c = float(P.n_searched[w].sum()), float(P.n_searched[~w].sum())
    if n == 0 or e_w == 0 or e_c == 0:
        return {"rr": float("nan"), "lo": float("nan"), "hi": float("nan"), "k_wells": k, "n_total": n}
    _, plo, phi = ek.clopper_pearson(k, n, alpha)
    to_rr = lambda p: float("inf") if p >= 1 else p / (1 - p) * e_c / e_w  # noqa: E731
    return {"rr": to_rr(k / n), "lo": to_rr(plo), "hi": to_rr(phi), "k_wells": k, "n_total": n}


def _separated(D: pd.DataFrame) -> bool:
    """Quasi-separation. One group has no events, so the Poisson MLE of the ratio is 0 or infinite."""
    return bool(D.y[D.is_well == 1].sum() == 0 or D.y[D.is_well == 0].sum() == 0)


def rate_ratio(P: pd.DataFrame, B: int, seed: int):
    """Cluster bootstrap over cells. A resample with separation has no finite MLE. It is undefined (NaN),
    counted, and by SH-01 makes the interval undefined. The exact conditional interval is reported beside it."""
    def fit(D):
        if D.is_well.nunique() < 2 or D.y.sum() == 0 or _separated(D):
            return np.nan
        X = np.c_[np.ones(len(D)), D.is_well.to_numpy(float)]
        return float(np.exp(poisson_irls(X, D.y.to_numpy(float), np.log(D.n_searched.to_numpy(float)))[1]))
    groups = {c: d for c, d in P.groupby("cell_id")}
    blocks = list(groups)
    point, lo, hi, draws = ek.block_bootstrap(lambda bl: fit(pd.concat([groups[b] for b in bl])), blocks, B=B,
                                              seed=seed)
    return {"rate_ratio": point, "lo": lo, "hi": hi, "n_cells": len(blocks), "n_wells": int(P.is_well.sum()),
            "n_controls": int((P.is_well == 0).sum()), "n_sources_counted": float(P.y.sum()),
            "separation": _separated(P), "undefined_share": ek.undefined_share(draws),
            "exact_conditional": exact_conditional_rr(P),
            "bootstrap_unreliable": len(blocks) < 15}


def run(cfg: dict, out_root: Path | None = None, overlay_dir: Path | None = None, basin: str = "pennsylvania") -> dict:
    m2, m3 = cfg["m2"], cfg["m3"]
    crs = next((b["metric_crs"] for b in cfg.get("m4_basins", []) if b["basin"] == basin), cfg["metric_crs"])
    od = overlay_dir or io.latest_run("methane_overlay", base=out_root)
    ov = io.need(None if od is None else Path(od) / "methane_overlay_by_plume.csv", "M2 overlay table",
                 "run _methane_plume_overlay_pa.py first")
    pl = pd.read_csv(ov)
    pl = pl[pl.usable]
    run_dir = ek.new_run(io.EXP, "methane_sources", {**m3, "basin": basin}, base=out_root,
                         why="M3 source grouping, attribution rule and rate ratio (fw_4_4 section 7).")
    inputs = [ov]
    pts = []
    for key in ("wells_gpkg", "orphan_csv"):
        L = read_points(io.resolve(m2.get(key)), crs, key)
        if L is not None:
            pts.append(np.c_[L.geometry.x, L.geometry.y])
            inputs.append(io.resolve(m2[key]))
    wells_xy = np.unique(np.round(np.vstack(pts), 1), axis=0) if pts else np.empty((0, 2))
    fac = read_points(io.resolve(m2.get("facilities_gpkg")), crs, "facilities")
    fac_xy = None if fac is None else np.c_[fac.geometry.x, fac.geometry.y]
    cand = read_points(io.resolve(m2.get("candidate_wells_gpkg")), crs, "candidates")
    cand_xy = np.empty((0, 2)) if cand is None else np.c_[cand.geometry.x, cand.geometry.y]

    S = attribute(build_sources(pl), wells_xy, fac_xy, int(m3["min_repeat_dates"]))
    ek.assert_unique(S, "source_id")
    sc = run_dir / "methane_sources_attribution.csv"
    S.to_csv(sc, index=False)
    outputs = [sc]

    res = {"basin": basin, "n_plumes_usable": int(len(pl)), "n_sources": int(len(S)),
           "readings": S.reading.value_counts().to_dict(),
           "note": "Repeated observations of one source are one source. Selection toward known emitters is not removed."}
    opp_p = Path(od) / "methane_opportunity_by_cell.csv"
    if opp_p.exists():
        opp = pd.read_csv(opp_p)
        inputs.append(opp_p)
        rng = np.random.default_rng(int(m3["seed"]))
        excl = np.vstack([wells_xy, cand_xy]) if len(cand_xy) else wells_xy
        P = make_points(wells_xy, excl, opp, float(m2["cell_m"]), int(m3["controls_per_well"]),
                        float(m3["control_exclusion_m"]), rng)
        P["y"] = count_near(P, S, m3.get("near_radius_m"))
        useful = float(m3["useful_rate_ratio"])
        out = {}
        for tag, D in (("all_cells", P), ("facility_free_cells", None)):
            if D is None:
                if fac_xy is None:
                    out[tag] = "facility layer missing"
                    continue
                cm = float(m2["cell_m"])
                fc = set(map(tuple, np.floor(fac_xy / cm).astype(np.int64)))
                bad = [r.cell_id for r in opp.itertuples()
                       if (int(np.floor(r.x0 / cm)), int(np.floor(r.y0 / cm))) in fc]
                D = P[~P.cell_id.isin(bad)]
            rr = rate_ratio(D, int(m3["bootstrap_B"]), int(m3["seed"]))
            rr["verdict"] = ek.decide(rr["lo"], rr["hi"], useful, "superiority") if np.isfinite(rr["lo"]) else "inconclusive"
            out[tag] = rr
        res["rate_ratio"] = out
        res["useful_rate_ratio"] = useful
    else:
        res["rate_ratio"] = "no opportunity table. Descriptive source map only (fw_4_4 section 12)."
    rj = run_dir / "methane_source_rate_ratio.json"
    rj.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    outputs.append(rj)
    ek.write_provenance(run_dir, inputs=inputs, outputs=outputs, params={**m3, "basin": basin},
                        seeds={"controls": m3["seed"]})
    return {"run_dir": run_dir, "sources": sc, "result": res}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=io.CONFIG_PATH)
    ap.add_argument("--overlay-dir", type=Path, default=None, help="M2 run folder (default newest)")
    ap.add_argument("--basin", default="pennsylvania")
    ap.add_argument("--out-root", type=Path, default=None)
    a = ap.parse_args()
    r = run(io.load_config(a.config), a.out_root, a.overlay_dir, a.basin)
    print(json.dumps(r["result"], indent=2, default=float))


if __name__ == "__main__":
    main()
