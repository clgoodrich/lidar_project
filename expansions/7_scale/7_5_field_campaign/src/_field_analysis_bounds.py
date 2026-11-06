"""Weighted identity bounds, interval diagnostics and the precision gate (7.5 S4, S6, section 7).

Purpose
    Bounds (protocol section 6). Per arm and per stratum, with weights w = 1 / pi.
        lower = sum w over confirmed wells / sum w
        upper = 1 - sum w over definite non-wells / sum w
    Every ambiguous and inaccessible site sits in the gap between them.
    Sampling uncertainty (review F04). Design-based, from the declared strata, clusters (PSUs) and pi.
        - Variance. Linearisation (ultimate cluster) variance of each weighted bound, PSUs nested in strata.
          A stratum taken whole (all pi = 1) adds no variance. A cluster that spans strata collapses the strata.
        - Interval. Korn-Graubard design-based Clopper-Pearson. Effective n = R (1 - R) / v, capped at n and
          scaled by (t_{n-1} / t_df)^2. With v = 0 the effective n is the PSU count, so copies inside one
          cluster add nothing. The reported interval runs from the lower bound's low limit to the upper
          bound's high limit. The Kish columns cp_lo and cp_hi stay as diagnostics only.
        - Refusal. Fewer than two clusters, a sampled stratum with one PSU, or no degrees of freedom give
          inconclusive with logical bounds [0, 1] and the reason in interval_method.
    Differences between strata or arms use Newcombe hybrid score intervals on the within-stratum counts
    (ek.newcombe_diff) for the lower-bound share. Era strata are always reported separately, never pooled.
    Arm B precision per score band is descriptive unless sized.
    Arm C. Confirmed wells with no tied agency record per km2 searched, from the child well table. Every
    well counts, several per cell, with or without a control in the cell. Search sensitivity comes from
    repeated independent searches (Chapman two-searcher estimate, a diagnostic) and from seeded controls
    (known DEP wells inside searched cells, Clopper-Pearson, counted per control well). Density is bounded by observed / sensitivity limits.
    Without either source the result is conditional on the search and says so.
    Gate. Width from the interval's low end (lower bound) to its high end (upper bound) at or under the
    target width means success (precision). Wider is inconclusive. There is no failure for a measurement.

Inputs (expansions/7_scale/7_5_field_campaign/results/tables/)
    field_results_clean_v1.csv, field_sample_key_v1.csv, field_repeat_searches_v1.csv, field_wells_clean_v1.csv
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


def _unidentified(label: dict, b: dict, why: str) -> dict:
    return {**label, **b, "var_lower": None, "var_upper": None, "n_psu": None, "df": None,
            "interval_lo": 0.0, "interval_hi": 1.0, "width": 1.0, "gate": "inconclusive",
            "interval_method": f"unidentified design variance. {why}",
            "evidence_level": "[0, 1] is a logical bound, not a confidence interval"}


def design_variance(df: pd.DataFrame, y: np.ndarray, strat_col: str = "stratum", psu_col: str = "cluster_id") -> dict:
    """Linearisation (ultimate cluster) variance of the weighted share R = sum w y / sum w (review F04).

    PSUs are the clusters, nested in the sampling strata. A stratum whose sites all have pi = 1 was taken
    whole and adds no sampling variance. If one cluster sits in two strata the PSUs are not nested, so the
    strata are collapsed for the variance (one stratum, clusters as PSUs). No finite-population correction.
        z_hi = sum over sites in PSU i of stratum h of w (y - R) / sum w
        v = sum_h n_h / (n_h - 1) sum_i (z_hi - mean_h z)^2,   df = PSUs - strata
    Returns ok False with a reason when the variance is not identified (a sampled stratum with one PSU).
    """
    w = 1.0 / df["pi"].to_numpy(float)
    W = w.sum()
    R = float((w * y).sum() / W)
    d = pd.DataFrame({"h": df[strat_col].astype(str).to_numpy(), "psu": df[psu_col].astype(str).to_numpy(),
                      "z": w * (y - R) / W, "cert": df["pi"].to_numpy(float) >= 1.0})
    note = "strata as drawn, clusters nested"
    if (d.groupby("psu")["h"].nunique() > 1).any():
        d["h"] = "collapsed"
        d["cert"] = bool(d["cert"].all())
        note = "a cluster spans strata, so strata are collapsed for the variance"
    if d["cert"].all():
        return {"ok": True, "R": R, "v": 0.0, "n_psu": int(d["psu"].nunique()), "df": None, "census": True, "note": note}
    s = d[~d["cert"]]
    z = s.groupby(["h", "psu"])["z"].sum().reset_index()
    nh = z.groupby("h").size()
    one = sorted(nh[nh < 2].index)
    if one:
        return {"ok": False, "why": f"stratum {one[0]} has one PSU ({len(one)} such strata). Collapse strata or add clusters"}
    v = 0.0
    for h, g in z.groupby("h"):
        n = len(g)
        v += n / (n - 1) * float(((g["z"] - g["z"].mean()) ** 2).sum())
    dof = int(len(z) - len(nh))
    if dof < 1:
        return {"ok": False, "why": "no degrees of freedom left for the variance"}
    return {"ok": True, "R": R, "v": float(v), "n_psu": int(d["psu"].nunique()), "df": dof, "census": False, "note": note}


def korn_graubard(R: float, v: float, n: int, n_psu: int, dof: int, alpha: float = 0.05) -> tuple[float, float, float]:
    """Korn and Graubard (1998) design-based Clopper-Pearson interval for a survey share.
    Effective n = R (1 - R) / v, capped at n, times (t_{n-1} / t_df)^2. When v = 0 (all sites agree) the
    effective n is the number of PSUs, so copies inside one cluster add no sample size.
    Returns (lo, hi, effective n after the df scaling)."""
    from scipy.stats import beta, t
    ne = R * (1 - R) / v if v > 0 else float(n_psu)
    ne = min(ne, float(n)) * (t.ppf(1 - alpha / 2, n - 1) / t.ppf(1 - alpha / 2, dof)) ** 2
    k = R * ne
    lo = 0.0 if k <= 0 else float(beta.ppf(alpha / 2, k, ne - k + 1))
    hi = 1.0 if k >= ne else float(beta.ppf(1 - alpha / 2, k + 1, ne - k))
    return lo, hi, float(ne)


def summarise(df: pd.DataFrame, label: dict, target: float, strat_col: str = "stratum") -> dict:
    b = bounds(df)
    if df["cluster_id"].isna().any():
        raise ValueError("every observation needs a cluster_id")
    if df["cluster_id"].nunique() < 2:
        return _unidentified(label, b, "fewer than two independent clusters")
    conf = (df["identity"] == "confirmed_well").to_numpy(float)
    up = 1.0 - (df["identity"] == "definite_non_well").to_numpy(float)
    vl, vu = design_variance(df, conf, strat_col), design_variance(df, up, strat_col)
    if not vl["ok"]:
        return _unidentified(label, b, vl["why"])
    n = len(df)
    if vl["census"]:
        lo, hi = b["lower_bound"], b["upper_bound"]
        method = "census of the frame (all pi = 1). No sampling variance"
    else:
        lo = korn_graubard(vl["R"], vl["v"], n, vl["n_psu"], vl["df"])[0]
        hi = korn_graubard(vu["R"], vu["v"], n, vu["n_psu"], vu["df"])[1]
        method = f"Korn-Graubard on linearisation variance, {vl['n_psu']} PSUs, df {vl['df']}, {vl['note']}"
    width = hi - lo
    return {**label, **b, "var_lower": vl["v"], "var_upper": vu["v"], "n_psu": vl["n_psu"], "df": vl["df"],
            "interval_lo": lo, "interval_hi": hi, "width": width,
            "gate": "success (precision)" if width <= target else "inconclusive", "interval_method": method,
            "evidence_level": "d (confirmed) and c (steel) kept apart"}


def _controls(key: pd.DataFrame) -> pd.DataFrame:
    """One row per listed control well (DEP permit) per Arm C cell."""
    k = key[key["arm"] == "C"][["site_id", "controls"]].copy()
    k["control_id"] = k["controls"].fillna("").astype(str).str.split(";")
    k = k.explode("control_id")
    k["control_id"] = k["control_id"].astype(str).str.strip()
    return k[k["control_id"].ne("") & k["control_id"].ne("nan")][["site_id", "control_id"]]


def sensitivity(rep: pd.DataFrame, key: pd.DataFrame, clean: pd.DataFrame, wells: pd.DataFrame | None = None) -> dict:
    out = {}
    if len(rep):
        f1 = rep["identity_r1"] == "confirmed_well"
        f2 = rep["identity_r2"] == "confirmed_well"
        n1, n2, m = int(f1.sum()), int(f2.sum()), int((f1 & f2).sum())
        out["two_searcher"] = {"sites": int(len(rep)), "n1": n1, "n2": n2, "both": m,
                               "chapman_N": (n1 + 1) * (n2 + 1) / (m + 1) - 1,
                               "sens_searcher1": m / n2 if n2 else None, "note": "diagnostic, not a guarantee"}
    ctl = _controls(key)
    if len(ctl):
        # The unit is the control well in numerator and denominator (review 7.5-02). A control counts as found
        # when a primary-search well row in its own cell names its permit in tied_record_id.
        searched = set(clean.loc[clean["outcome"] != "inaccessible", "site_id"])
        cs = ctl[ctl["site_id"].isin(searched)]
        found_pairs = set()
        if wells is not None and len(wells):
            wp = wells[(wells["status"] == "primary") & (wells["identity"] == "confirmed_well")]
            found_pairs = set(zip(wp["site_id"], wp["tied_record_id"].fillna("").astype(str)))
        n = int(len(cs))
        found = int(sum((s, c) in found_pairs for s, c in zip(cs["site_id"], cs["control_id"])))
        rec = {"unit": "control well", "n_controls_listed": int(len(ctl)), "n_controls": n,
               "n_controls_unsearched": int(len(ctl) - n), "found": found}
        if n:
            p, lo, hi = ek.clopper_pearson(found, n)
            rec.update(sensitivity=p, lo=lo, hi=hi)
        out["seeded_controls"] = rec
    return out


def arm_c_density(clean: pd.DataFrame, key: pd.DataFrame, wells: pd.DataFrame | None, cell_m: float, sens: dict) -> dict:
    """Undocumented confirmed wells per km2 searched, from the child well table (review F16).
    Every confirmed well of the primary search counts, several per cell, in cells with or without a control.
    A well is undocumented when no agency record is tied to it on site. Weighted ratio sum w n / sum w area."""
    c = clean.merge(key[["site_id", "pi"]], on="site_id").query("arm == 'C'")
    if not len(c):
        return {"note": "no Arm C cells"}
    searched = c[c["outcome"] != "inaccessible"]
    a_cell = cell_m ** 2 / 1e6
    n_new = pd.Series(0, index=searched["site_id"].to_numpy())
    if wells is not None and len(wells):
        wp = wells[(wells["status"] == "primary") & (wells["identity"] == "confirmed_well")
                   & wells["tied_record_id"].fillna("").astype(str).eq("")]
        n_new = wp.groupby("site_id").size().reindex(searched["site_id"].to_numpy(), fill_value=0)
    w = 1.0 / searched["pi"].to_numpy(float)
    area_w = float((w * a_cell).sum())
    new_w = float((w * n_new.to_numpy(float)).sum())
    res = {"cells_searched": int(len(searched)), "cells_inaccessible": int(len(c) - len(searched)),
           "cells_unresolved": int((searched["outcome"] == "unresolved").sum()),
           "cells_zero_new_wells": int((n_new == 0).sum()), "km2": float(len(searched) * a_cell),
           "undocumented_confirmed": int(n_new.sum()), "per_km2_observed": new_w / area_w if area_w else None,
           "method": "weighted ratio over searched cells. Inaccessible cells leave the searched area"}
    sc = sens.get("seeded_controls") or {}
    if sc.get("lo", 0) > 0 and res["per_km2_observed"] is not None:
        res["per_km2_bounds_by_sensitivity"] = [res["per_km2_observed"] / sc["hi"], res["per_km2_observed"] / sc["lo"]]
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


def analyse(cfg: dict, clean: pd.DataFrame, key: pd.DataFrame, rep: pd.DataFrame, out: Path,
            figs: Path | None = None, wells: pd.DataFrame | None = None) -> dict:
    df = clean.merge(key[["site_id", "stratum", "pi", "cluster_id", "era"]], on="site_id", how="left")
    ek.assert_rows(df, len(clean), "clean x key")
    ek.assert_no_nan(df["pi"], "pi")
    tgt = cfg["design"]["target_width"]
    rows = []
    for arm, g in df.groupby("arm"):
        rows.append(summarise(g, {"arm": arm, "stratum": "all (weighted)"}, tgt))
        for s, gs in g.groupby("stratum"):
            rows.append(summarise(gs, {"arm": arm, "stratum": s}, tgt))
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
    sens = sensitivity(rep, key, clean, wells)
    res["search_sensitivity"] = sens or {"note": "no repeat searches and no seeded controls. Recall is conditional only"}
    res["arm_C"] = arm_c_density(clean, key, wells, cfg["arm_C"]["cell_m"], sens)
    (out / "field_analysis_v1.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    figure(tab, (figs or out) / "field_bounds_v1.png")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.5 S6 analysis with identity bounds.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--tables", default=str(ek.sub("7.5", "results/tables")))
    a = ap.parse_args(argv)
    t = Path(a.tables)
    try:
        clean = pd.read_csv(need(t / "field_results_clean_v1.csv", "clean field results (run the ingest)"))
        key = pd.read_csv(need(t / "field_sample_key_v1.csv", "sample key"))
        rp = t / "field_repeat_searches_v1.csv"
        rep = pd.read_csv(rp) if rp.exists() else pd.DataFrame()
        wp = t / "field_wells_clean_v1.csv"
        wells = pd.read_csv(wp, dtype={"tied_record_id": str}) if wp.exists() else None
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    res = analyse(load_cfg(Path(a.config)), clean, key, rep, t, ek.sub("7.5", "results/figures"), wells)
    print(json.dumps(res["primary_result"], indent=2, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
