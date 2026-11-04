"""Propose associations between DEP well records and held-out pit/pad detections on tile 9t, with a spatial null.

Plan: docs/iterations/expansion_options_methods.md, item 5.6. Write-up: docs/iterations/record_assoc_pits_9t.md.

WITHDRAWN INPUT (2026-11-04). load() drops dup_on_pit == 1, which removes every matched detection, and the pad file is the unmatched leftover set.
Do not cite results from this version. See docs/plans/protocol_gates_and_metrics.md section 4 for the input contract.

What this does and does not claim.
  - A detection centroid is not a borehole. The output is a PROPOSED ASSOCIATION between a record and a nearby terrain feature.
  - Nothing here shows a coordinate is corrected. That needs independent coordinates (GNSS points, NETL sites). None are used.
  - The shifted-record null estimates chance matching under that null. It is not the error rate of accepted matches.

Inputs.
  - Detections: out-of-fold held-out pit detections at cutoff 0.50 (layers matched + undecided of pit_candidates_undecided_thr0p50_9t.gpkg),
    one per pit (dup_on_pit == 1 dropped). Pad candidates: pad_candidates_filtered_heldout_9t.shp.
  - Records: PA DEP Venango export (venango_wells_all.gpkg, April 2026), wells inside the tile, split by WELL_STATU.
Coverage (revised 2026-11-04 after outside review). Eligibility is the scored footprint, the 115 pit-bearing 375 m CV blocks of
  pit_blocks_9t.gpkg, including blocks where the detector found nothing. It does not depend on model output. Observed and shifted records
  use the same rule (inside the footprint and the tile). The whole record set is translated as one, which keeps its clustering.
  Primary radius for pits 50 m and for pads inside the polygon. Other radii are sensitivity only.
Pit level. One-to-one assignment (Hungarian) on distance with a gate. Pad level. Many records may share a pad, distance is to the polygon.
Null. Each record set is translated by a vector of length 200 to 500 m in a random direction, 300 times.

Outputs (data/9t/results/records/): record_pit_assoc_proposals_9t.csv, record_assoc_rates_9t.csv, record_assoc_summary_9t.json,
  record_assoc_rates_9t.png

Run: python notebooks/wellsight_v2/s5_eval/_record_assoc_pits_9t.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/9t/results/records"
OUT.mkdir(parents=True, exist_ok=True)
BB = (619500.0, 4593000.0, 624000.0, 4597500.0)
CELL, GATE, RADII = 250.0, 100.0, (10, 25, 50, 75, 100)
NSHIFT, SEED = 300, 20261104
GROUPS = {"orphan or abandoned": ["DEP Orphan List", "DEP Abandoned List"], "plugged": ["Plugged OG Well"], "active": ["Active"]}
# Palette: observed #1F5FA8 (validated blue), null grey #8E959B. Second encoding is line style and markers.
BLUE, GREY = "#1F5FA8", "#8E959B"


def load():
    p = ROOT / "data/9t/results/pit/centroid_matching/pit_candidates_undecided_thr0p50_9t.gpkg"
    det = pd.concat([gpd.read_file(p, layer=l) for l in ("matched", "undecided")], ignore_index=True)
    det = det[det.dup_on_pit == 0]
    pits = np.c_[det["cx"].values, det["cy"].values]
    pads = gpd.read_file(ROOT / "data/9t/results/pit/centroid_matching/pad_candidates_filtered_heldout_9t.shp")
    w = gpd.read_file(ROOT / "data/_source/reference/dep_wells/venango_wells_all.gpkg")
    x, y = w.geometry.x, w.geometry.y
    w = w[(x >= BB[0]) & (x <= BB[2]) & (y >= BB[1]) & (y <= BB[3])].copy()
    w["x"], w["y"] = w.geometry.x, w.geometry.y
    return pits, pads, w


def footprint():
    b = gpd.read_file(ROOT / "data/9t/derived/05/pit_blocks_9t.gpkg", layer="blocks")
    return b[b.n_pits > 0]


def cells(blocks):
    """Set of (ix, iy) block indices that were scored."""
    return set(zip(blocks.ix.astype(int), blocks.iy.astype(int)))


BLOCK = 375.0


def inside(xy, cov):
    ij = np.floor((xy - np.array(BB[:2])) / BLOCK).astype(int)
    return np.array([tuple(c) in cov for c in ij])


def pit_rates(rec, det):
    """Share of records with a detection within r (nearest, many-to-one) and the one-to-one assignment within the gate."""
    t = cKDTree(det)
    d, _ = t.query(rec)
    rates = {r: float((d <= r).mean()) for r in RADII}
    return rates, d


def one_to_one(rec, det):
    D = np.hypot(rec[:, None, 0] - det[None, :, 0], rec[:, None, 1] - det[None, :, 1])
    C = np.where(D <= GATE, D, 1e6)
    i, j = linear_sum_assignment(C)
    ok = C[i, j] < 1e6
    return i[ok], j[ok], D[i[ok], j[ok]]


def main():
    pits, pads, w = load()
    rng = np.random.default_rng(SEED)
    fp = footprint()
    cov_pit = cov_pad = cells(fp)
    padgeom = pads.geometry.values
    from shapely import STRtree
    ptree = STRtree(padgeom)
    print(f"detections {len(pits)} pit, {len(pads)} pad polygons; scored blocks {len(cov_pit)}")

    rows, prop, summ = [], [], {}
    for gname, stats in GROUPS.items():
        g = w[w.WELL_STATU.isin(stats)]
        rec = np.c_[g.x.values, g.y.values]
        keep = inside(rec, cov_pit)
        rec, gg = rec[keep], g[keep]
        n = len(rec)
        rates, dnn = pit_rates(rec, pits)
        # null
        null = {r: [] for r in RADII}
        for _ in range(NSHIFT):
            a = rng.uniform(0, 2 * np.pi)
            m = rng.uniform(200, 500)
            sh = rec + np.array([m * np.cos(a), m * np.sin(a)])
            ok = inside(sh, cov_pit) & (sh[:, 0] >= BB[0]) & (sh[:, 0] <= BB[2]) & (sh[:, 1] >= BB[1]) & (sh[:, 1] <= BB[3])
            if ok.sum() < 10:
                continue
            rr, _ = pit_rates(sh[ok], pits)
            for r in RADII:
                null[r].append(rr[r])
        for r in RADII:
            v = np.array(null[r])
            rows.append(dict(level="pit", group=gname, n_records=n, radius_m=r, observed=round(rates[r], 4), null_mean=round(float(v.mean()), 4),
                             null_lo=round(float(np.percentile(v, 2.5)), 4), null_hi=round(float(np.percentile(v, 97.5)), 4),
                             excess=round(rates[r] - float(v.mean()), 4), n_null=len(v)))
        # pad level: distance to polygon, many records may share a pad
        gp = g[inside(np.c_[g.x.values, g.y.values], cov_pad)]
        pts = gpd.points_from_xy(gp.x.values, gp.y.values)

        def pad_rate(pt_arr, r):
            idx = ptree.query(pt_arr, predicate="dwithin", distance=r)
            return float(len(np.unique(idx[0])) / len(pt_arr))
        nullp = {r: [] for r in (0, 25, 50)}
        for _ in range(NSHIFT):
            a = rng.uniform(0, 2 * np.pi)
            m = rng.uniform(200, 500)
            sx = gp.x.values + m * np.cos(a)
            sy = gp.y.values + m * np.sin(a)
            ok = inside(np.c_[sx, sy], cov_pad) & (sx >= BB[0]) & (sx <= BB[2]) & (sy >= BB[1]) & (sy <= BB[3])
            if ok.sum() < 10:
                continue
            spts = gpd.points_from_xy(sx[ok], sy[ok])
            for r in nullp:
                nullp[r].append(pad_rate(spts, r))
        for r in (0, 25, 50):
            v = np.array(nullp[r])
            ob = pad_rate(pts, r)
            rows.append(dict(level="pad", group=gname, n_records=len(gp), radius_m=r, observed=round(ob, 4), null_mean=round(float(v.mean()), 4),
                             null_lo=round(float(np.percentile(v, 2.5)), 4), null_hi=round(float(np.percentile(v, 97.5)), 4),
                             excess=round(ob - float(v.mean()), 4), n_null=len(v)))
        # proposals (pit level, one-to-one within gate)
        i, j, dd = one_to_one(rec, pits)
        gi = gg.iloc[i]
        P = pd.DataFrame(dict(permit=gi.PERMIT_NUM.values, status=gi.WELL_STATU.values, rec_x=rec[i, 0], rec_y=rec[i, 1],
                              det_x=pits[j, 0], det_y=pits[j, 1], dx=pits[j, 0] - rec[i, 0], dy=pits[j, 1] - rec[i, 1], dist_m=dd.round(1)))
        P["group"] = gname
        prop.append(P)
        close = P[P.dist_m <= 50]
        summ[gname] = dict(n_records=n, one_to_one_within_gate=len(P), within_50m=len(close),
                           median_dist_m=float(P.dist_m.median()) if len(P) else None,
                           mean_offset_dE_dN_m=[round(float(close.dx.mean()), 1), round(float(close.dy.mean()), 1)] if len(close) else None,
                           mean_offset_se_m=[round(float(close.dx.std() / np.sqrt(len(close))), 1), round(float(close.dy.std() / np.sqrt(len(close))), 1)] if len(close) > 2 else None)
    R = pd.DataFrame(rows)
    R.to_csv(OUT / "record_assoc_rates_9t.csv", index=False)
    pd.concat(prop).to_csv(OUT / "record_pit_assoc_proposals_9t.csv", index=False)
    summ["settings"] = dict(gate_m=GATE, radii_m=list(RADII), n_shifts=NSHIFT, shift_m="200 to 500", seed=SEED, cell_m=CELL,
                            n_pit_detections=int(len(pits)), n_pad_polygons=int(len(pads)),
                            note="Proposed associations only. Not corrected coordinates. No independent coordinates used.")
    (OUT / "record_assoc_summary_9t.json").write_text(json.dumps(summ, indent=2))
    print(R.to_string(index=False))
    print(json.dumps(summ, indent=2))

    fig, ax = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    for a, gname in zip(ax, GROUPS):
        s = R[(R.level == "pit") & (R.group == gname)]
        a.fill_between(s.radius_m, s.null_lo, s.null_hi, color=GREY, alpha=0.3, label="shifted records, 95%")
        a.plot(s.radius_m, s.null_mean, color=GREY, ls="--", marker="s", label="shifted records, mean")
        a.plot(s.radius_m, s.observed, color=BLUE, ls="-", marker="o", label="DEP records")
        a.set_title(f"{gname} (n={int(s.n_records.iloc[0])})", fontsize=10)
        a.set_xlabel("distance to a held-out pit detection (m)")
    ax[0].set_ylabel("share of records with a detection within distance")
    ax[0].legend(fontsize=8, loc="upper left")
    fig.suptitle("DEP records against held-out pit detections, tile 9t, with a shifted-record null", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "record_assoc_rates_9t.png", dpi=140)
    print(OUT / "record_assoc_rates_9t.png")


if __name__ == "__main__":
    main()
