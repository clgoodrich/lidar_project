"""M0 and M1. Detection-limit arithmetic gate for satellite methane over Pennsylvania abandoned wells.

Purpose
    Compares the emission of an ordinary abandoned Pennsylvania well with the 90% detection limit (DL) of each
    satellite in the config. Writes the ratio R = DL / rate at the stated DL and at the best case, the aggregation
    count N = DL / mean rate against the most wells that share one footprint, a tail estimate when per-well rates
    are on file, and the M1 verdict (CLOSE or PROCEED) per gate in fw_4_4 section 10.
    Pure arithmetic. No spatial data except an optional count of DEP wells per footprint.

Inputs (from config_4_4.json, section m0)
    numbers with citations (Kang et al. 2014 mean rate, Carbon Mapper Tanager DL)
    data/_source/reference/dep_wells/venango_wells_all.gpkg          (optional, wells per footprint)
    data/_source/reference/legacy_data/US_Documented_Orphan_Wells.csv (optional, documented orphan count)
    expansions/4_modalities/4_4_methane_plumes/data/raw/kang2014_per_well_rates.csv (assumed, tail step)

Outputs (run folder expansions/4_modalities/4_4_methane_plumes/results/<YYYYMMDD>_methane_gate_<hash7>/)
    methane_gate_limit_pa.json     ratios, gates and the verdict
    methane_gate_limit_pa.csv      one row per instrument and DL scenario
    methane_gate_ratio_bars_pa.png log10 ratio bars with the parity and closure lines
    _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/4_modalities/4_4_methane_plumes/src/_methane_gate_limit_pa.py [--no-dep-count] [--out-root DIR]
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

KG_DAY_TO_KG_H = 1.0 / 24.0


# ----------------------------------------------------------------------------- pieces
def wells_per_footprint(points_xy: np.ndarray, gsd_m: float) -> dict:
    """Most wells in one square footprint of side gsd_m, over four grid offsets. Points in a metric CRS.

    Two counts. 'max_raw' counts every record. 'max' counts distinct coordinates (0.1 m), because DEP stacks
    whole leases on one placeholder coordinate (41 LIPKO ALAN wells share one point in venango_wells_all).
    Stacked records are real wells with unknown positions, so they cannot be placed in one 30 m pixel.
    """
    if len(points_xy) == 0:
        return {"max": 0, "max_raw": 0, "p99_occupied": 0.0, "n_points": 0, "n_distinct": 0, "max_stacked": 0}

    def scan(xy):
        best, p99 = 0, 0.0
        for ox, oy in ((0, 0), (0.5, 0), (0, 0.5), (0.5, 0.5)):
            ij = np.floor(xy / gsd_m + np.array([ox, oy])).astype(np.int64)
            _, counts = np.unique(ij, axis=0, return_counts=True)
            best, p99 = max(best, int(counts.max())), max(p99, float(np.percentile(counts, 99)))
        return best, p99
    uniq, stack = np.unique(np.round(points_xy, 1), axis=0, return_counts=True)
    raw, _ = scan(points_xy)
    best, p99 = scan(uniq)
    return {"max": best, "max_raw": raw, "p99_occupied": p99, "n_points": int(len(points_xy)),
            "n_distinct": int(len(uniq)), "max_stacked": int(stack.max()), "n_stacked_locations": int((stack > 1).sum())}


def fit_tail(rates_kg_h: np.ndarray, threshold_kg_h: float, B: int, seed: int) -> dict:
    """P(rate >= threshold) under a lognormal and a log-logistic (heavier tail) fit, with a well-level bootstrap."""
    from scipy import stats
    r = np.asarray(rates_kg_h, float)
    n_nonpos = int((r <= 0).sum())
    r = r[r > 0]
    if len(r) < 5:
        return {"error": f"only {len(r)} positive rates", "n_nonpositive_dropped": n_nonpos}

    def p_exceed(x):
        lmu, lsd = np.mean(np.log(x)), np.std(np.log(x), ddof=1)
        p_ln = float(stats.norm.sf((np.log(threshold_kg_h) - lmu) / lsd)) if lsd > 0 else float(x.max() >= threshold_kg_h)
        try:
            c, loc, scale = stats.fisk.fit(x, floc=0)
            p_ll = float(stats.fisk.sf(threshold_kg_h, c, loc=loc, scale=scale))
        except Exception:  # noqa: BLE001
            p_ll = float("nan")
        return p_ln, p_ll

    p_ln, p_ll = p_exceed(r)
    rng = np.random.default_rng(seed)
    draws = np.array([p_exceed(r[rng.integers(0, len(r), len(r))]) for _ in range(B)])
    out = {"n_wells_used": int(len(r)), "n_nonpositive_dropped": n_nonpos, "threshold_kg_h": threshold_kg_h,
           "largest_rate_kg_h": float(r.max()), "extrapolation_multiple": float(threshold_kg_h / r.max())}
    for j, name in enumerate(("lognormal", "loglogistic")):
        # SH-01. Failed fits are counted. Any undefined draw makes the interval undefined (NaN, NaN).
        und = ek.undefined_share(draws[:, j])
        if und > 0:
            lo, hi = float("nan"), float("nan")
        else:
            lo, hi = np.percentile(draws[:, j], [2.5, 97.5])
        out[name] = {"p_exceed": (p_ln, p_ll)[j], "lo": float(lo), "hi": float(hi), "undefined_share": und}
    return out


def gate_mean(r_best: float, closure: float) -> str:
    return "success" if r_best <= 1 else "failure" if r_best >= closure else "inconclusive"


def gate_aggregation(n_needed: float, wells_in_fp: float, closure: float) -> str:
    if n_needed <= wells_in_fp:
        return "success"
    return "failure" if n_needed >= closure * max(wells_in_fp, 1) else "inconclusive"


NOT_IDENTIFIABLE = "not identifiable by extrapolation"


def gate_tail(tail: dict | None, largest_kg_h: float | None, dl_best: float, population: dict,
              max_extrapolation: float | None = None) -> dict:
    """fw_4_4 section 10 tail row. Uses the largest population scenario so the gate errs toward PROCEED.

    4.4-01. A fitted tail says nothing about rates far beyond the data. When the detection limit lies above
    max_extrapolation times the largest observed rate, the verdict is 'not identifiable by extrapolation'.
    max_extrapolation is a user decision (config m0.tail_max_extrapolation_multiple). While it is null, any
    limit above the largest observed rate is refused the same way. Success needs the lower bound of the
    expected exceeding count to reach one well (the old check 'lower bound > 0' was always true)."""
    if not tail or "error" in tail:
        return {"verdict": "inconclusive", "why": "per-well rates not on file" if not tail else tail["error"]}
    n_pop = max(population.values())
    largest = largest_kg_h if largest_kg_h is not None else tail.get("largest_rate_kg_h")
    data_max = max(v for v in (tail.get("largest_rate_kg_h"), largest_kg_h) if v is not None)
    mult = dl_best / data_max
    base = {"population_used": n_pop, "largest_rate_kg_h": largest, "extrapolation_multiple": mult,
            "max_extrapolation_multiple": max_extrapolation}
    allowed = 1.0 if max_extrapolation is None else float(max_extrapolation)
    if mult > allowed:
        why = (f"detection limit {dl_best:g} kg/h is {mult:.1f} times the largest observed rate {data_max:g} kg/h. "
               + ("No extrapolation multiple is declared (user decision)." if max_extrapolation is None else
                  f"The declared limit is {allowed:g} times."))
        return {"verdict": NOT_IDENTIFIABLE, "why": why, **base}
    exp = {fit: {s: tail[fit][s] * n_pop for s in ("p_exceed", "lo", "hi")} for fit in ("lognormal", "loglogistic")}
    vals = [exp[f][s] for f in exp for s in ("lo", "hi")]
    if not all(np.isfinite(vals)):
        return {"verdict": "inconclusive", "why": "tail bootstrap interval undefined (SH-01)", "expected_count": exp,
                **base}
    hi_upper = max(exp[f]["hi"] for f in exp)
    lo_lower = min(exp[f]["lo"] for f in exp)
    if lo_lower >= 1:
        v = "success"
    elif hi_upper < 1 and largest is not None and largest < dl_best:
        v = "failure"
    else:
        v = "inconclusive"
    return {"verdict": v, "expected_count": exp, **base}


def verdict(gates: dict) -> dict:
    """M1. CLOSE for PA small-well attribution when the mean and aggregation gates fail. The tail keeps M2 alive."""
    close = gates["mean"] == "failure" and gates["aggregation"] == "failure"
    proceed = gates["mean"] == "success" or gates["aggregation"] == "success"
    v = "CLOSE" if close else "PROCEED" if proceed else "INCONCLUSIVE"
    tail = gates["tail"]["verdict"]
    m2 = "live (tail success)" if tail == "success" else "live for the tail only (tail inconclusive)" \
        if tail == "inconclusive" else "closed for Pennsylvania (tail failure). Other basins stay open (M4)"
    return {"small_well_attribution": v, "m2_large_leaker_branch": m2,
            "scope": "Routine satellite screening of individual ordinary small wells, under the stated instrument "
                     "conditions only. Does not bound rare large emitters, aggregation elsewhere, other basins or other instruments."}


# ----------------------------------------------------------------------------- main
def run(cfg: dict, out_root: Path | None = None, dep_count: bool = True, rates_csv: Path | None = None) -> dict:
    m0 = cfg["m0"]
    we = m0["well_emission"]
    mean_kg_h = we["mean_kg_per_day"] * KG_DAY_TO_KG_H
    factor, closure = float(m0["best_case_factor"]), float(m0["closure_ratio"])
    run_dir = ek.new_run(io.EXP, "methane_gate", m0, base=out_root,
                         why="M0 detection-limit arithmetic gate and M1 verdict (fw_4_4 section 7).")
    inputs = [io.CONFIG_PATH]

    # wells per footprint
    fp_src = io.resolve(m0["wells_per_footprint"]["from_dep_points"])
    dl0 = m0["detection_limits"][0]
    wpf = {"source": "fallback", "max": int(m0["wells_per_footprint"]["fallback_max_wells"])}
    mode = m0["wells_per_footprint"].get("count_mode", "distinct_locations")
    if dep_count and fp_src is not None and fp_src.exists():
        import geopandas as gpd
        g = io.to_metric(gpd.read_file(fp_src), cfg["metric_crs"])
        g = g[g.geometry.notna() & ~g.geometry.is_empty]
        xy = np.c_[g.geometry.x.values, g.geometry.y.values]
        wpf = {"source": str(fp_src), **wells_per_footprint(xy, float(dl0["gsd_m"]))}
        if mode == "raw_records":
            wpf["max"] = wpf["max_raw"]
        wpf["count_mode"] = mode
        inputs.append(fp_src)

    # population for the tail
    pop = dict(m0["population"]["abandoned_scenarios"])
    oc = io.resolve(m0["population"]["documented_orphan_csv"])
    if oc is not None and oc.exists():
        n_orphan = int(len(pd.read_csv(oc, usecols=[0], encoding="utf-8-sig")))
        pop["documented_orphans_2022"] = n_orphan
        inputs.append(oc)

    # per-well rates (assumed input)
    rp = rates_csv or io.resolve(we["per_well_rates_csv"])
    rates = None
    if rp is not None and Path(rp).exists():
        df = pd.read_csv(rp)
        if "rate_kg_per_day" not in df.columns:
            raise ValueError(f"{rp}: needs column rate_kg_per_day ({we['per_well_rates_schema']})")
        rates = df["rate_kg_per_day"].to_numpy(float) * KG_DAY_TO_KG_H
        inputs.append(Path(rp))
    largest = we.get("largest_measured_kg_per_day")
    largest_kg_h = None if largest is None else float(largest) * KG_DAY_TO_KG_H

    rows, per_instrument = [], []
    for dl in m0["detection_limits"]:
        lo, hi = float(dl["pod90_low_kg_per_h"]), float(dl["pod90_high_kg_per_h"])
        dl_best = lo / factor
        for scen, val in (("stated_low", lo), ("stated_high", hi), ("best_case_low", lo / factor),
                          ("best_case_high", hi / factor)):
            rows.append({"instrument": dl["instrument"], "scenario": scen, "dl_kg_h": val, "mean_rate_kg_h": mean_kg_h,
                         "ratio_R": val / mean_kg_h, "log10_R": float(np.log10(val / mean_kg_h)),
                         "aggregation_N": val / mean_kg_h, "wells_in_footprint_max": wpf["max"],
                         "conditions": dl["conditions"], "source": dl["source"]})
        tail = fit_tail(rates, dl_best, int(m0["tail_bootstrap_B"]), int(m0["seed"])) if rates is not None else None
        r_best = dl_best / mean_kg_h
        gates = {"mean": gate_mean(r_best, closure),
                 "aggregation": gate_aggregation(r_best, wpf["max"], closure),
                 "tail": gate_tail(tail, largest_kg_h, dl_best, pop, m0.get("tail_max_extrapolation_multiple")),
                 "aggregation_sensitivity_raw_records": gate_aggregation(r_best, wpf.get("max_raw", wpf["max"]), closure)}
        per_instrument.append({"instrument": dl["instrument"], "dl_best_kg_h": dl_best, "R_mean_stated_low": lo / mean_kg_h,
                               "R_mean_stated_high": hi / mean_kg_h, "R_mean_best_case": r_best,
                               "R_high_best_case": (dl_best / largest_kg_h) if largest_kg_h else None,
                               "aggregation_N_best_case": r_best, "tail_fit": tail, "gates": gates,
                               "verdict": verdict(gates)})

    tab = pd.DataFrame(rows)
    csv = run_dir / "methane_gate_limit_pa.csv"
    tab.to_csv(csv, index=False)
    js = run_dir / "methane_gate_limit_pa.json"
    out = {"mean_rate_kg_per_day": we["mean_kg_per_day"], "mean_rate_kg_per_h": mean_kg_h,
           "mean_rate_source": we["source"], "best_case_factor": factor, "closure_ratio": closure,
           "wells_per_footprint": wpf, "population": pop, "instruments": per_instrument,
           "overall_verdict": per_instrument[0]["verdict"]["small_well_attribution"] if len(per_instrument) == 1 else
           ("CLOSE" if all(p["verdict"]["small_well_attribution"] == "CLOSE" for p in per_instrument) else "MIXED"),
           "evidence_level": "none of (a) to (d). Arithmetic only.",
           "verify": "Every figure tagged VERIFY in config_4_4.json must be read in its source before this verdict is final."}
    js.write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    png = run_dir / "methane_gate_ratio_bars_pa.png"
    _figure(tab, closure, png)
    ek.write_provenance(run_dir, inputs=inputs, outputs=[csv, js, png], params=m0, seeds={"tail": m0["seed"]})
    return {"run_dir": run_dir, "json": js, "csv": csv, "png": png, "result": out}


def _figure(tab: pd.DataFrame, closure: float, png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    P = ek.PALETTE  # lost/found palette, worst pair dE 21.1 deutan (dataviz validator --pairs all, CLAUDE.md)
    fig, ax = plt.subplots(figsize=(7, 3.2 + 0.3 * len(tab)))
    lab = [f"{a} {b.replace('_', ' ')}" for a, b in zip(tab.instrument, tab.scenario)]
    best = tab.scenario.str.startswith("best")
    ax.barh(lab, tab.log10_R, color=[P["orange"] if b else P["blue"] for b in best],
            hatch=["//" if b else "" for b in best], edgecolor=P["charcoal"])
    ax.axvline(0, color=P["charcoal"], lw=1)
    ax.axvline(np.log10(closure), color=P["dark_red"], lw=1.5, ls="--")
    ax.text(np.log10(closure) + 0.05, 0.02, f"closure at R = {closure:g}", fontsize=8, color=P["dark_red"],
            transform=ax.get_xaxis_transform())
    ax.set_xlim(min(0, float(tab.log10_R.min())) - 0.1, float(tab.log10_R.max()) + 0.4)
    ax.set_xlabel("log10 R. R = detection limit / mean well rate. 0 is detectable")
    ax.set_title("Detection limit over the mean abandoned-well rate", fontsize=10)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=io.CONFIG_PATH)
    ap.add_argument("--out-root", type=Path, default=None, help="parent of the run folder (default expansion results/)")
    ap.add_argument("--rates-csv", type=Path, default=None, help="per-well rates CSV (overrides config)")
    ap.add_argument("--no-dep-count", action="store_true", help="skip counting DEP wells per footprint")
    a = ap.parse_args()
    r = run(io.load_config(a.config), a.out_root, dep_count=not a.no_dep_count, rates_csv=a.rates_csv)
    print(json.dumps({"verdict": r["result"]["instruments"][0]["verdict"], "json": str(r["json"])}, indent=2))


if __name__ == "__main__":
    main()
