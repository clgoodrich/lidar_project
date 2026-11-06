"""S4. Sensitivity of the risk scenarios on 9t (fw_5_3 section 6 S4).

Purpose
    Show how much the top N moves when the rule moves.
    - Weight grid. The weighted-sum variant (rank-scaled P, H, E) with each weight swept 0 to 1 by 0.1 and the
      other two sharing the remainder equally. Jaccard of the top N and Kendall tau against equal weights.
    - Dirichlet draws. 2000 weight vectors from Dirichlet(1, 1, 1), seed from config (ek.child_seed). Per-site
      top-N membership frequency.
    - One-out. Remove each E component, each H component and the P band in turn. Top-N change per scenario.
    - Distance bands. Re-run with the water-well band at 25, 50 and 100 m (skipped and recorded when the
      water-well layer is absent).
    The figure shows top-N membership by weight value, single-hue sequential ramp from white to the validated
    blue (#1F5FA8), direct labels. No red and no green.
Inputs
    S1 and S2 outputs in @exp:5.3/results/tables/, receptor layers via config (for distance-band variants)
Outputs
    @exp:5.3/results/tables/risk_weight_sweep_9t.csv
    @exp:5.3/results/tables/risk_oneout_change_9t.csv
    @exp:5.3/results/figures/risk_weight_sweep_9t.png
    run folder @exp:5.3/results/runs/<YYYYMMDD>_risk_sensitivity_<hash>/
Run
    python expansions/5_tasks/5_3_risk_ranking/src/_risk_sensitivity_9t.py [--n-dirichlet 2000] [--no-figure]
"""
from __future__ import annotations

import argparse
import sys
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
BASE_W = (1 / 3, 1 / 3, 1 / 3)


def weight_sweep(df, n, step, n_dir, seed):
    ids = df["site_id"].to_numpy()
    base_r = rc.weighted_rank(df, BASE_W)
    base = rc.top_set(base_r, n, ids)
    rows, grid_member = [], {}
    for name, v, w in rc.weight_grid(step):
        r = rc.weighted_rank(df, w)
        t = rc.top_set(r, n, ids)
        grid_member[(name, v)] = t
        rows.append(dict(kind="grid", weight=name, value=v, wP=w[0], wH=w[1], wE=w[2],
                         jaccard_vs_equal=rc.jaccard(t, base), kendall_vs_equal=rc.kendall_tau(r, base_r)))
    rng = np.random.default_rng(seed)
    freq = pd.Series(0, index=ids, dtype=float)
    for i in range(n_dir):
        w = rng.dirichlet((1.0, 1.0, 1.0))
        r = rc.weighted_rank(df, w)
        t = rc.top_set(r, n, ids)
        freq[list(t)] += 1
        rows.append(dict(kind="dirichlet", weight="draw", value=i, wP=w[0], wH=w[1], wE=w[2],
                         jaccard_vs_equal=rc.jaccard(t, base), kendall_vs_equal=np.nan))
    return pd.DataFrame(rows), grid_member, (freq / max(n_dir, 1))


def one_out(sites, H, comps, n, agency=None):
    base = s3.rank_all(s3.assemble(sites, H, comps), agency)
    ids = base["site_id"].to_numpy()
    scen = [c[5:] for c in base.columns if c.startswith("rank_")]
    rows = []
    variants = [("E", c) for c in comps] + [("H", c) for c in H.columns if c.startswith("h_")] + [("P", "P")]
    for part, comp in variants:
        if part == "E":
            df = s3.assemble(sites, H, comps, drop_e=(comp,))
        elif part == "H":
            df = s3.assemble(sites, H, comps, drop_h=(comp,))
        else:
            df = s3.assemble(sites, H, comps)
            df["P"] = np.nan
        R = s3.rank_all(df, agency)
        for s in scen:
            a, b = rc.top_set(base[f"rank_{s}"], n, ids), rc.top_set(R[f"rank_{s}"], n, ids)
            rows.append(dict(removed_part=part, removed=comp, scenario=s, jaccard_vs_full=rc.jaccard(a, b),
                             n_swapped=len(a - b), kendall_vs_full=rc.kendall_tau(base[f"rank_{s}"], R[f"rank_{s}"])))
    return pd.DataFrame(rows)


def band_variants(cfg, sites, H, comps, n, recs):
    rows = []
    for name, bands in cfg.get("band_variants", {}).items():
        if name not in recs:
            rows.append(dict(removed_part="band", removed=f"{name} absent", scenario="all", jaccard_vs_full=np.nan,
                             n_swapped=np.nan, kendall_vs_full=np.nan))
            continue
        base = s3.rank_all(s3.assemble(sites, H, comps))
        ids = base["site_id"].to_numpy()
        ex = recs[name].exposure(sites[["x", "y"]].to_numpy(), bands)
        for b in bands:
            ss = sites.copy()
            ss[f"{name}_n_{b}"] = ex[f"{name}_n_{b}"]
            c2 = {(f"{name}_n_{b}" if k.startswith(name + "_") else k): v for k, v in comps.items()}
            R = s3.rank_all(s3.assemble(ss, H, c2))
            for s in [c[5:] for c in R.columns if c.startswith("rank_")]:
                a, bb = rc.top_set(base[f"rank_{s}"], n, ids), rc.top_set(R[f"rank_{s}"], n, ids)
                rows.append(dict(removed_part="band", removed=f"{name}_n_{b}", scenario=s,
                                 jaccard_vs_full=rc.jaccard(a, bb), n_swapped=len(a - bb),
                                 kendall_vs_full=rc.kendall_tau(base[f"rank_{s}"], R[f"rank_{s}"])))
    return pd.DataFrame(rows)


def figure(grid_member, ids_order, path, n):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    # Single-hue sequential ramp to the validated lost/found blue (ek.PALETTE, worst pair dE 21.1 deutan by the
    # dataviz validator --pairs all, CLAUDE.md). Membership is binary here, so only two ramp ends are shown.
    cmap = LinearSegmentedColormap.from_list("blue_seq", ["#FFFFFF", ek.PALETTE["blue"]])
    names = ("P", "H", "E")
    fig, axes = plt.subplots(1, 3, figsize=(12, 6), sharey=True)
    for ax, nm in zip(axes, names):
        vals = sorted(v for (k, v) in grid_member if k == nm)
        M = np.array([[sid in grid_member[(nm, v)] for v in vals] for sid in ids_order], float)
        ax.imshow(M, aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
        ax.set_xticks(range(len(vals)), [f"{v:.1f}" for v in vals], fontsize=7)
        ax.set_xlabel(f"weight on {nm} (others share the rest)")
        ax.set_title(f"top {n} membership as w_{nm} moves", fontsize=10)
    axes[0].set_ylabel("sites ever in the top N (filled = in the top N)")
    fig.suptitle("Weighted-sum scenario sensitivity, tile 9t. Candidate rows are " + th.CONDITIONAL, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    ap.add_argument("--n-dirichlet", type=int, default=None)
    ap.add_argument("--no-figure", action="store_true")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    sites, s1, H = s3.load_stage_inputs(cfg)
    comps = s1["e_components_used"]
    run = rio.start_run(cfg, "risk_sensitivity", "S4 sensitivity.", ["sweep_grid_step", "n_dirichlet", "master_seed"])
    df = s3.assemble(sites, H, comps)
    n = rc.top_n_size(len(df), cfg["top_n_max"], cfg["top_n_share"])
    n_dir = a.n_dirichlet if a.n_dirichlet is not None else cfg["n_dirichlet"]
    seed = ek.child_seed(cfg["master_seed"], 0, 4)
    sw, grid_member, freq = weight_sweep(df, n, cfg["sweep_grid_step"], n_dir, seed)
    sw_out = th.outp(cfg, "sweep_csv")
    sw.to_csv(sw_out, index=False)
    recs, missing = rio.receptors(cfg, names=tuple(cfg.get("band_variants", {})))
    oo = pd.concat([one_out(sites, H, comps, n), band_variants(cfg, sites, H, comps, n, recs)], ignore_index=True)
    oo_out = th.outp(cfg, "oneout_csv")
    oo.to_csv(oo_out, index=False)
    outs = [sw_out, oo_out]
    freq.rename("dirichlet_topn_freq").to_csv(sw_out.with_name(sw_out.stem + "_site_freq.csv"), index_label="site_id")
    outs.append(sw_out.with_name(sw_out.stem + "_site_freq.csv"))
    if not a.no_figure:
        ever = sorted(set().union(*grid_member.values()), key=lambda s: -freq.get(s, 0))
        png = th.outp(cfg, "sweep_png")
        figure(grid_member, ever, png, n)
        outs.append(png)
    g = sw[sw.kind == "grid"]
    ek.write_provenance(run, outputs=outs, params=dict(top_n=n, n_dirichlet=n_dir, seed=seed,
                                                       band_variant_missing=missing),
                        seeds={"dirichlet": seed})
    print(f"top N {n}. grid Jaccard vs equal min {g.jaccard_vs_equal.min():.3f} median {g.jaccard_vs_equal.median():.3f}")
    print(f"Dirichlet Jaccard 5th pct {sw[sw.kind == 'dirichlet'].jaccard_vs_equal.quantile(0.05):.3f}")
    for p in outs:
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
