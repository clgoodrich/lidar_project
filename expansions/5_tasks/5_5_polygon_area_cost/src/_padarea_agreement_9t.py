"""5.5 S4 and S5. Area agreement of model pad polygons with a reference outline, and the scale-factor calibration arm.

Purpose
    Pads are matched one to one by config match_rule (overlap_any, any positive overlap). The IoU >= 0.3 gate is a
    sensitivity in the summary, because it caps |r| at 1.204 and drops pads with large area error (review 5.5-01).
    Per pad. A_hat, A_ref, r = ln(A_hat / A_ref), absolute percent error, IoU, mean symmetric boundary distance and
    Hausdorff 95. Bland-Altman limits on the log scale. OLS of ln A_hat on ln A_ref (slope and intercept separate
    proportional from fixed bias). Strata by size tercile and canopy cover class.
    Primary (fw_5_5 section 8). Median r with a block-bootstrap interval (B = 2000, blocks are the unit) and P90 |r|.
    delta_area = ln(1 + tol / f) when the cost table gives f, else the configured fallback (ln 1.25). Success if the
    median interval sits inside +-delta and P90 |r| <= ln(1 + tol). Failure if the interval lies outside. Else
    inconclusive.
    S5 calibration arm. Blocks split in two halves at random (seeded). A scale factor exp(-median r) fitted on one half
    is applied to the other, then swapped. It is reported as useful only if cross-half median |r| drops in both.
    --reference survey (default, needs S3) or drawn (annotations, runnable now, exploratory, level a against level a).

Inputs (config_5_5.json)
    pad_products, annotations, pad_blocks, pad_cover
    survey + reference_area   assumed (S3) when --reference survey
Outputs
    expansions/5_tasks/5_5_polygon_area_cost/results/tables/pad_area_agreement_9t.csv
    expansions/5_tasks/5_5_polygon_area_cost/results/tables/pad_area_agreement_summary_9t.json
    (drawn reference writes ..._drawn_9t.csv / .json beside them so the survey files are never overwritten)
Run
    python expansions/5_tasks/5_5_polygon_area_cost/src/_padarea_agreement_9t.py --reference drawn
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _padarea_geometry_tools as gt  # noqa: E402

th, ek = gt.th, gt.ek


def reference(cfg, mode: str, pits):
    if mode == "drawn":
        plat, _ = gt.load_drawn(cfg)
        return gt.remove_pits(plat, pits) if cfg.get("subtract_pits") else plat
    sv = th.read_vector(th.inp(cfg, "survey"))
    th.inp(cfg, "reference_area")                 # S3 must have run (and its QC passed)
    sv = gt.clean(sv[sv.definition != "graded"]).dissolve("pad_id").reset_index()
    return gt.remove_pits(sv, pits) if cfg.get("subtract_pits") else sv


def stats(T: pd.DataFrame) -> dict:
    m = T.dropna(subset=["log_ratio"])
    r = m.log_ratio.to_numpy()
    la, lr = np.log(m.A_hat.to_numpy()), np.log(m.A_ref.to_numpy())
    slope, intercept = np.polyfit(lr, la, 1) if len(m) > 2 else (np.nan, np.nan)
    sd = float(np.std(r, ddof=1)) if len(r) > 1 else np.nan
    return dict(n=len(m), mean_r=float(r.mean()) if len(r) else np.nan, sd_r=sd,
                bland_altman_log=[float(r.mean() - 1.96 * sd), float(r.mean() + 1.96 * sd)] if len(r) > 1 else None,
                ols_slope=float(slope), ols_intercept=float(intercept),
                mape=float(m.abs_pct_err.mean()) if len(m) else np.nan,
                median_iou=float(m.iou.median()) if len(m) else np.nan,
                median_boundary_m=float(m.mean_boundary_m.median()) if "mean_boundary_m" in m else np.nan,
                median_hausdorff95_m=float(m.hausdorff95_m.median()) if "hausdorff95_m" in m else np.nan)


def calibration_arm(T: pd.DataFrame, seed: int) -> dict:
    m = T.dropna(subset=["log_ratio"])
    blocks = np.array(sorted(m.block_id.unique()))
    rng = np.random.default_rng(seed)
    half = set(rng.permutation(blocks)[: len(blocks) // 2])
    A, B = m[m.block_id.isin(half)], m[~m.block_id.isin(half)]
    out = {}
    for name, fit, test in (("fit_A_test_B", A, B), ("fit_B_test_A", B, A)):
        if not len(fit) or not len(test):
            out[name] = None
            continue
        shift = -float(fit.log_ratio.median())
        before = float(test.log_ratio.abs().median())
        after = float((test.log_ratio + shift).abs().median())
        out[name] = dict(scale_factor=float(np.exp(shift)), median_abs_r_before=before, median_abs_r_after=after,
                         improves=after < before)
    out["useful"] = bool(all(v and v["improves"] for k, v in out.items() if k.startswith("fit_")))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("--reference", choices=("survey", "drawn"))
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    mode = a.reference or cfg["reference"]
    pred = gt.load_pred(cfg)
    _, pits = gt.load_drawn(cfg)
    if cfg.get("subtract_pits"):
        pred = gt.remove_pits(pred, pits)
    ref = reference(cfg, mode, pits)
    pol = ek.policy_for("pad")
    T = gt.per_pad(pred, ref, "pad_id", pol["iou"], cfg["merge_overlap_frac"], cfg["match_rule"])
    ek.assert_rows(T, len(ref), "one row per reference pad")
    T["road_length_m"] = gt.road_length(ref, gt.load_roads(cfg), cfg["road_window_m"])
    bd = [gt.boundary_dist(pred.geometry.iloc[int(p)], ref.geometry.iloc[int(j)], cfg["boundary_sample_m"])
          if p >= 0 else (np.nan, np.nan) for p, j in zip(T.pred_row, T.ref_row)]
    T["mean_boundary_m"], T["hausdorff95_m"] = [x[0] for x in bd], [x[1] for x in bd]
    c = ref.geometry.centroid
    T["block_id"] = th.block_id_of(np.c_[c.x, c.y], th.read_vector(th.inp(cfg, "pad_blocks"), layer="blocks"))
    if th.has(cfg, "pad_cover"):
        cov = th.read_vector(th.inp(cfg, "pad_cover"))
        T = T.merge(pd.DataFrame(cov[["pad_id", "cover_class"]]).drop_duplicates("pad_id"), on="pad_id", how="left")
    T["size_tercile"] = pd.qcut(T.A_ref, 3, labels=["small", "medium", "large"]).astype(str)
    T["reference"] = mode
    T = th.tag(T, "a", "confirmatory_survey" if mode == "survey" else "exploratory_drawn_reference")
    dec = cfg["decision"]
    delta = gt.delta_area(dec["primary_tolerance"], dec["area_share_f"], dec["delta_area_fallback"])
    prim = gt.median_r_interval(T, cfg["bootstrap_B"], int(cfg["seed"]))
    Ts = gt.per_pad(pred, ref, "pad_id", pol["iou"], cfg["merge_overlap_frac"], cfg["match_rule_sensitivity"])
    Ts["block_id"] = T["block_id"].to_numpy()
    prim_s = gt.median_r_interval(Ts, cfg["bootstrap_B"], int(cfg["seed"]))
    strata = {col: T.dropna(subset=["log_ratio"]).groupby(col).log_ratio.agg(["size", "median"]).round(4)
              .reset_index().to_dict(orient="records") for col in ("size_tercile", "cover_class") if col in T}
    summary = dict(reference=mode, match_rule=cfg["match_rule"], policy=pol, primary=prim, delta_area=delta,
                   delta_source="ln(1 + tol / f)" if dec["area_share_f"] else "fallback ln(1.25), no cost table",
                   decision=gt.area_decision(prim, delta, dec["primary_tolerance"]), secondary=stats(T),
                   strata=strata, calibration_arm=calibration_arm(T, int(cfg["seed"]) + 5),
                   matched=int(T.matched.sum()), unmatched_reference=int((T.matched == 0).sum()),
                   sensitivity=dict(match_rule=cfg["match_rule_sensitivity"], iou_min=pol["iou"], primary=prim_s,
                                    decision=gt.area_decision(prim_s, delta, dec["primary_tolerance"]),
                                    matched=int(Ts.matched.sum()),
                                    note="An IoU gate caps |r| at ln(1/iou) for nested shapes. Not the primary."),
                   note="Area is level (a). It says nothing about wells.")
    o1, o2 = th.outp(cfg, "agreement"), th.outp(cfg, "agreement_summary")
    if mode == "drawn":
        o1 = o1.with_name(o1.stem.replace("_9t", "_drawn_9t") + o1.suffix)
        o2 = o2.with_name(o2.stem.replace("_9t", "_drawn_9t") + o2.suffix)
    T.to_csv(o1, index=False)
    th.write_json(o2, summary)
    print({k: summary[k] for k in ("reference", "primary", "delta_area", "decision")})
    print("wrote", o1, "\nwrote", o2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
