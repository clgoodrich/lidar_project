"""5.6 S4. Cohort-stratified association, orphan and abandoned records, 9t. Descriptive only.

Purpose
    Split orphan and abandoned records into those on the 2022-05-09 orphan list ("listed_2022") and those not on it
    ("newly_documented", the 2022 to 2026 additions, which include reclassifications). Each cohort gets its own
    shifted null, so cohorts are compared by normalised excess over a cohort-specific null, never by raw match rate
    (protocol section 4 rule 7). When DEP coordinate provenance (R1) arrives, each cohort is further split by
    coord_source. This replaces the withdrawn _recall_gap_newly_documented_9t.py as the A6 input for 5.4.
    No recall-equivalence gate. Spatial excess alone does not identify detection sensitivity.

Inputs (config_5_6.json)
    full_pit, full_pad (S0), pit_blocks, pad_blocks, dep_wells, orphan_2022
    coord_source   assumed, @dep_wells/dep_coordinate_source_venango.csv (PERMIT_NUM, coord_source). Optional.
Outputs
    expansions/5_tasks/5_6_record_association/results/tables/records_cohort_excess_9t.csv
    expansions/5_tasks/5_6_record_association/results/tables/records_cohort_excess_9t.json
Run
    python expansions/5_tasks/5_6_record_association/src/_records_cohort_strata_9t.py [--n-shift 300]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _records_assoc_core as core  # noqa: E402
import _records_assoc_v2_9t as v2  # noqa: E402

ek = th.ek
COHORT_STATUSES = ["DEP Orphan List", "DEP Abandoned List", "Abandoned"]


def old_keys_2022(csv: Path, county: str = "Venango") -> set:
    old = pd.read_csv(csv, low_memory=False)
    th.require_columns(old, ["Well_ident", "County"], "2022 orphan list")
    old = old[old.County == county]
    return set(old.Well_ident.astype(str).str.extract(r"API:37121(\d{5})")[0].dropna().astype(int))


def permit_key(permit) -> pd.Series:
    return pd.Series(permit).astype(str).str.extract(r"121-(\d+)")[0].astype(float)


def cohort_table(dep, old_keys: set, coord=None):
    d = dep[dep.WELL_STATU.isin(COHORT_STATUSES)].copy()
    d["key"] = permit_key(d.PERMIT_NUM).to_numpy()
    d["cohort"] = np.where(d.key.isin(old_keys), "listed_2022", "newly_documented")
    d["coord_source"] = "unstratified"
    if coord is not None:
        th.require_columns(coord, ["PERMIT_NUM", "coord_source"], "coord_source")
        m = dict(zip(coord.PERMIT_NUM.astype(str), coord.coord_source.astype(str)))
        d["coord_source"] = d.PERMIT_NUM.astype(str).map(m).fillna("unknown")
    return d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("--n-shift", type=int)
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    n_shift = a.n_shift or cfg["null"]["n_shift"]
    org, size, bbox, nl = cfg["block_origin"], cfg["block_m"], cfg["tile_bbox"], cfg["null"]
    pit = th.read_vector(th.inp(cfg, "full_pit"))
    pad = th.read_vector(th.inp(cfg, "full_pad"))
    pb = th.read_vector(th.inp(cfg, "pit_blocks"), layer="blocks")
    db = th.read_vector(th.inp(cfg, "pad_blocks"), layer="blocks")
    elig = {"pit": v2.make_eligible(v2.footprint_cells(pb, "n_pits", org, size), bbox, org, size),
            "pad": v2.make_eligible(v2.footprint_cells(db, "n_pads", org, size), bbox, org, size)}
    dep = th.load_dep(th.inp(cfg, "dep_wells"), bbox=bbox)
    coord = pd.read_csv(th.inp(cfg, "coord_source")) if th.has(cfg, "coord_source") else None
    d = cohort_table(dep, old_keys_2022(th.inp(cfg, "orphan_2022")), coord)
    rate = {"pit": core.pit_rate_fn(np.c_[pit["cx"], pit["cy"]], [cfg["pit"]["primary_radius_m"]]),
            "pad": core.pad_rate_fn(pad.geometry.values, [cfg["pad"]["primary_radius_m"]])}
    rows, nulls = [], {}
    for mi, mod in enumerate(("pit", "pad")):
        r = cfg[mod]["primary_radius_m"]
        for ci, ((coh, src), g) in enumerate(d.groupby(["cohort", "coord_source"])):
            xy = np.c_[g.x.to_numpy(), g.y.to_numpy()]
            xy = xy[elig[mod](xy)]
            seed = ek.child_seed(int(cfg["seed"]) + 7, fold=mi, arm=ci)
            nul = core.shift_null(xy, elig[mod], rate[mod], n_shift, nl["shift_min_m"], nl["shift_max_m"],
                                  nl["max_loss"], np.random.default_rng(seed), nl["max_tries"])
            v = [x[r] for x in nul["draws"]]
            e = core.excess(rate[mod](xy)[r] if len(xy) else float("nan"), v)
            nulls[(mod, coh, src)] = (e["observed"], np.array(v))
            rows.append(dict(modality=mod, cohort=coh, coord_source=src, radius_m=r, n_records=len(xy), **e,
                             mde=core.mde(len(xy), v), seed=seed))
    R = th.tag(pd.DataFrame(rows), "a", "descriptive_cohort")
    # Difference of normalised excess (newly documented minus listed), null draws paired at random.
    diffs = []
    rng = np.random.default_rng(int(cfg["seed"]) + 99)
    for mod in ("pit", "pad"):
        for src in sorted(d.coord_source.unique()):
            kn, ko = (mod, "newly_documented", src), (mod, "listed_2022", src)
            if kn in nulls and ko in nulls and len(nulls[kn][1]) and len(nulls[ko][1]):
                (on, vn), (oo, vo) = nulls[kn], nulls[ko]
                m = min(len(vn), len(vo))
                dn = (on - rng.permutation(vn)[:m]) / np.maximum(1 - vn.mean(), 1e-9)
                do = (oo - rng.permutation(vo)[:m]) / np.maximum(1 - vo.mean(), 1e-9)
                lo, hi = np.percentile(dn - do, [2.5, 97.5])
                diffs.append(dict(modality=mod, coord_source=src, diff_norm_excess=float((dn - do).mean()),
                                  lo=float(lo), hi=float(hi), label="descriptive only, no recall-equivalence gate"))
    out = th.outp(cfg, "cohort_rates")
    R.to_csv(out, index=False)
    js = out.with_suffix(".json")
    th.write_json(js, dict(cohort_counts=d.groupby(["cohort", "coord_source"]).size().rename("n").reset_index()
                           .to_dict(orient="records"), differences=diffs,
                           stratified_by_coord_source=coord is not None,
                           note="Newly documented includes reclassifications. Venango only. Descriptive."))
    print(R[["modality", "cohort", "coord_source", "n_records", "observed", "null_mean", "norm_excess", "norm_lo",
             "norm_hi"]].round(4).to_string(index=False))
    print("wrote", out, "\nwrote", js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
