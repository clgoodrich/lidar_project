"""5.4 S2. Sensitivity grid of implied totals over precision p, recall r and wells per site m. Not an estimate.

Purpose
    T = D p m / r, missed = D p m (1 - r) / r, undocumented = T - N_doc, for every cell of the grid. A cell where T is
    below N_doc is flagged inconsistent (the detector population could not hold the documented wells). The figure is
    a single-hue sequential heat map of undocumented wells at m = 1, labelled sensitivity. As r goes to 0 the total
    has no finite upper bound, which the JSON states in words.

Inputs
    accounting   expansions/5_tasks/5_4_undocumented_density/results/tables/density_accounting_9t.json (S1)
Outputs
    expansions/5_tasks/5_4_undocumented_density/results/tables/density_sensitivity_9t.csv
    expansions/5_tasks/5_4_undocumented_density/results/figures/density_sensitivity_9t.png
Run
    python expansions/5_tasks/5_4_undocumented_density/src/_density_sensitivity_grid_9t.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

ek = th.ek


def grid(D: float, n_doc: int, g: dict) -> pd.DataFrame:
    ps = np.round(np.arange(g["p_min"], g["p_max"] + 1e-9, g["step"]), 4)
    rs = np.round(np.arange(g["r_min"], g["r_max"] + 1e-9, g["step"]), 4)
    rows = []
    for m in g["m_values"]:
        for p in ps:
            for r in rs:
                t = D * p * m / r
                rows.append(dict(m=m, p=p, r=r, total=t, missed=D * p * m * (1 - r) / r, undocumented=t - n_doc,
                                 inconsistent=int(t < n_doc)))
    G = pd.DataFrame(rows)
    G["label"] = "sensitivity, not an estimate"
    return G


def figure(G: pd.DataFrame, path: Path, D: int, n_doc: int):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    # Single-hue sequential ramp to ek.PALETTE blue #1F5FA8 (ordered data, so no categorical pair to validate).
    # Inconsistent cells are hatched grey #8E959B as a second encoding.
    cmap = LinearSegmentedColormap.from_list("blue_seq", ["#F2F6FB", ek.PALETTE["blue"]])
    s = G[G.m == 1.0].pivot(index="r", columns="p", values="undocumented")
    inc = G[G.m == 1.0].pivot(index="r", columns="p", values="inconsistent")
    fig, ax = plt.subplots(figsize=(8, 6))
    v = np.where(inc.values == 1, np.nan, s.values)
    hp = (s.columns[1] - s.columns[0]) / 2 if len(s.columns) > 1 else 0.025
    hr = (s.index[1] - s.index[0]) / 2 if len(s.index) > 1 else 0.025
    im = ax.imshow(v, origin="lower", aspect="auto", cmap=cmap,   # extent on cell edges so hatches align
                   extent=[s.columns.min() - hp, s.columns.max() + hp, s.index.min() - hr, s.index.max() + hr])
    ax.contourf(s.columns, s.index, inc.values, levels=[0.5, 1.5], colors="none", hatches=["//"])
    ax.set_xlabel("p, share of candidate sites that are wells")
    ax.set_ylabel("r, share of eligible wells that yield a candidate")
    fig.colorbar(im, ax=ax, label="implied undocumented wells (m = 1)")
    ax.set_title(f"Sensitivity, not an estimate. D = {D} sites, N_doc = {n_doc}. Hatched = total below N_doc",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    acc = json.loads(th.inp(cfg, "accounting").read_text())
    D, n_doc = int(acc["D_sites"]), int(acc["N_doc_wells"])
    G = grid(D, n_doc, cfg["grid"])
    out = th.outp(cfg, "grid")
    G.to_csv(out, index=False)
    fig = th.outp(cfg, "grid_fig")
    figure(G, fig, D, n_doc)
    meta = dict(D_sites=D, N_doc_wells=n_doc, cells=len(G), inconsistent_cells=int(G.inconsistent.sum()),
                unbounded="As r approaches 0 the implied total grows without limit. No finite upper bound exists without a lower bound on r.",
                label="sensitivity, not an estimate")
    th.write_json(out.with_suffix(".json"), meta)
    print(meta, "\nwrote", out, "\nwrote", fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
