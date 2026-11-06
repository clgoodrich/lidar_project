"""Sample-size table and design check for the field campaign (7.5 S2).

Purpose
    n per estimate = 1.96^2 x 0.25 / d^2 under simple random sampling (ek.n_for_proportion), inflated by
    the design effect (default 1.5) and by the expected inaccessible share (default 20%), since every
    inaccessible site stays in the frame as ambiguous and widens the bounds.
    For each arm and stratum in the frame counts, say whether the allocated n supports a sized estimate
    at each d, or is exploratory only. Also report the expected Clopper-Pearson width at p = 0.5 for the
    allocated effective n, and the bound width when the expected inaccessible share sits in the gap.
    Forty sites in total cannot support five score bins. The table shows it.

Inputs
    config_7_5.json (d targets, deff, inaccessible share), optional field_frame_counts_v1.csv from the draw
Outputs
    expansions/7_scale/7_5_field_campaign/results/tables/field_sample_size_v1.csv
    expansions/7_scale/7_5_field_campaign/results/tables/field_design_check_v1.csv (with counts)

Run
    python expansions/7_scale/7_5_field_campaign/src/_field_sample_size_design.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _field_sample_draw_frames import CFG, ek, load_cfg  # noqa: E402


def size_table(cfg: dict) -> pd.DataFrame:
    d = cfg["design"]
    rows = []
    for dt in d["d_targets"]:
        srs = ek.n_for_proportion(dt, deff=1.0)
        clus = ek.n_for_proportion(dt, deff=d["deff"])
        rows.append({"d": dt, "n_srs": srs, "n_with_deff": clus, "deff": d["deff"],
                     "n_with_deff_and_access": int(np.ceil(clus / (1 - d["inaccessible_share"]))),
                     "inaccessible_share": d["inaccessible_share"]})
    return pd.DataFrame(rows)


def expected_width(n_alloc: int, cfg: dict) -> dict:
    d = cfg["design"]
    n_acc = n_alloc * (1 - d["inaccessible_share"])
    n_eff = n_acc / d["deff"]
    k = int(round(0.5 * n_eff))
    _, lo, hi = ek.clopper_pearson(k, max(int(round(n_eff)), 1))
    gap = d["inaccessible_share"]          # inaccessible weight sits between the bounds
    return {"n_eff": round(n_eff, 1), "cp_width_p05": round(hi - lo, 3), "bound_width_with_gap": round(hi - lo + gap, 3)}


def design_check(cfg: dict, counts: pd.DataFrame) -> pd.DataFrame:
    tab = size_table(cfg)
    rows = []
    groups = [("all", "all", int(counts["n_h"].sum()))] + [
        (r["arm"], r["stratum"], int(r["n_h"])) for _, r in counts.iterrows()] + [
        (arm, "arm total", int(g["n_h"].sum())) for arm, g in counts.groupby("arm")]
    for arm, stratum, n in groups:
        w = expected_width(n, cfg)
        sized = [f"+/-{dt:.2f}" for dt, need in zip(tab["d"], tab["n_with_deff_and_access"]) if n >= need]
        rows.append({"arm": arm, "stratum": stratum, "n_alloc": n, **w,
                     "supports": ", ".join(sized) if sized else "exploratory only",
                     "meets_target_width": w["bound_width_with_gap"] <= cfg["design"]["target_width"]})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.5 S2 sample-size table and design check.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--counts", default=str(ek.sub("7.5", "results/tables") / "field_frame_counts_v1.csv"))
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    t = ek.sub("7.5", "results/tables")
    tab = size_table(cfg)
    tab.to_csv(t / "field_sample_size_v1.csv", index=False)
    print(tab.to_string(index=False))
    if Path(a.counts).exists():
        chk = design_check(cfg, pd.read_csv(a.counts))
        chk.to_csv(t / "field_design_check_v1.csv", index=False)
        print(chk.to_string(index=False))
    else:
        print(f"no frame counts at {a.counts}. Run _field_sample_draw_frames.py for the per-stratum check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
