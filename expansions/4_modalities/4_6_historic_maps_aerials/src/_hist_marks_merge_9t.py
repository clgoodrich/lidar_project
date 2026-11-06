"""S4 of framework 4.6. Two-digitiser agreement and the adjudicated historic mark layer.

Purpose. Read the two independent mark sheets for one source, pair marks one to one across digitisers within the
agreement radius (greedy by distance), report agreement as the share of all marks that have a partner, and write the
merged layer. The interval resamples units, not marks. A unit is one pair (2 marks, both agreed) or one unpaired
mark (1 mark, not agreed). A Clopper-Pearson interval on marks counted both members of a pair as independent
trials and was too narrow (review 4.6-01, 2026-11-06). Agreed pairs become one mark at their midpoint. Unpaired
marks stay "pending" until a third-look file says keep or reject. Each mark carries the source's measured
positional accuracy from S3, so marks of different accuracy are never merged without it.
Inputs.
  expansions/4_modalities/4_6_historic_maps_aerials/data/raw/marks/<source>__<digitiser>.csv (assumed, two digitisers)
  expansions/4_modalities/4_6_historic_maps_aerials/data/raw/marks/<source>__adjudication.csv (optional; mark_id, decision)
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_georef_<source>_9t.json (from S3)
Outputs.
  data/9t/results/historic/historic_well_marks_9t.gpkg   layer marks (appends this source, replaces its old rows)
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_marks_agreement_<source>_9t.json
Run.
  python expansions/4_modalities/4_6_historic_maps_aerials/src/_hist_marks_merge_9t.py --source NAME [--digitisers d1 d2] [--out-gpkg PATH]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _hist_kit_4_6 as hk


def read_marks(path: Path, schema) -> pd.DataFrame:
    if path.suffix.lower() == ".gpkg":
        import geopandas as gpd
        g = gpd.read_file(path)
        hk.ek.assert_crs(g)
        df = pd.DataFrame(g.drop(columns="geometry"))
        df["x"], df["y"] = g.geometry.x, g.geometry.y
    else:
        df = pd.read_csv(path)
    miss = [c for c in schema if c not in df.columns]
    if miss:
        raise ValueError(f"{path} lacks {miss}")
    hk.ek.assert_no_nan(df.x, f"{path.name} x")
    return df


def pair_marks(a: pd.DataFrame, b: pd.DataFrame, radius: float):
    """Greedy one-to-one pairing by distance. Returns list of (ia, ib, dist)."""
    if not len(a) or not len(b):
        return []
    d = np.hypot(a.x.to_numpy()[:, None] - b.x.to_numpy()[None], a.y.to_numpy()[:, None] - b.y.to_numpy()[None])
    cand = np.argwhere(d <= radius)
    order = np.argsort(d[cand[:, 0], cand[:, 1]], kind="stable")
    ua, ub, pairs = set(), set(), []
    for i, j in cand[order]:
        if i not in ua and j not in ub:
            ua.add(i), ub.add(j)
            pairs.append((int(i), int(j), float(d[i, j])))
    return pairs


def agreement_ci(n_pairs: int, n_marks: int, B: int, seed: int) -> tuple[float, float, float, float]:
    """Agreement = 2 * pairs / marks with a percentile interval from resampling units (pairs and unpaired marks).
    Returns (point, lo, hi, undefined_share)."""
    n_single = n_marks - 2 * n_pairs
    if n_marks <= 0 or n_single < 0:
        return float("nan"), float("nan"), float("nan"), 1.0
    units = [(2, 2)] * n_pairs + [(0, 1)] * n_single

    def stat(us):
        k, n = sum(u[0] for u in us), sum(u[1] for u in us)
        return k / n if n else float("nan")
    p, lo, hi, draws = hk.ek.block_bootstrap(stat, units, B=B, seed=seed)
    return p, lo, hi, hk.ek.undefined_share(draws)


def merge(a, b, pairs, accuracy_m, adjud: dict | None):
    adjud = adjud or {}
    rows, pa, pb = [], {p[0] for p in pairs}, {p[1] for p in pairs}
    for i, j, dist in pairs:
        ra, rb = a.iloc[i], b.iloc[j]
        rows.append({"mark_id": f"{ra.mark_id}+{rb.mark_id}", "source": ra.source, "date": ra.date,
                     "digitiser": f"{ra.digitiser}+{rb.digitiser}",
                     "symbol": ra.symbol if ra.symbol == rb.symbol else f"{ra.symbol}|{rb.symbol}",
                     "x": (ra.x + rb.x) / 2, "y": (ra.y + rb.y) / 2, "pair_dist_m": dist,
                     "accuracy_m": accuracy_m, "adjudicated": "agreed"})
    for df, used in ((a, pa), (b, pb)):
        for k, r in df.reset_index(drop=True).iterrows():
            if k in used:
                continue
            dec = adjud.get(str(r.mark_id), "pending")
            rows.append({"mark_id": str(r.mark_id), "source": r.source, "date": r.date, "digitiser": r.digitiser,
                         "symbol": r.symbol, "x": r.x, "y": r.y, "pair_dist_m": np.nan,
                         "accuracy_m": accuracy_m, "adjudicated": dec})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    cfg = hk.load_cfg()
    pr = cfg["prereg"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True)
    ap.add_argument("--digitisers", nargs=2, default=["d1", "d2"])
    ap.add_argument("--marks-dir", default=None)
    ap.add_argument("--georef-json", default=None)
    ap.add_argument("--out-gpkg", default=None)
    ap.add_argument("--out", default=None, help="tables folder")
    a = ap.parse_args(argv)
    spec = cfg["inputs"]["marks_dir"]
    mdir = Path(a.marks_dir) if a.marks_dir else hk.resolve(spec)
    sheets = []
    for dname in a.digitisers:
        cands = [mdir / f"{a.source}__{dname}{ext}" for ext in (".csv", ".gpkg")]
        hit = next((c for c in cands if c.exists()), None)
        sheets.append(read_marks(hk.need(hit or cands[0], f"marks of digitiser {dname}", spec), spec["schema"]))
    A, Bm = sheets
    if set(A.digitiser) & set(Bm.digitiser):
        raise AssertionError("the two sheets share a digitiser name. Agreement needs independent digitisers")
    tables = Path(a.out) if a.out else hk.resolve(cfg["outputs"]["tables"])
    gj = Path(a.georef_json) if a.georef_json else tables / f"hist_georef_{a.source}_9t.json"
    geo = json.loads(hk.need(gj, f"S3 accuracy for {a.source}").read_text())
    pairs = pair_marks(A, Bm, pr["agreement_radius_m"])
    n_marks = len(A) + len(Bm)
    p, lo, hi, und = agreement_ci(len(pairs), n_marks, int(pr["B"]), int(pr["master_seed"]))
    adj_f = mdir / f"{a.source}__adjudication.csv"
    adjud = dict(pd.read_csv(adj_f).astype(str)[["mark_id", "decision"]].values) if adj_f.exists() else None
    merged = merge(A, Bm, pairs, geo["rmse_m"], adjud)
    hk.ek.assert_rows(merged, n_marks - len(pairs), "merged marks")
    import geopandas as gpd
    g = gpd.GeoDataFrame(merged, geometry=gpd.points_from_xy(merged.x, merged.y), crs=cfg["crs"])
    gpk = Path(a.out_gpkg) if a.out_gpkg else hk.resolve(cfg["outputs"]["marks_gpkg"])
    gpk.parent.mkdir(parents=True, exist_ok=True)
    if gpk.exists():
        old = gpd.read_file(gpk, layer="marks")
        g = pd.concat([old[old.source != a.source], g], ignore_index=True)
        g = gpd.GeoDataFrame(g, geometry="geometry", crs=cfg["crs"])
    hk.ek.assert_unique(g, "mark_id")
    g.to_file(gpk, layer="marks", driver="GPKG")
    res = {"source": a.source, "n_marks": n_marks, "n_pairs": len(pairs), "agreement": p, "agreement_lo": lo,
           "agreement_hi": hi, "agreement_level": pr["agreement_level"], "radius_m": pr["agreement_radius_m"],
           "agreement_passes": bool(np.isfinite(lo) and lo > pr["agreement_level"]),
           "agreement_ci": "percentile bootstrap over units (pairs and unpaired marks)", "undefined_share": und,
           "n_units": len(pairs) + n_marks - 2 * len(pairs),
           "n_pending": int((merged.adjudicated == "pending").sum()), "accuracy_m": geo["rmse_m"]}
    tables.mkdir(parents=True, exist_ok=True)
    jf = tables / f"hist_marks_agreement_{a.source}_9t.json"
    jf.write_text(json.dumps(res, indent=2), encoding="utf-8")
    hk.prov(tables, f"hist_marks_merge_{a.source}", inputs=[mdir, gj], outputs=[gpk, jf], params=res)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
