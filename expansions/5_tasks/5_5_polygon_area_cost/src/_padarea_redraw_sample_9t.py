"""5.5 S2. Reviewer redraws. Draw the 30-pad sample, then score inter-reviewer agreement from the redraws.

Purpose
    --draw   stratified random sample of drawn pads (size terciles, equal allocation, one pad per block where
             possible so blocks spread). The sheet holds pad_id, block_id and an extent only. No model polygon and no
             annotator outline, so reviewers redraw blind to both.
    --score  reads two reviewer layers (reviewer_a, reviewer_b) and reports per pad IoU, log area ratio a over b,
             mean symmetric boundary distance and Hausdorff 95. This is a reproducibility reference, not a ceiling.

Inputs (config_5_5.json)
    by_pad   results/tables/pad_area_by_pad_9t.csv (S1)
    redraws  assumed, expansions/5_tasks/5_5_polygon_area_cost/data/raw/pad_redraw_reviewers_9t.gpkg
Outputs
    expansions/5_tasks/5_5_polygon_area_cost/data/interim/pad_redraw_sample_sheet_9t.csv   (--draw)
    expansions/5_tasks/5_5_polygon_area_cost/results/tables/pad_redraw_agreement_9t.csv    (--score)
Run
    python expansions/5_tasks/5_5_polygon_area_cost/src/_padarea_redraw_sample_9t.py --draw
    python expansions/5_tasks/5_5_polygon_area_cost/src/_padarea_redraw_sample_9t.py --score
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


def draw(T: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    T = T[T.block_id >= 0]
    terc = sorted(T.size_tercile.unique())
    per = int(np.ceil(n / len(terc)))
    parts = []
    for t in terc:
        g = T[T.size_tercile == t].sample(frac=1, random_state=int(rng.integers(1 << 31)))
        first = g.drop_duplicates("block_id")              # spread over blocks first
        rest = g[~g.index.isin(first.index)]
        parts.append(pd.concat([first, rest]).head(per).assign(weight=len(g) / min(per, len(g))))
    S = pd.concat(parts).head(n)
    return S[["pad_id", "block_id", "size_tercile", "weight"]].reset_index(drop=True)


def score(a, b, step: float) -> pd.DataFrame:
    th.require_columns(a, ["pad_id"], "reviewer_a")
    th.require_columns(b, ["pad_id"], "reviewer_b")
    A = gt.clean(a).dissolve("pad_id").reset_index()
    Bd = gt.clean(b).dissolve("pad_id").reset_index().set_index("pad_id")
    rows = []
    for _, r in A.iterrows():
        if r.pad_id not in Bd.index:
            rows.append(dict(pad_id=r.pad_id, status="missing_in_b"))
            continue
        g1, g2 = r.geometry, Bd.loc[r.pad_id, "geometry"]
        inter = g1.intersection(g2).area
        u = g1.union(g2).area
        msd, h95 = gt.boundary_dist(g1, g2, step)
        rows.append(dict(pad_id=r.pad_id, status="ok", iou=inter / u if u else np.nan,
                         log_ratio_a_over_b=float(np.log(g1.area / g2.area)), mean_boundary_m=msd, hausdorff95_m=h95))
    return th.tag(pd.DataFrame(rows), "a", "reproducibility_reference")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--draw", action="store_true")
    g.add_argument("--score", action="store_true")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    if a.draw:
        S = draw(pd.read_csv(th.inp(cfg, "by_pad")), cfg["redraw"]["n_pads"], int(cfg["seed"]))
        out = th.outp(cfg, "redraw_sheet")
        S.to_csv(out, index=False)
        print(S.size_tercile.value_counts().to_dict(), f"{S.block_id.nunique()} blocks\nwrote", out)
        return 0
    p = th.inp(cfg, "redraws")
    R = score(th.read_vector(p, layer="reviewer_a"), th.read_vector(p, layer="reviewer_b"), cfg["boundary_sample_m"])
    out = th.outp(cfg, "redraw_agreement")
    R.to_csv(out, index=False)
    print(R.describe().round(3).to_string(), "\nwrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
