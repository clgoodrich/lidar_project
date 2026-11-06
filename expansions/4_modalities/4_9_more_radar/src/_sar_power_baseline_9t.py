"""S1 of framework 4.9. Headroom and simulated power of a paired AUC gain, per stratum, before any purchase.

Purpose. From saved per-row baseline scores (y, block, score), compute per stratum the baseline AUC, headroom
(1 minus AUC) and blocks available. Strata are "all" and "lidar_weak" (targets in the lowest quartile of baseline
score, chosen before any SAR feature exists, against all decoys). Then simulate an arm.
  z      probit of the baseline score's mid-rank
  arm    z' = rho z + sqrt(1 - rho^2) e + shift y, with shift calibrated by bisection so the expected gain is g
  power  share of n_sims draws whose paired block-bootstrap lower bound exceeds delta_gain
A gain the ceiling cannot hold (AUC would pass 1) is marked infeasible with power 0.
Eligibility. Power at g = delta_gain + 0.01 at the primary rho is at least 0.80, and headroom is at least delta_gain
plus the median interval half-width. If no stratum is eligible the test is not run. The record then says "no room,
untestable at current baseline", which is a statement about the ceiling, not about radar.
Inputs (one or more --rows files).
  data/613590/results/nisar/nisar_pit_heldout_scores_613590_slc.csv (held, score column "rich lidar baseline")
  expansions/4_modalities/4_9_more_radar/data/processed/sar_baseline_rows_pit_9t.csv (assumed, see config)
Outputs.
  data/9t/results/sar_new/sar_power_by_stratum_9t.csv   one row per input, stratum, rho and g
  data/9t/results/sar_new/sar_power_eligibility_9t.json
Run.
  python expansions/4_modalities/4_9_more_radar/src/_sar_power_baseline_9t.py --rows CSV[:SCORECOL[:LABEL]] [more] [--n-sims 100] [--B 200] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata

import _sar_kit_4_9 as sk


def strata(y: np.ndarray, s: np.ndarray, q: float) -> dict:
    """Row masks. lidar_weak keeps targets with baseline score at or below the q quantile of target scores, and all decoys."""
    cut = np.quantile(s[y == 1], q)
    return {"all": np.ones(len(y), bool), "lidar_weak": (y == 0) | (s <= cut)}


def calibrate_shift(z, y, rho, g, draws, seed) -> float | None:
    """Shift so mean AUC(arm) - AUC(base) = g. None when the ceiling cannot hold g."""
    base = sk.auc(y, z)
    rng = np.random.default_rng(seed)
    E = rng.standard_normal((draws, len(z)))
    w = np.sqrt(1 - rho ** 2)

    def gain(sh):
        return np.mean([sk.auc(y, rho * z + w * e + sh * y) for e in E]) - base
    lo, hi = -5.0, 10.0
    if gain(hi) < g:
        return None
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if gain(mid) < g else (lo, mid)
    return (lo + hi) / 2


def power_table(y, s, blocks, cfg, seed, label) -> pd.DataFrame:
    P = cfg["prereg"]["power"]
    d = cfg["prereg"]["delta_gain"]
    rows = []
    for sname, m in strata(y, s, cfg["prereg"]["lidar_weak_quantile"]).items():
        yy, ss, bb = y[m], s[m], blocks[m]
        z = norm.ppf((rankdata(ss) - 0.5) / len(ss))
        base = sk.auc(yy, z)
        nb = len(np.unique(bb))
        ntb = len(np.unique(bb[yy == 1]))
        for ri, rho in enumerate(P["rho_pair"]):
            for gi, g in enumerate(P["gains"]):
                sd = sk.ek.child_seed(seed, ri, gi)
                sh = calibrate_shift(z, yy, rho, g, P["calib_draws"], sd)
                r = {"input": label, "stratum": sname, "n_targets": int(yy.sum()), "n_decoys": int((1 - yy).sum()), "n_blocks": nb, "n_target_blocks": ntb,
                     "baseline_auc": base, "headroom": 1 - base, "rho": rho, "g": g, "feasible": sh is not None}
                if sh is None:
                    rows.append({**r, "power": 0.0, "median_half_width": np.nan})
                    continue
                rng = np.random.default_rng(sd + 7)
                los, hw = [], []
                for k in range(P["n_sims"]):
                    arm = rho * z + np.sqrt(1 - rho ** 2) * rng.standard_normal(len(z)) + sh * yy
                    bt = sk.paired_gain_boot(yy, z, arm, bb, P["B_power"], int(rng.integers(1 << 31)))
                    los.append(bt["lo"])
                    hw.append((bt["hi"] - bt["lo"]) / 2)
                rows.append({**r, "power": float(np.mean(np.array(los) > d)), "median_half_width": float(np.median(hw))})
    return pd.DataFrame(rows)


def eligibility(tab: pd.DataFrame, cfg) -> dict:
    pr = cfg["prereg"]
    d, rho0 = pr["delta_gain"], pr["power"]["rho_primary"]
    g_pow = pr["power"].get("g_for_power") or round(d + 0.01, 4)
    out = {}
    for (inp, st), g in tab.groupby(["input", "stratum"]):
        row = g[(g.rho == rho0) & np.isclose(g.g, g_pow)]
        if not len(row):
            out[f"{inp}:{st}"] = {"eligible": False, "why": f"g = {g_pow} not in the grid"}
            continue
        r = row.iloc[0]
        hw = r.median_half_width if np.isfinite(r.median_half_width) else np.inf
        ok = bool(r.power >= pr["power"]["power_needed"] and r.headroom >= d + hw)
        out[f"{inp}:{st}"] = {"eligible": ok, "power": float(r.power), "headroom": float(r.headroom),
                              "median_half_width": float(r.median_half_width), "n_blocks": int(r.n_blocks),
                              "n_target_blocks": int(r.n_target_blocks),
                              "bootstrap_unreliable": bool(r.n_target_blocks < pr["min_blocks_bootstrap"])}
    any_ok = any(v["eligible"] for v in out.values())
    return {"delta_gain": d, "rho_primary": rho0, "g_for_power": g_pow, "strata": out, "any_eligible": any_ok,
            "record": "proceed to purchase request" if any_ok else "no room, untestable at current baseline"}


def read_rows(spec: str, cfg) -> tuple[np.ndarray, np.ndarray, np.ndarray, str, Path]:
    parts = spec.split(":")
    # Windows drive letters contain a colon. Rejoin the first two parts when the first is one letter.
    if len(parts[0]) == 1 and len(parts) > 1:
        parts = [parts[0] + ":" + parts[1]] + parts[2:]
    p = sk.need(Path(parts[0]), "baseline rows", cfg["inputs"]["baseline_rows_9t"])
    col = parts[1] if len(parts) > 1 else "score"
    label = parts[2] if len(parts) > 2 else p.stem
    df = pd.read_csv(p)
    for c in ("y", "block", col):
        if c not in df.columns:
            raise ValueError(f"{p} lacks column {c!r}")
    sk.ek.assert_no_nan(df.block, "block")
    df = df[np.isfinite(df[col])]
    return df.y.to_numpy(int), df[col].to_numpy(float), df.block.to_numpy(), label, p


def main(argv=None) -> int:
    cfg = sk.load_cfg()
    P = cfg["prereg"]["power"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rows", nargs="+", default=None, help="CSV[:score column[:label]]. Default the held 613590 file")
    ap.add_argument("--n-sims", type=int, default=P["n_sims"])
    ap.add_argument("--B", type=int, default=P["B_power"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    cfg["prereg"]["power"]["n_sims"], cfg["prereg"]["power"]["B_power"] = a.n_sims, a.B
    if a.rows is None:
        h = cfg["inputs"]["baseline_rows_613590"]
        a.rows = [f"{sk.resolve(h)}:{h['score_col']}:613590_heldout"]
    tabs, ins = [], []
    for spec in a.rows:
        y, s, b, label, p = read_rows(spec, cfg)
        ins.append(p)
        tabs.append(power_table(y, s, b, cfg, cfg["prereg"]["master_seed"], label))
    tab = pd.concat(tabs, ignore_index=True)
    el = eligibility(tab, cfg)
    out = Path(a.out) if a.out else sk.resolve(cfg["outputs"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "sar_power_by_stratum_9t.csv", index=False)
    (out / "sar_power_eligibility_9t.json").write_text(json.dumps(el, indent=2), encoding="utf-8")
    sk.prov(out, "sar_power_baseline_9t", inputs=ins, outputs=[out / "sar_power_by_stratum_9t.csv"], params=cfg["prereg"],
            seeds={"master": cfg["prereg"]["master_seed"]})
    print(tab.groupby(["input", "stratum"])[["baseline_auc", "headroom", "n_blocks"]].first().to_string())
    print(json.dumps(el, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
