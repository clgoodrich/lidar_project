"""Weighted identity bounds, interval diagnostics and the precision gate (7.5 S4, S6, section 7).

Purpose
    Bounds (protocol section 6). Per arm and per stratum, with weights w = 1 / pi.
        lower = sum w over confirmed wells / sum w
        upper = 1 - sum w over definite non-wells / sum w
    Every ambiguous and inaccessible site sits in the gap between them.
    Sampling uncertainty.
        - Heuristic. Clopper-Pearson on the Kish effective sample size, n_eff = (sum w)^2 / sum w^2, applied
          to the lower bound (its lower limit) and to the upper bound (its upper limit). Within one
          stratum weights are equal, so this reduces to Clopper-Pearson on counts, whose exact coverage
          requires independent binomial observations. Kish substitution is not exact survey inference.
        - Clustered. Bootstrap over clusters (lease or DEP pad), B = 2000, of both bounds. The reported
          interval is the wider of the two.
          Fewer than two clusters produces an inconclusive result with logical bounds [0, 1].
          Multi-cluster coverage still requires validation against the actual sampling design.
    Differences between strata or arms use Newcombe hybrid score intervals on the within-stratum counts
    (ek.newcombe_diff) for the lower-bound share. Era strata are always reported separately, never pooled.
    Arm B precision per score band is descriptive unless sized.
    Arm C. Confirmed wells with no DEP record per km2 searched. Search sensitivity comes from repeated
    independent searches (Chapman two-searcher estimate, a diagnostic) and from seeded controls (known DEP
    wells inside drawn cells, Clopper-Pearson). Density is bounded by observed / sensitivity limits.
    Without either source the result is conditional on the search and says so.
    Gate. Width from the interval's low end (lower bound) to its high end (upper bound) at or under the
    target width means success (precision). Wider is inconclusive. There is no failure for a measurement.

Inputs (expansions/7_scale/7_5_field_campaign/results/tables/)
    field_results_clean_v1.csv, field_sample_key_v1.csv, field_repeat_searches_v1.csv
Outputs
    field_bounds_v1.csv (one row per arm, stratum and pooled arm), field_analysis_v1.json
    expansions/7_scale/7_5_field_campaign/results/figures/field_bounds_v1.png

Run
    python expansions/7_scale/7_5_field_campaign/src/_field_analysis_bounds.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _field_sample_draw_frames import CFG, ek, load_cfg, need  # noqa: E402


def bounds(df: pd.DataFrame) -> dict:
    pi = df["pi"].to_numpy(float)
    if not len(pi) or not np.isfinite(pi).all() or np.any((pi <= 0) | (pi > 1)):
        raise ValueError("inclusion probabilities must be finite and in (0, 1]")
    w = 1.0 / df["pi"].to_numpy(float)
    conf = (df["identity"] == "confirmed_well").to_numpy()
    non = (df["identity"] == "definite_non_well").to_numpy()
    W = w.sum()
    lo_b, hi_b = w[conf].sum() / W, 1 - w[non].sum() / W
    n_eff = W ** 2 / (w ** 2).sum()
    k_lo = int(round(lo_b * n_eff)); k_hi = int(round(hi_b * n_eff)); ne = max(int(round(n_eff)), 1)
    _, cp_lo, _ = ek.clopper_pearson(min(k_lo, ne), ne)
    _, _, cp_hi = ek.clopper_pearson(min(k_hi, ne), ne)
    return {"n": int(len(df)), "n_eff": float(n_eff), "n_confirmed": int(conf.sum()), "n_non_well": int(non.sum()),
            "n_ambiguous": int(len(df) - conf.sum() - non.sum()),
            "n_inaccessible": int((df["outcome"] == "inaccessible").sum()),
            "lower_bound": float(lo_b), "upper_bound": float(hi_b), "cp_lo": float(cp_lo), "cp_hi": float(cp_hi)}


def cluster_boot(df: pd.DataFrame, B: int, seed: int) -> tuple[float, float]:
    cl = df.groupby("cluster_id")
    keys = list(cl.groups)
    parts = {k: g for k, g in cl}
    rng = np.random.default_rng(seed)
    los, his = [], []
    for _ in range(B):
        d = pd.concat([parts[keys[j]] for j in rng.integers(0, len(keys), len(keys))])
        b = bounds(d)
        los.append(b["lower_bound"]); his.append(b["upper_bound"])
    return float(np.percentile(los, 2.5)), float(np.percentile(his, 97.5))


def summarise(df: pd.DataFrame, label: dict, B: int, seed: int, target: float) -> dict:
    b = bounds(df)
    if df["cluster_id"].isna().any():
        raise ValueError("every observation needs a cluster_id")
    if df["cluster_id"].nunique() < 2:
        return {**label, **b, "boot_lo": None, "boot_hi": None,
                "interval_lo": 0.0, "interval_hi": 1.0, "width": 1.0,
                "gate": "inconclusive", "interval_method": "unidentified cluster variance",
                "evidence_level": "fewer than two independent clusters; [0, 1] is a logical bound, not a confidence interval"}
    bl, bh = cluster_boot(df, B, seed) if df["cluster_id"].nunique() > 1 else (b["cp_lo"], b["cp_hi"])
    lo, hi = min(b["cp_lo"], bl), max(b["cp_hi"], bh)
    width = hi - lo
    return {**label, **b, "boot_lo": bl, "boot_hi": bh, "interval_lo": lo, "interval_hi": hi, "width": width,
            "gate": "success (precision)" if width <= target else "inconclusive",
            "evidence_level": "d (confirmed) and c (steel) kept apart"}


def sensitivity(rep: pd.DataFrame, key: pd.DataFrame, clean: pd.DataFrame) -> dict:
    out = {}
    if len(rep):
        f1 = rep["identity_r1"] == "confirmed_well"
        f2 = rep["identity_r2"] == "confirmed_well"
        n1, n2, m = int(f1.sum()), int(f2.sum()), int((f1 & f2).sum())
        out["two_searcher"] = {"sites": int(len(rep)), "n1": n1, "n2": n2, "both": m,
                               "chapman_N": (n1 + 1) * (n2 + 1) / (m + 1) - 1,
                               "sens_searcher1": m / n2 if n2 else None, "note": "diagnostic, not a guarantee"}
    ctl = key[(key["arm"] == "C") & key["controls"].fillna("").astype(str).ne("")]
    if len(ctl):
        c = ctl.merge(clean[["site_id", "identity", "evidence_codes"]], on="site_id", how="left")
        n = int(c["controls"].astype(str).str.split(";").apply(len).sum())
        found = int(c["evidence_codes"].fillna("").str.contains("agency_record_tied_on_site").sum())
        p, lo, hi = ek.clopper_pearson(min(found, n), n)
        out["seeded_controls"] = {"n_controls": n, "found": found, "sensitivity": p, "lo": lo, "hi": hi}
    return out


def arm_c_density(clean: pd.DataFrame, key: pd.DataFrame, cell_m: float, sens: dict) -> dict:
    c = clean.merge(key[["site_id", "controls"]], on="site_id").query("arm == 'C'")
    if not len(c):
        return {"note": "no Arm C cells"}
    searched = c[c["outcome"] != "inaccessible"]
    area = len(searched) * cell_m ** 2 / 1e6
    new = int(((searched["identity"] == "confirmed_well") & searched["controls"].fillna("").astype(str).eq("")).sum())
    res = {"cells_searched": int(len(searched)), "cells_inaccessible": int(len(c) - len(searched)), "km2": area,
           "undocumented_confirmed": new, "per_km2_observed": new / area if area else None}
    sc = sens.get("seeded_controls")
    if sc and sc["lo"] > 0:
        res["per_km2_bounds_by_sensitivity"] = [new / area / sc["hi"], new / area / sc["lo"]] if area else None
    else:
        res["conditional"] = "search sensitivity not bounded. The density is conditional on the search"
    return res


def figure(tab: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # ek.PALETTE lost/found set (worst pair dE 21.1 deutan, dataviz validator --pairs all, in expkit).
    # Two marks per row, a filled circle (lower bound) and an open square (upper bound), so shape also encodes it.
    t = tab.reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(7, 0.4 * len(t) + 1.2))
    y = np.arange(len(t))
    ax.hlines(y, t["interval_lo"], t["interval_hi"], color=ek.PALETTE["grey"], lw=6, alpha=0.5, label="95% interval")
    ax.plot(t["lower_bound"], y, "o", color=ek.PALETTE["blue"], label="lower bound (confirmed share)")
    ax.plot(t["upper_bound"], y, "s", mfc="none", color=ek.PALETTE["orange"], label="upper bound (1 - non-well share)")
    ax.set_yticks(y, [f"{a} {s}" for a, s in zip(t["arm"], t["stratum"])])
    ax.set_xlim(0, 1)
    ax.set_xlabel("Share of sampled sites that are wells (identity bounds)")
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def analyse(cfg: dict, clean: pd.DataFrame, key: pd.DataFrame, rep: pd.DataFrame, B: int, out: Path,
            figs: Path | None = None) -> dict:
    df = clean.merge(key[["site_id", "stratum", "pi", "cluster_id", "era"]], on="site_id", how="left")
    ek.assert_rows(df, len(clean), "clean x key")
    ek.assert_no_nan(df["pi"], "pi")
    tgt = cfg["design"]["target_width"]
    rows = []
    for arm, g in df.groupby("arm"):
        rows.append(summarise(g, {"arm": arm, "stratum": "all (weighted)"}, B, cfg["master_seed"], tgt))
        for s, gs in g.groupby("stratum"):
            rows.append(summarise(gs, {"arm": arm, "stratum": s}, B, cfg["master_seed"] + 1, tgt))
    tab = pd.DataFrame(rows)
    tab.to_csv(out / "field_bounds_v1.csv", index=False)
    res = {"primary": cfg["design"]["primary"],
           "primary_result": tab[(tab["arm"] == "A") & (tab["stratum"] == "all (weighted)")].to_dict("records"),
           "era_strata_note": "era strata are reported separately and never pooled. Magnetometry misses wooden or removed casing"}
    a = df[df["arm"] == "A"].copy()
    if len(a):
        a["era_s"] = a["stratum"].str.split("|").str[-1]
        eras = sorted(a["era_s"].unique())
        diffs = {}
        for i, e1 in enumerate(eras):
            for e2 in eras[i + 1:]:
                g1, g2 = a[a["era_s"] == e1], a[a["era_s"] == e2]
                k1, k2 = int((g1["identity"] == "confirmed_well").sum()), int((g2["identity"] == "confirmed_well").sum())
                if len(g1) and len(g2):
                    diffs[f"{e1} minus {e2}"] = dict(zip(("diff", "lo", "hi"), ek.newcombe_diff(k1, len(g1), k2, len(g2))))
        res["era_differences_lower_bound_share"] = {"method": "Newcombe hybrid score, unweighted within-stratum counts, exploratory",
                                                    **diffs}
    sens = sensitivity(rep, key, clean)
    res["search_sensitivity"] = sens or {"note": "no repeat searches and no seeded controls. Recall is conditional only"}
    res["arm_C"] = arm_c_density(clean, key, cfg["arm_C"]["cell_m"], sens)
    (out / "field_analysis_v1.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    figure(tab, (figs or out) / "field_bounds_v1.png")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.5 S6 analysis with identity bounds.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--tables", default=str(ek.sub("7.5", "results/tables")))
    ap.add_argument("--B", type=int, default=2000)
    a = ap.parse_args(argv)
    t = Path(a.tables)
    try:
        clean = pd.read_csv(need(t / "field_results_clean_v1.csv", "clean field results (run the ingest)"))
        key = pd.read_csv(need(t / "field_sample_key_v1.csv", "sample key"))
        rp = t / "field_repeat_searches_v1.csv"
        rep = pd.read_csv(rp) if rp.exists() else pd.DataFrame()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    res = analyse(load_cfg(Path(a.config)), clean, key, rep, a.B, t, ek.sub("7.5", "results/figures"))
    print(json.dumps(res["primary_result"], indent=2, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
