"""Recall gap on newly documented wells, tile 9t (A6). Descriptive, underpowered by design.

Question. Do wells that entered the DEP abandoned or orphan inventory after 2022-05-09 get detected less often than wells already
on the 2022 orphan list? Proxy only. 'newly documented' includes reclassifications of wells that were already on the ground.
Cohort is Venango. It contributes to a later region only if that region has its own dated baseline.

Groups (WELL_STATU in DEP Orphan List, DEP Abandoned List, Abandoned), inside the scored footprint (115 CV blocks).
  old  = permit on the 2022 orphan list
  new  = not on the 2022 list
Outcome. A held-out detection within 50 m (pit), or inside a held-out pad polygon.
Statistic. Exact (Clopper-Pearson) interval per group and a Newcombe interval for the difference.
Decision rule belongs in the preregistration (non-inferiority margin). Overlap of separate intervals is not a test.

Outputs (data/9t/results/records/): record_recall_gap_9t.json
Run: python notebooks/wellsight_v2/s5_eval/_recall_gap_newly_documented_9t.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import beta

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _record_assoc_pits_9t as ra  # noqa: E402

ROOT = ra.ROOT
STAT = ["DEP Orphan List", "DEP Abandoned List", "Abandoned"]


def cp(k, n, a=0.05):
    if n == 0:
        return (np.nan, np.nan)
    lo = 0.0 if k == 0 else beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - a / 2, k + 1, n - k)
    return (float(lo), float(hi))


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def newcombe(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - np.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + np.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def main():
    pits, pads, w = ra.load()
    cov = ra.cells(ra.footprint())
    old = pd.read_csv(ROOT / "data/_source/reference/legacy_data/US_Documented_Orphan_Wells.csv")
    old = old[old.County == "Venango"]
    old_keys = set(old.Well_ident.str.extract(r"API:37121(\d{5})")[0].dropna().astype(int))
    w = w[w.WELL_STATU.isin(STAT)].copy()
    w["key"] = w.PERMIT_NUM.str.extract(r"121-(\d+)")[0].astype(float)
    w["old"] = w.key.isin(old_keys)
    w = w[ra.inside(np.c_[w.x.values, w.y.values], cov)]
    t = cKDTree(pits)
    d, _ = t.query(np.c_[w.x.values, w.y.values])
    w["pit50"] = d <= 50
    pts = gpd.points_from_xy(w.x.values, w.y.values)
    from shapely import STRtree
    idx = STRtree(pads.geometry.values).query(pts, predicate="intersects")
    w["pad_in"] = False
    w.iloc[np.unique(idx[0]), w.columns.get_loc("pad_in")] = True
    w["any"] = w.pit50 | w.pad_in
    res = {"cohort_note": "Proxy. New includes reclassifications. Venango only. Counts are small."}
    for col in ("pit50", "pad_in", "any"):
        g = {}
        for name, m in (("old", w.old), ("new", ~w.old)):
            k, n = int(w.loc[m, col].sum()), int(m.sum())
            g[name] = dict(k=k, n=n, rate=round(k / n, 3) if n else None, exact95=[round(x, 3) for x in cp(k, n)])
        if g["old"]["n"] and g["new"]["n"]:
            dd, lo, hi = newcombe(g["new"]["k"], g["new"]["n"], g["old"]["k"], g["old"]["n"])
            g["new_minus_old"] = dict(diff=round(dd, 3), newcombe95=[round(lo, 3), round(hi, 3)])
        res[col] = g
    out = ROOT / "data/9t/results/records/record_recall_gap_9t.json"
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    print(out)


if __name__ == "__main__":
    main()
