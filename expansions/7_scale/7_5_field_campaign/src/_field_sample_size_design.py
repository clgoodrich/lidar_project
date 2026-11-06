"""Sample-size table and design check for the field campaign (7.5 S2).

Purpose
    n per estimate = 1.96^2 x 0.25 / d^2 under simple random sampling (ek.n_for_proportion), inflated by
    the design effect (default 1.5) and by the expected inaccessible share (default 20%), since every
    inaccessible site stays in the frame as ambiguous and widens the bounds.
    For each arm and stratum in the frame counts, say whether the allocated n supports a sized estimate
    at each d, or is exploratory only. Also report the expected Clopper-Pearson width at p = 0.5 for the
    allocated effective n, and the bound width when the expected inaccessible share sits in the gap.
    Forty sites in total cannot support five score bins. The table shows it.
    The share has two bounds with the inaccessible gap between them. n = 182 sizes each bound to +/-0.10 but
    the bound width is then 0.407, over the 0.30 target. The table gives the n the target needs (746 at the
    defaults) and says when no n can give +/-d because the gap alone is wider (review 7.5-01).

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


N_MAX = 20000


def n_for_width(cfg: dict, width: float) -> int | None:
    """Smallest allocated n whose expected bound width (with the inaccessible gap) is at or under width.
    None when the gap alone already reaches the width, so no n can meet it (review 7.5-01)."""
    if cfg["design"]["inaccessible_share"] >= width:
        return None
    lo, hi = 2, N_MAX
    if expected_width(hi, cfg)["bound_width_with_gap"] > width:
        return None
    for n in range(lo, hi + 1):           # widths are not strictly monotone after rounding, so scan
        if expected_width(n, cfg)["bound_width_with_gap"] <= width:
            return n
    return None


def size_table(cfg: dict) -> pd.DataFrame:
    """n per estimate. n_with_deff_and_access sizes each identity bound alone (+/-d on one bound).
    It ignores the inaccessible gap between the bounds, so it does not give a +/-d share. n_with_gap does.
    n_for_target_width is the n the precision gate needs (bound width at or under the target)."""
    d = cfg["design"]
    rows = []
    n_target = n_for_width(cfg, d["target_width"])
    for dt in d["d_targets"]:
        srs = ek.n_for_proportion(dt, deff=1.0)
        clus = ek.n_for_proportion(dt, deff=d["deff"])
        n_acc = int(np.ceil(clus / (1 - d["inaccessible_share"])))
        ng = n_for_width(cfg, 2 * dt)
        rows.append({"d": dt, "n_srs": srs, "n_with_deff": clus, "deff": d["deff"],
                     "n_with_deff_and_access": n_acc, "inaccessible_share": d["inaccessible_share"],
                     "bound_width_at_that_n": expected_width(n_acc, cfg)["bound_width_with_gap"],
                     "n_with_gap": ng if ng is not None else "unreachable (gap alone reaches 2d)",
                     "target_width": d["target_width"], "n_for_target_width": n_target})
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
        # +/-d on the share needs the whole bound interval, gap included, within 2d (review 7.5-01).
        sized = [f"+/-{dt:.2f}" for dt in tab["d"] if w["bound_width_with_gap"] <= 2 * dt]
        per_bound = [f"+/-{dt:.2f}" for dt, need in zip(tab["d"], tab["n_with_deff_and_access"]) if n >= need]
        rows.append({"arm": arm, "stratum": stratum, "n_alloc": n, **w,
                     "supports": ", ".join(sized) if sized else "exploratory only",
                     "per_bound_only": ", ".join(per_bound) if per_bound else "none",
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
