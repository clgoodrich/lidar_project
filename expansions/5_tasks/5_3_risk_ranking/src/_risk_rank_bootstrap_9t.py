"""S5. Rank-stability bootstrap for risk ranking on 9t (fw_5_3 section 6 S5).

Purpose
    Perturb the inputs within their stated uncertainty and see which sites stay in the top N.
    Per draw (B from config, default 2000, each draw seeded by ek.child_seed(master, draw, 5))
    - Candidate scores. Resample 375 m blocks with replacement. Recompute the K-rank tercile cut points from
      the resampled scores. Re-band every candidate site with those cut points.
    - Positions. Jitter record positions by the stated record error (isotropic normal, RMS radial error =
      record_pos_error_m) and candidate positions by candidate_jitter_m. Recompute exposure from the receptors.
    - Missing H attributes. Impute by a draw from the observed values of that column, never by the mean.
    - Rank every scenario. Save Jaccard and Kendall tau against the base ranking.
    Per site. Top-N membership frequency, rank interval (2.5 and 97.5 percentiles) and 'stable in' when the
    site is in the top N in at least 90% of draws. Stability is not validity.
    The pathway flag is kept at its base value (stream geometry is not perturbed).
Inputs
    S1 and S2 outputs in @exp:5.3/results/tables/ (risk_exposure_sites_9t.csv, risk_candidate_scores_9t.csv,
    risk_exposure_summary_9t.json, risk_hazard_proxy_9t.csv), receptor layers via config
Outputs
    @exp:5.3/results/tables/risk_rank_stability_9t.csv     one row per draw and scenario
    @exp:5.3/results/tables/risk_site_rank_interval_9t.csv one row per site and scenario
    @exp:5.3/results/figures/risk_rank_stability_9t.png    rank intervals of the primary scenario's top N
    run folder @exp:5.3/results/runs/<YYYYMMDD>_risk_bootstrap_<hash>/
Run
    python expansions/5_tasks/5_3_risk_ranking/src/_risk_rank_bootstrap_9t.py [--n-boot 2000] [--no-figure]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _risk_io_9t as rio  # noqa: E402
import _risk_ranking_core as rc  # noqa: E402
import _risk_scenarios_9t as s3  # noqa: E402

ek = th.ek


def one_draw(rng, sites, H, comps, cand, k, recs, cfg):
    """One perturbed ranking. Returns ranked DataFrame."""
    s = sites.copy()
    # candidate band cut points from block-resampled scores
    blocks = cand["block_id"].unique()
    pick = rng.choice(blocks, len(blocks), replace=True)
    sc = np.concatenate([cand.loc[cand.block_id == b, "score"].to_numpy() for b in pick]) if len(pick) else np.array([])
    _, cuts = rc.p_bands(sc, k)
    is_c = (s["p_source"] == "feature_band").to_numpy()
    b, _ = rc.p_bands(s.loc[is_c, "cand_score"].to_numpy(float), k, cuts)
    s.loc[is_c, "p_band"] = b
    s["P"] = s["p_band"].map(rc.P_BAND_VALUE).astype(float)
    # position jitter, RMS radial error = stated error
    sd = np.where(is_c, cfg["candidate_jitter_m"], cfg["record_pos_error_m"]) / np.sqrt(2)
    xy = s[["x", "y"]].to_numpy() + rng.normal(size=(len(s), 2)) * sd[:, None]
    if recs:
        ex = rc.exposure_table(xy, recs, cfg["distance_bands_m"])
        for c in ex.columns:
            s[c] = ex[c].to_numpy()
    # impute missing H by draw from observed values
    # Imputation stays inside one p_source group. A candidate has no plugging record by construction, so that
    # column is structurally absent for candidates and is not imputed from records.
    Hd = H.copy()
    grp = s["p_source"].to_numpy()
    for c in [c for c in Hd.columns if c.startswith("h_") and pd.api.types.is_numeric_dtype(Hd[c])]:
        for g in np.unique(grp):
            ing = grp == g
            m = ing & Hd[c].isna().to_numpy()
            obs = Hd.loc[ing & ~Hd[c].isna().to_numpy(), c].to_numpy()
            if m.any() and len(obs):
                Hd.loc[m, c] = rng.choice(obs, m.sum(), replace=True)
    return s3.rank_all(s3.assemble(s, Hd, comps, cfg=cfg))


def run_boot(sites, H, comps, cand, k, recs, cfg, B, master):
    base = s3.rank_all(s3.assemble(sites, H, comps, cfg=cfg))
    scen = [c[5:] for c in base.columns if c.startswith("rank_")]
    ids = base["site_id"].to_numpy()
    n = rc.top_n_size(len(base), cfg["top_n_max"], cfg["top_n_share"])
    base_top = {s: rc.top_set(base[f"rank_{s}"], n, ids) for s in scen}
    R = {s: np.full((B, len(base)), np.nan) for s in scen}
    rows = []
    t0 = time.time()
    for i in range(B):
        rng = np.random.default_rng(ek.child_seed(master, i, 5))
        d = one_draw(rng, sites, H, comps, cand, k, recs, cfg)
        for s in scen:
            r = d[f"rank_{s}"].to_numpy()
            R[s][i] = r
            rows.append(dict(draw=i, scenario=s, jaccard_vs_base=rc.jaccard(rc.top_set(r, n, ids), base_top[s]),
                             kendall_vs_base=rc.kendall_tau(r, base[f"rank_{s}"])))
        if i == 0:
            print(f"  one draw {time.time() - t0:.2f} s, projected {B * (time.time() - t0):.0f} s")
    st = pd.DataFrame(rows)
    site_rows = []
    for s in scen:
        M = R[s]
        freq = (np.nan_to_num(M, nan=np.inf) <= n).mean(0)
        unr = np.isnan(M).mean(0)
        # an interval is reported only for a site rankable in every draw (no draws dropped, review SH-01)
        lo, hi = np.percentile(np.where(np.isnan(M), np.inf, M), [2.5, 97.5], axis=0)
        lo = np.where(unr > 0, np.nan, lo)
        hi = np.where(unr > 0, np.nan, hi)
        site_rows.append(pd.DataFrame(dict(site_id=ids, scenario=s, base_rank=base[f"rank_{s}"].to_numpy(),
                                           rank_lo=lo, rank_hi=hi, topn_freq=freq, unrankable_share=unr,
                                           stable_in=freq >= cfg["stable_in_share"],
                                           p_source=base["p_source"], P=base["P"], H=base["H"], E=base["E"],
                                           conditional=base["conditional"])))
    return st, pd.concat(site_rows, ignore_index=True), n


def figure(si, scen, n, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # Blue #1F5FA8 and grey #8E959B from ek.PALETTE (validated, dataviz validator --pairs all, worst pair
    # dE 21.1 deutan per CLAUDE.md). Second encoding is marker shape.
    d = si[(si.scenario == scen) & (si.base_rank <= n)].sort_values("base_rank")
    fig, ax = plt.subplots(figsize=(8, max(4, 0.12 * len(d))))
    y = np.arange(len(d))
    for stable, col, mk, lab in ((True, ek.PALETTE["blue"], "o", "stable in (>= 90% of draws)"),
                                 (False, ek.PALETTE["grey"], "s", "not stable")):
        m = d.stable_in.to_numpy() == stable
        ax.hlines(y[m], d.rank_lo[m], d.rank_hi[m], color=col, lw=1.5)
        ax.plot(d.base_rank[m], y[m], mk, color=col, ms=4, label=lab)
    ax.axvline(n, color=ek.PALETTE["charcoal"], ls="--", lw=0.8)
    ax.text(n, len(d), f" N = {n}", fontsize=8, va="bottom")
    ax.set_yticks(y, d.site_id, fontsize=5)
    ax.invert_yaxis()
    ax.set_xlabel("rank (base point, 95% bootstrap interval)")
    ax.set_title(f"Scenario {scen} rank stability, tile 9t. Candidates are {th.CONDITIONAL}", fontsize=9)
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    rio.save_fig(fig, path)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    ap.add_argument("--n-boot", type=int, default=None)
    ap.add_argument("--no-figure", action="store_true")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    sites, s1, H = s3.load_stage_inputs(cfg)
    cp = th.resolve(cfg["outputs"]["cand_scores_csv"])
    if not cp.exists():
        raise th.MissingInput("cand_scores_csv (S1 output)", cp, "Run _risk_exposure_layers_9t.py first.")
    cand = pd.read_csv(cp)
    B = a.n_boot if a.n_boot is not None else cfg["n_boot"]
    run = rio.start_run(cfg, "risk_bootstrap", "S5 rank-stability bootstrap.",
                        ["n_boot", "record_pos_error_m", "candidate_jitter_m", "master_seed"])
    recs, missing = rio.receptors(cfg)
    st, si, n = run_boot(sites, H, s1["e_components_used"], cand, s1["k"], recs, cfg, B, cfg["master_seed"])
    o1, o2 = th.outp(cfg, "stability_csv"), th.outp(cfg, "site_interval_csv")
    st.to_csv(o1, index=False)
    si.to_csv(o2, index=False)
    outs = [o1, o2]
    if not a.no_figure:
        png = th.outp(cfg, "stability_png")
        figure(si, cfg["primary_scenario"], n, png)
        outs.append(png)
    summ = st.groupby("scenario").jaccard_vs_base.agg(median="median", p05=lambda v: v.quantile(0.05)).round(4)
    summ["n_stable_in"] = si.groupby("scenario").stable_in.sum()
    ek.write_provenance(run, inputs=[cp], outputs=outs,
                        params=dict(B=B, top_n=n, missing_receptors=missing, summary=summ.to_dict()),
                        seeds={"master": cfg["master_seed"], "rule": "child_seed(master, draw, 5)"})
    print(summ.to_string())
    for p in outs:
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
