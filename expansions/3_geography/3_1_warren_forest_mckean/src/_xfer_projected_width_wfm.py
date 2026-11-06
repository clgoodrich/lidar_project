"""3.1 S2. Projected interval width for the transfer difference, over target density and clustering.

Purpose
    Readiness gate. Before any annotation, forecast the 95% interval width of
    recall(target) - recall(9t) at K = 40 per km2. The forecast does not resample 9t only
    (third review). For each grid cell (target feature density, cluster size, number of test
    blocks) it simulates target blocks under the null of equal recall.
        clusters per block ~ Poisson(density x block km2 / cluster size)
        block recall r_b   ~ Beta with mean r0 and the between-block dispersion measured on
                             the 9t reference blocks (method of moments)
        each cluster is found or missed as one unit (pits on one pad move together)
    The reference side is the 9t out-of-fold block table, so its own uncertainty enters the
    width. The interval is ek.bootstrap_diff with independent block resampling. The median
    width over reps is compared with 2 x margin. If no margin is set the gate is not decided.
    The planned number of test blocks is read from the S1 roles file when it exists.

Inputs
    reference   config reference.blocks_csv (provisional: 3.3 S1 slope_recall_blocks_9t.csv)
    S1 roles    results/tables/<area>/xfer_blocks_roles_<area>.gpkg (optional, sets n_test)

Outputs
    expansions/3_geography/3_1_warren_forest_mckean/results/tables/<area>/xfer_projected_width_<area>.csv
    .../results/tables/<area>/xfer_projected_width_<area>.json (r0, dispersion, margin, gate per cell)

Run
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_projected_width_wfm.py --area warren
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_projected_width_wfm.py --area mckean --reps 20 --B 100
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_1.json"


def dispersion(ref: pd.DataFrame):
    """Pooled recall r0 and beta precision phi of block recall (method of moments, n-weighted)."""
    d = ref[ref.n_truth > 0]
    n, h = d.n_truth.to_numpy(float), d.hits.to_numpy(float)
    r0 = h.sum() / n.sum()
    p = h / n
    var_obs = np.average((p - r0) ** 2, weights=n)
    binom = r0 * (1 - r0) * np.mean(1 / n)
    rho = max(0.0, (var_obs - binom) / max(r0 * (1 - r0) * (1 - np.mean(1 / n)), 1e-12))
    phi = 1e4 if rho <= 1e-4 else 1 / rho - 1
    return float(r0), float(phi), float(rho)


def simulate_target(rng, n_blocks, density, cluster, r0, phi, block_km2):
    lam = density * block_km2 / cluster
    rows = []
    for _ in range(n_blocks):
        nc = rng.poisson(lam)
        rb = rng.beta(max(r0 * phi, 1e-3), max((1 - r0) * phi, 1e-3))
        found = rng.binomial(nc, rb)
        rows.append((found * cluster, nc * cluster))
    return rows


def projected_grid(ref_rows, r0, phi, grid, reps, B, seed, block_km2, margin):
    out = []
    for n_blocks in grid["n_blocks"]:
        for dens in grid["densities_per_km2"]:
            for c in grid["cluster_sizes"]:
                rng = np.random.default_rng(ek.child_seed(seed, int(n_blocks), int(dens * 10 + c)))
                widths = []
                for r in range(reps):
                    tgt = simulate_target(rng, n_blocks, dens, c, r0, phi, block_km2)
                    if sum(t[1] for t in tgt) == 0:
                        continue
                    _, lo, hi = ek.bootstrap_diff(xl.pooled_recall, tgt, xl.pooled_recall, ref_rows, B=B,
                                                  seed=int(rng.integers(1 << 31)))
                    widths.append(hi - lo)
                w = float(np.median(widths)) if widths else np.nan
                out.append({"n_test_blocks": n_blocks, "density_per_km2": dens, "cluster_size": c,
                            "median_width": w, "reps_used": len(widths),
                            "gate_width_le_2margin": (bool(w <= 2 * margin) if margin is not None and np.isfinite(w) else None)})
    return pd.DataFrame(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--area", required=True)
    ap.add_argument("--reps", type=int, default=None)
    ap.add_argument("--B", type=int, default=None)
    ap.add_argument("--margin", type=float, default=None, help="override config margin_delta[area]")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.area)
    G = dict(cfg["projected_width"])
    reps, B = a.reps or G["reps"], a.B or G["B"]
    ref_p = xl.need(xl.resolve_path(cfg["reference"]["blocks_csv"]), "9t reference block table",
                    "run 3.3 _slope_recall_tercile_9t.py, or point reference.blocks_csv at the P1 isolated table")
    ref = pd.read_csv(ref_p)
    ref_rows = list(zip(ref.hits, ref.n_truth))
    r0, phi, rho = dispersion(ref)
    margin = a.margin if a.margin is not None else (cfg.get("margin_delta") or {}).get(a.area)
    roles = ctx["tables"] / f"xfer_blocks_roles_{a.area}.gpkg"
    n_plan = None
    if roles.exists():
        import geopandas as gpd
        n_plan = int((gpd.read_file(roles, layer="blocks").role == "test").sum())
        G["n_blocks"] = sorted(set(G["n_blocks"]) | {n_plan})
    block_km2 = cfg.get("block_m", 375.0) ** 2 / 1e6
    tab = projected_grid(ref_rows, r0, phi, G, reps, B, cfg["master_seed"], block_km2, margin)
    out = ctx["tables"] / f"xfer_projected_width_{a.area}.csv"
    tab.to_csv(out, index=False)
    ref_density = float(ref.n_truth.sum() / ref.area_km2.sum()) if "area_km2" in ref else None
    meta = {"area": a.area, "reference": str(ref_p), "reference_provisional": "slope_recall" in str(ref_p),
            "r0": r0, "phi": phi, "icc_rho": rho, "reference_blocks": len(ref_rows),
            "reference_density_per_km2": ref_density, "margin": margin, "planned_test_blocks": n_plan,
            "reps": reps, "B": B, "seed": cfg["master_seed"],
            "gate": "not decided (no margin)" if margin is None else "see gate_width_le_2margin per row"}
    js = ctx["tables"] / f"xfer_projected_width_{a.area}.json"
    js.write_text(json.dumps(meta, indent=2, default=float), encoding="utf-8")
    print(tab.to_string(index=False))
    print(json.dumps(meta, indent=2, default=float))
    print(f"wrote {out}\n      {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
