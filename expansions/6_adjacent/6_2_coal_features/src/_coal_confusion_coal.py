"""6.2 S3. Confusion of the frozen well models with mine features in the coal area (Q2 primary).

Purpose
    Take the top K = 40 per km2 candidates of the frozen pit model and of the pad model over the complete coal
    blocks. Look up each candidate's adjudicated class from the S2 labels. Top-K candidates with no label yet are
    written to a to-label list in the S2 sample format (label them blind through the 6.3 sheets, then rerun).
    The matrix has adjudicated class rows (M S H W O U) and model columns. Primary (Q2, pit model) is the share of
    top-K candidates adjudicated M, S or H, with a block-bootstrap interval (blocks, B = 2000). Mine detections
    per km2 are reported beside it. Cells with fewer than 15 features are marked exploratory.
Inputs
    data/greene/results/coal/candidates/coal_well_candidates_greene.gpkg (S1)
    data/greene/results/coal/confuser_labels_adjudicated_greene.csv and confuser_sheet_key_greene.csv (S2 + 6.3 agreement)
    data/greene/derived/05/coal_blocks_greene.gpkg
Outputs (data/greene/results/coal/)
    coal_confusion_wells_vs_mine.csv, coal_confusion_summary.json, coal_confusion_wells_vs_mine.png,
    coal_confusion_to_label_greene.csv (only while labels are missing)
Run
    python expansions/6_adjacent/6_2_coal_features/src/_coal_confusion_coal.py [--out DIR] [--B 2000]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _coal_common as K
from _coal_common import C, ek


def topk_per_model(cands, blocks, k_per_km2: float):
    km2 = float(blocks.area.sum() / 1e6)
    out = []
    for m, g in cands.groupby("model"):
        top, k = C.top_k(g, km2, k_per_km2)
        out.append(top.assign(K=k))
    return pd.concat(out, ignore_index=True)


def confusion(top: pd.DataFrame, labels: pd.DataFrame, cfg: dict, blocks, B: int, primary_model: str = "pit"):
    lab = labels.set_index("uid")["class"]
    t = top.assign(cls=top.uid.map(lab))
    missing = t[t.cls.isna()]
    classes = cfg["classes"]["all"]
    mat = pd.crosstab(t.cls, t.model).reindex(index=classes, fill_value=0)
    mine = set(cfg["classes"]["mine"])
    km2 = dict(zip(blocks.block_id.astype(int), blocks.area / 1e6))
    res = {"n_topk": t.groupby("model").size().to_dict(), "n_unlabelled": int(len(missing)), "per_model": {}}
    seed = ek.child_seed(cfg["sample"]["master_seed"], 0, 40)
    for m, g in t.dropna(subset=["cls"]).groupby("model"):
        nm = {b: int(((g.block_id == b) & g.cls.isin(mine)).sum()) for b in km2}
        nl = {b: int((g.block_id == b).sum()) for b in km2}
        bl = sorted(km2)
        share = lambda L: sum(nm[b] for b in L) / sum(nl[b] for b in L) if sum(nl[b] for b in L) else np.nan  # noqa: E731
        rate = lambda L: sum(nm[b] for b in L) / sum(km2[b] for b in L)  # noqa: E731
        p, lo, hi, _ = ek.block_bootstrap(share, bl, B=B, seed=seed)
        r, rlo, rhi, _ = ek.block_bootstrap(rate, bl, B=B, seed=seed + 1)
        res["per_model"][m] = {"share_mine_of_topk": p, "lo95": lo, "hi95": hi, "mine_per_km2": r,
                               "mine_per_km2_lo95": rlo, "mine_per_km2_hi95": rhi,
                               "n_mine": int(sum(nm.values())), "n_labelled": int(sum(nl.values())),
                               "role": "primary" if m == primary_model else "exploratory"}
    res["exploratory_cells"] = [f"{r}/{c}" for r in mat.index for c in mat.columns if mat.loc[r, c] < 15]
    res["evidence_level"] = "a"
    return mat, res, missing


def render(mat: pd.DataFrame, png: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4, 4.5))
    ax.imshow(mat.to_numpy(), cmap="Blues", aspect="auto")  # one sequential hue, counts are ordered
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = int(mat.iloc[i, j])
            ax.text(j, i, str(v), ha="center", va="center", fontsize=9,
                    color="white" if v > mat.to_numpy().max() / 2 else ek.PALETTE["charcoal"])
    ax.set_xticks(range(mat.shape[1]), [f"{c} model top K" for c in mat.columns])
    ax.set_yticks(range(mat.shape[0]), mat.index)
    ax.set_ylabel("adjudicated class")
    fig.text(0.01, 0.01, "Evidence level a. M portal, S subsidence, H spoil, W well pit or pad, O other, U uncertain.",
             fontsize=6)
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--B", type=int, default=None)
    a = ap.parse_args()
    cfg = K.load_config(a.config)
    out = C.results_dir(cfg, a.out)
    ar = cfg["area"]
    import _confuser_sample_9t as S1
    blocks = C.read_vector(C.input_path(cfg, "blocks"), cfg["crs"], layer="blocks")
    cands = S1.load_candidates(cfg)
    cands["model"] = cands.src_layer
    cxy = np.column_stack([cands.geometry.centroid.x, cands.geometry.centroid.y])
    cands["block_id"], cands["cx"], cands["cy"] = C.block_of_points(cxy, blocks), cxy[:, 0], cxy[:, 1]
    top = topk_per_model(cands, blocks, cfg["score"]["k_per_km2"])
    lp, kp = out / f"confuser_labels_adjudicated_{ar}.csv", out / f"confuser_sheet_key_{ar}.csv"
    if not lp.exists():
        raise K.MissingInput(f"{lp} missing. Run S2 sheets and the 6.3 agreement script with config_6_2.json.")
    labels = pd.read_csv(lp)
    mat, res, missing = confusion(top, labels, cfg, blocks, a.B or cfg["score"]["B"])
    if len(missing):
        tl = out / f"coal_confusion_to_label_{ar}.csv"
        missing.assign(incl_prob=1.0, relabel=False, band=-3)[["uid", "cx", "cy", "band", "incl_prob", "score", "relabel"]].to_csv(tl, index=False)
        print(f"{len(missing)} top-K candidates are unlabelled. Label them blind from {tl}, then rerun.")
    mp = out / "coal_confusion_wells_vs_mine.csv"
    mat.to_csv(mp)
    js = out / "coal_confusion_summary.json"
    js.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    png = render(mat, out / "coal_confusion_wells_vs_mine.png")
    C.provenance(cfg, out, "coalconf", inputs=[lp, kp], outputs=[mp, js, png])
    print(mat.to_string())
    print(json.dumps(res["per_model"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
