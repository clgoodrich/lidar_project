"""5.5 S6 and S7. Propagate area error to cost by Monte Carlo, then the restoration-budget decision analysis.

Purpose
    Cost model C = F + c_a A + c_r L_road (fw_5_5 section 3). Only c_a A depends on the polygon.
    Step 1, no cost table needed. Break-even area share f* per tolerance. Area error alone moves cost by
        f (exp(r) - 1), so for 90% of pads to stay within tol, f must be at most tol / P90 |exp(r) - 1|.
    Step 2, needs the agency cost table (assumed). c_a, F and c_r are lognormal with the table's low and high as the
        5th and 95th percentiles. 10,000 draws per pad. r is drawn from the empirical distribution by block
        resampling (a block, then a pad in it), so pad-level r is not treated as independent noise. Per pad the
        relative cost error C_hat / C_ref - 1. Portfolios of N pads show that unbiased errors partly cancel and a
        bias does not.
    Step 3 (S7). For each tolerance (15, 25, 40%) the share of pads whose observed C_hat (own r, median costs) is
        within tolerance, with a Clopper-Pearson interval and a block-bootstrap interval.
    If the table has no separable area term, cost claims stop at area and the script says so.
    Units (review 5.5-02). Every cost row needs a unit. Area costs are converted to USD per m2 and road costs to
    USD per m (acre, ha, ft, km, mile are converted). Any other unit refuses. L_road is road_length_m from S4. If the
    table has a road item and road length is missing the script refuses rather than use 0.

Inputs (config_5_5.json)
    agreement     results/tables/pad_area_agreement_9t.csv (S4, survey) or ..._drawn_9t.csv with --reference drawn
    cost_table    assumed, @reference/cost/restoration_cost_table.csv
Outputs
    expansions/5_tasks/5_5_polygon_area_cost/results/tables/pad_cost_error_9t.csv
    expansions/5_tasks/5_5_polygon_area_cost/results/tables/pad_cost_error_summary_9t.json
    expansions/5_tasks/5_5_polygon_area_cost/results/figures/pad_cost_error_9t.png
    (drawn reference adds _drawn before _9t)
Run
    python expansions/5_tasks/5_5_polygon_area_cost/src/_padarea_cost_mc_9t.py --reference drawn
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
Z95 = 1.6449


def suffix(p: Path, mode: str) -> Path:
    return p.with_name(p.stem.replace("_9t", "_drawn_9t") + p.suffix) if mode == "drawn" else p


def break_even(r: np.ndarray, tols) -> dict:
    q = float(np.percentile(np.abs(np.exp(r) - 1), 90))
    return {f"{t:.2f}": (t / q if q > 0 else float("inf")) for t in tols} | {"p90_abs_area_error": q}


def lognormal(lo: float, hi: float):
    lo, hi = max(lo, 1e-9), max(hi, lo * 1.000001)
    mu = (np.log(lo) + np.log(hi)) / 2
    return mu, (np.log(hi) - np.log(lo)) / (2 * Z95)


# Unit check (review 5.5-02). Each item has one base unit. Known alternatives are converted, anything else refuses.
# factor = multiply a cost in the stated unit by this to get the cost in the base unit.
M2_PER_ACRE = 4046.8564224
UNIT_FACTOR = {
    "fixed_per_well": {"usd per well": 1.0},
    "area_restoration": {"usd per m2": 1.0, "usd per ha": 1 / 1e4, "usd per acre": 1 / M2_PER_ACRE},
    "road_restoration": {"usd per m": 1.0, "usd per km": 1 / 1e3, "usd per ft": 1 / 0.3048,
                         "usd per mile": 1 / 1609.344},
}


def _norm_unit(u) -> str:
    u = str(u).strip().lower().replace("/", " per ").replace("²", "2").replace("$", "usd")
    u = u.replace("m^2", "m2").replace("sq m", "m2").replace("hectare", "ha").replace("acres", "acre")
    u = u.replace("feet", "ft").replace("foot", "ft").replace("metre", "m").replace("meter", "m")
    return " ".join(u.split())


def unit_factor(item: str, unit) -> float:
    if item not in UNIT_FACTOR:
        raise SystemExit(f"COST TABLE unknown item {item!r}")
    nu = _norm_unit(unit)
    if nu not in UNIT_FACTOR[item]:
        raise SystemExit(f"COST TABLE unit {unit!r} for {item} is not one of {sorted(UNIT_FACTOR[item])}. "
                         "Fix the table or add a declared conversion.")
    return UNIT_FACTOR[item][nu]


def parse_costs(C: pd.DataFrame, cls: str) -> dict:
    """Lognormal (mu, sd) per item in base units (USD per well, per m2, per m). Refuses a missing or unknown unit."""
    th.require_columns(C, ["item", "unit", "low", "high"], "cost table")
    items = set(C["item"])
    if "area_restoration" not in items:
        raise SystemExit("COST TABLE has no separable area term (item area_restoration). Cost claims stop at area.")
    out = {}
    for it in ("fixed_per_well", "area_restoration", "road_restoration"):
        rows = C[C["item"] == it]
        if it == "fixed_per_well" and "condition_class" in C and (rows.condition_class == cls).any():
            rows = rows[rows.condition_class == cls]
        if not len(rows):
            out[it] = (None, None)
            continue
        f = unit_factor(it, rows.unit.iloc[0])
        out[it] = lognormal(float(rows.low.iloc[0]) * f, float(rows.high.iloc[0]) * f)
    return out


def simulate(T: pd.DataFrame, costs: dict, draws: int, portfolio_n, seed: int):
    rng = np.random.default_rng(seed)
    m = T.dropna(subset=["log_ratio"]).reset_index(drop=True)
    blocks = m.block_id.to_numpy()
    ub = np.unique(blocks)
    idx_by = {b: np.flatnonzero(blocks == b) for b in ub}

    def draw_r(n):
        bsel = ub[rng.integers(0, len(ub), n)]
        return np.array([m.log_ratio.iloc[idx_by[b][rng.integers(0, len(idx_by[b]))]] for b in bsel])

    def draw_c(key, n):
        mu, sd = costs[key]
        return np.zeros(n) if mu is None else np.exp(rng.normal(mu, sd, n))
    A = m.A_ref.to_numpy()
    if costs["road_restoration"][0] is None:
        L = np.zeros(len(m))                      # no road item in the table, so the road term is absent, not zero-length
    else:
        if "road_length_m" not in m or not np.isfinite(m["road_length_m"].to_numpy(float)).all():
            raise SystemExit("ROAD LENGTH missing: the cost table has road_restoration but the agreement table has "
                             "no finite road_length_m. Rerun _padarea_agreement_9t.py with a roads layer.")
        L = m["road_length_m"].to_numpy(float)
    rs = draw_r(draws)
    F, ca, cr = draw_c("fixed_per_well", draws), draw_c("area_restoration", draws), draw_c("road_restoration", draws)
    med = {k: (np.exp(v[0]) if v[0] is not None else 0.0) for k, v in costs.items()}
    rows = []
    for i in range(len(m)):
        cref = F + ca * A[i] + cr * L[i]
        chat = F + ca * A[i] * np.exp(rs) + cr * L[i]
        rel = chat / cref - 1
        cref0 = med["fixed_per_well"] + med["area_restoration"] * A[i] + med["road_restoration"] * L[i]
        obs = (med["area_restoration"] * A[i] * (np.exp(m.log_ratio.iloc[i]) - 1)) / cref0
        rows.append(dict(pad_id=m.pad_id.iloc[i], block_id=blocks[i], A_ref=A[i], log_ratio=m.log_ratio.iloc[i],
                         f_area_share=med["area_restoration"] * A[i] / cref0, rel_err_observed=obs,
                         rel_err_p05=np.percentile(rel, 5), rel_err_p50=np.percentile(rel, 50),
                         rel_err_p95=np.percentile(rel, 95)))
    P = pd.DataFrame(rows)
    port = {}
    for n in portfolio_n:
        tot = []
        for _ in range(min(draws, 2000)):
            k = rng.integers(0, len(m), n)
            rr = draw_r(n)
            f_, a_, c_ = draw_c("fixed_per_well", 1)[0], draw_c("area_restoration", 1)[0], draw_c("road_restoration", 1)[0]
            ref = (f_ + a_ * A[k] + c_ * L[k]).sum()
            tot.append((f_ + a_ * A[k] * np.exp(rr) + c_ * L[k]).sum() / ref - 1)
        port[str(n)] = dict(p05=float(np.percentile(tot, 5)), p50=float(np.median(tot)), p95=float(np.percentile(tot, 95)))
    return P, port


def tolerance_table(P: pd.DataFrame, tols, B: int, seed: int) -> list:
    out = []
    blocks = sorted(P.block_id.unique())
    for t in tols:
        ok = (P.rel_err_observed.abs() <= t)
        k, n = int(ok.sum()), int(len(P))
        _, lo, hi = ek.clopper_pearson(k, n)
        by = {b: ok[P.block_id == b].to_numpy() for b in blocks}
        pt, blo, bhi, _ = ek.block_bootstrap(lambda bl: float(np.concatenate([by[b] for b in bl]).mean()), blocks,
                                            B=B, seed=seed)
        out.append(dict(tolerance=t, share_within=k / n, cp_lo=lo, cp_hi=hi, block_lo=blo, block_hi=bhi, n_pads=n))
    return out


def figure(P: pd.DataFrame, tols, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # ek.PALETTE blue #1F5FA8 bars, grey #8E959B and orange #D97706 tolerance lines (lost/found palette, worst pair
    # dE 21.1 deutan, dataviz validator --pairs all). Lines also differ by style and carry direct labels.
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(P.rel_err_observed * 100, bins=40, color=ek.PALETTE["blue"])
    for t, col, ls in zip(tols, [ek.PALETTE["grey"], ek.PALETTE["orange"], ek.PALETTE["charcoal"]], ["--", "-", ":"]):
        for s in (-1, 1):
            ax.axvline(s * t * 100, color=col, ls=ls)
        ax.text(t * 100, ax.get_ylim()[1] * 0.9, f" ±{int(t * 100)}%", color=col, fontsize=8)
    ax.set_xlabel("relative pad cost error from area alone (%)")
    ax.set_ylabel("pads")
    ax.set_title("Area error propagated to cost, per pad (evidence level a)", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("--reference", choices=("survey", "drawn"))
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    mode = a.reference or cfg["reference"]
    src = suffix(th.resolve(cfg["outputs"]["agreement"]), mode)
    if not src.exists():
        raise th.MissingInput("agreement", src, f"Run _padarea_agreement_9t.py --reference {mode} first.")
    T = pd.read_csv(src)
    m = T.dropna(subset=["log_ratio"])
    dec, mc = cfg["decision"], cfg["monte_carlo"]
    summary = dict(reference=mode, break_even_f=break_even(m.log_ratio.to_numpy(), dec["tolerances"]),
                   closed_form_example="f = 0.3 and r = ln 2 move cost by 0.3 x (2 - 1) = 30%",
                   note="Area is level (a). Cost covers the surface term only. Nothing here speaks to wells.")
    js = suffix(th.outp(cfg, "cost_summary"), mode)
    if not th.has(cfg, "cost_table"):
        summary["cost_table"] = "missing"
        th.write_json(js, summary)
        print("break-even f:", summary["break_even_f"], "\nwrote", js)
        th.inp(cfg, "cost_table")                 # raises MissingInput naming the table
    costs = parse_costs(pd.read_csv(th.inp(cfg, "cost_table")), mc["default_condition_class"])
    P, port = simulate(m, costs, mc["draws"], mc["portfolio_n"], int(cfg["seed"]))
    P = th.tag(P, "a", "exploratory" if mode == "drawn" else "confirmatory_survey")
    summary.update(cost_table=gt.rel(th.inp(cfg, "cost_table")), portfolio=port,
                   cost_units=dict(fixed_per_well="USD per well", area_restoration="USD per m2",
                                   road_restoration="USD per m"),
                   median_road_length_m=float(m["road_length_m"].median()) if "road_length_m" in m else None,
                   tolerance=tolerance_table(P, dec["tolerances"], cfg["bootstrap_B"], int(cfg["seed"]) + 3),
                   median_f=float(P.f_area_share.median()))
    out = suffix(th.outp(cfg, "cost_error"), mode)
    P.to_csv(out, index=False)
    th.write_json(js, summary)
    fig = suffix(th.outp(cfg, "cost_fig"), mode)
    figure(P, dec["tolerances"], fig)
    print(summary["tolerance"], "\nwrote", out, "\nwrote", js, "\nwrote", fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
