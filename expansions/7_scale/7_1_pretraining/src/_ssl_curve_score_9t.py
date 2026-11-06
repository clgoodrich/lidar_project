"""Label-efficiency curves, the primary paired test and the decision for 7.1 (S5, S7).

Purpose
    Read every out-of-fold candidate file from the fine-tune runs. For each arm, fraction and seed,
    pool the held-out blocks of all folds and compute recall at K = 40 per km2 with the 7.3 scorer.
    Primary (fw_7_1 section 8). At f = 0.25, the preregistered arm minus A0, the mean over matched seeds
    inside each block resample (paired block bootstrap, B = 2000). Superiority against the useful gain G.
    G comes from config_7_1.json ("G") or the preregistration JSON (--prereg, key "G"), set before scoring
    (review 7.2-01 pattern in 7.1). It is never derived from the runs it judges and never floored.
    With G unset the decision is inconclusive. G_raw (A0 recall at f = 0.50 minus f = 0.25 on the same
    held-out blocks) is always reported as a diagnostic only.
    Fewer than 3 matched seeds voids the primary claim.
    Secondary, exploratory. Per-fraction differences, calibration per arm, curve fit recall = a - b n^-c
    and the label-efficiency ratio at 90% of A0 recall at f = 1.
    --audit-once (review 7.1-02) scores the sealed audit blocks once. It reads only audit_candidates_*.csv and
    audit_blocks_*.csv from _ssl_finetune_pit_9t.py --predict-audit, never the out-of-fold files. It needs a
    frozen P2 audit file and a primary arm. G (0.02) and finetune.audit_model_fold (0) are user defaults in the config. It writes
    results/tables/ssl_audit_lock.json (audit_opened true) before scoring and refuses any second run.

Inputs
    expansions/7_scale/7_1_pretraining/results/*/oof_candidates_*.csv and oof_blocks_*.csv
Outputs
    expansions/7_scale/7_1_pretraining/results/tables/ssl_recall_curves_9t.csv
    expansions/7_scale/7_1_pretraining/results/tables/ssl_G_frozen_9t.json
    expansions/7_scale/7_1_pretraining/results/tables/ssl_primary_decision_9t.json
    expansions/7_scale/7_1_pretraining/results/tables/ssl_audit_lock.json and audit/ssl_audit_decision_9t.json (--audit-once)
    expansions/7_scale/7_1_pretraining/results/figures/ssl_label_efficiency_9t.png

Run
    python expansions/7_scale/7_1_pretraining/src/_ssl_curve_score_9t.py --primary A1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ssl_pretrain_objectives_us import CFG, ek, load_cfg  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "7_3_benchmark" / "src"))
import _bench_evaluate_recall_k as sc  # noqa: E402

KEY = ["arm", "fraction", "seed"]


def load_runs(root: Path, stem: str = "oof") -> tuple[pd.DataFrame, pd.DataFrame]:
    c = [pd.read_csv(p) for p in sorted(root.rglob(f"{stem}_candidates_*.csv"))]
    b = [pd.read_csv(p) for p in sorted(root.rglob(f"{stem}_blocks_*.csv"))]
    if not c or not b:
        raise FileNotFoundError(f"no fine-tune outputs under {root}. Run _ssl_finetune_pit_9t.py first")
    cands, blocks = pd.concat(c, ignore_index=True), pd.concat(b, ignore_index=True)
    dup = blocks.duplicated(KEY + ["block_id"])
    if dup.any():
        raise AssertionError("a block is held out twice for one arm, fraction and seed")
    return cands, blocks


def payloads(cands, blocks) -> dict:
    out = {}
    for k, g in blocks.groupby(KEY):
        cg = cands[(cands["arm"] == k[0]) & np.isclose(cands["fraction"], k[1]) & (cands["seed"] == k[2])]
        out[k] = {int(b): p for b, p in zip(sorted(g["block_id"]), sc.payload_from_files(cg, g, strict=True))}
    return out


def recall(pl: dict, key, block_list) -> float:
    return sc.pooled_recall([pl[key][b] for b in block_list], K_PER_KM2)


def mean_over_seeds(pl, arm, f, seeds, block_list) -> float:
    return float(np.mean([recall(pl, (arm, f, s), block_list) for s in seeds]))


def curve_table(pl, blocks) -> pd.DataFrame:
    rows = []
    for k, d in pl.items():
        g = blocks[(blocks["arm"] == k[0]) & np.isclose(blocks["fraction"], k[1]) & (blocks["seed"] == k[2])]
        for fold, gf in g.groupby("fold"):
            bl = sorted(gf["block_id"].astype(int))
            r = sc.pooled_recall([d[b] for b in bl], K_PER_KM2)
            rows.append({"arm": k[0], "fraction": k[1], "seed": k[2], "fold": int(fold), "recall": r,
                         "truth": int(gf["n_truth"].sum()), "area_km2": float(gf["area_km2"].sum())})
        rows.append({"arm": k[0], "fraction": k[1], "seed": k[2], "fold": "pooled",
                     "recall": sc.pooled_recall(list(d.values()), K_PER_KM2), "truth": int(g["n_truth"].sum()),
                     "area_km2": float(g["area_km2"].sum())})
    return pd.DataFrame(rows)


class GUnset(ValueError):
    """G is null in the config and in the preregistration. The config default is 0.02 (user default 2026-11-06)."""


def resolve_G(cfg, prereg: dict | None, pl, seeds, block_list, path: Path) -> dict:
    """Review 7.2-01 (same pattern in 7.1). G is set before scoring, from the config or the preregistration.
    It is never chosen from the runs it judges and never floored. G_raw is always reported."""
    raw = None
    if seeds and all(("A0", 0.5, s) in pl for s in seeds):
        raw = mean_over_seeds(pl, "A0", 0.5, seeds, block_list) - mean_over_seeds(pl, "A0", 0.25, seeds, block_list)
    if cfg.get("G") is not None:
        G, src = float(cfg["G"]), "config_7_1.json G (set before scoring)"
    elif prereg and prereg.get("G") is not None:
        G, src = float(prereg["G"]), f"preregistration {prereg.get('_path', '')} G (set before scoring)"
    else:
        raise GUnset("G is null in config_7_1.json and the preregistration. The user default is 0.02")
    rec = {"G": G, "source": src, "G_raw": raw,
           "G_raw_note": "A0 recall f=0.50 minus f=0.25 on the same held-out blocks. Diagnostic only. "
                         "Never used as the margin and never floored",
           "seeds": [int(s) for s in seeds], "n_blocks": len(block_list)}
    path.write_text(json.dumps(rec, indent=2, default=float), encoding="utf-8")
    return rec


def fit_curve(n, r):
    from scipy.optimize import curve_fit
    f = lambda x, a, b, c: a - b * np.power(x, -c)  # noqa: E731
    try:
        p, _ = curve_fit(f, n, r, p0=[max(r), max(r) - min(r) + 1e-3, 0.5], maxfev=20000)
        return {"a": p[0], "b": p[1], "c": p[2]}
    except Exception as e:  # noqa: BLE001 - descriptive only, not a gate
        return {"error": str(e)}


def labels_to(target, fit):
    if "error" in fit or fit["a"] <= target or fit["b"] <= 0 or fit["c"] <= 0:
        return float("nan")
    return float((fit["b"] / (fit["a"] - target)) ** (1 / fit["c"]))


def figure(tab: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # ek.PALETTE lost/found set. Worst pair dE 21.1 deutan, 22.6 normal (dataviz validator --pairs all,
    # recorded in expkit). Grey and charcoal are neutrals. A second encoding (marker) is on every arm.
    col = {"A0": ek.PALETTE["charcoal"], "A1": ek.PALETTE["blue"], "A2": ek.PALETTE["orange"],
           "A3": ek.PALETTE["dark_red"], "A4": ek.PALETTE["grey"]}
    mk = {"A0": "o", "A1": "s", "A2": "^", "A3": "D", "A4": "v"}
    t = tab[tab["fold"] == "pooled"]
    fig, ax = plt.subplots(figsize=(6, 4))
    for arm, g in t.groupby("arm"):
        s = g.groupby("fraction")["recall"].agg(["mean", "min", "max"]).reset_index()
        ax.plot(s["fraction"] * 100, s["mean"], marker=mk.get(arm, "x"), color=col.get(arm, "black"), label=arm)
        ax.fill_between(s["fraction"] * 100, s["min"], s["max"], color=col.get(arm, "black"), alpha=0.15)
    ax.set_xscale("log")
    ax.set_xlabel("Label fraction (% of training blocks)")
    ax.set_ylabel("Recall at 40 per km2")
    ax.set_title("Recall of drawn pit floors against label fraction")
    ax.legend(title="Arm", frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


K_PER_KM2 = 40.0


def analyse(cfg, root: Path, primary: str | None, B: int, tables: Path, figs: Path, prereg: dict | None = None) -> dict:
    global K_PER_KM2
    K_PER_KM2 = cfg["scoring"]["k_per_km2"]
    cands, blocks = load_runs(root)
    pl = payloads(cands, blocks)
    tab = curve_table(pl, blocks)
    tab.to_csv(tables / "ssl_recall_curves_9t.csv", index=False)
    f0 = cfg["finetune"]["primary_fraction"]
    seeds_a0 = sorted({k[2] for k in pl if k[0] == "A0" and np.isclose(k[1], f0)})
    res: dict = {"evidence_level": "a", "k_per_km2": K_PER_KM2, "primary_fraction": f0}
    if not seeds_a0:
        raise FileNotFoundError("no A0 runs at the primary fraction")
    block_list = sorted(pl[("A0", f0, seeds_a0[0])])
    res["G"] = resolve_G(cfg, prereg, pl, seeds_a0, block_list, tables / "ssl_G_frozen_9t.json")
    primary = primary or cfg["finetune"]["primary_arm"]
    if primary is None:
        res["primary"] = "not scored. The primary arm is a user decision named in the preregistration"
    else:
        seeds = sorted(set(seeds_a0) & {k[2] for k in pl if k[0] == primary and np.isclose(k[1], f0)})
        stat = lambda bl: mean_over_seeds(pl, primary, f0, seeds, bl) - mean_over_seeds(pl, "A0", f0, seeds, bl)  # noqa: E731
        point, lo, hi, _ = ek.block_bootstrap(stat, block_list, B=B, seed=cfg["master_seed"])
        G = res["G"]["G"]
        res["primary"] = {"arm": primary, "diff": point, "lo": lo, "hi": hi, "n_seeds": len(seeds),
                          "n_blocks": len(block_list), "G": G, "G_raw": res["G"]["G_raw"],
                          "decision": ("void (fewer than 3 matched seeds)" if len(seeds) < 3 else
                                       ek.decide(lo, hi, G, "superiority"))}
    expl = {}
    for (arm, f, s) in sorted(pl):
        if arm == "A0":
            continue
        sd = sorted({k[2] for k in pl if k[0] == arm and np.isclose(k[1], f)} &
                    {k[2] for k in pl if k[0] == "A0" and np.isclose(k[1], f)})
        if sd and f"{arm}|{f}" not in expl:
            expl[f"{arm}|{f}"] = mean_over_seeds(pl, arm, f, sd, block_list) - mean_over_seeds(pl, "A0", f, sd, block_list)
    res["exploratory_diffs"] = expl
    res["calibration"] = {arm: ek.calibration(pd.notna(g["matched_truth"]).astype(int), g["score"])
                          for arm, g in cands.groupby("arm") if len(g)}
    pooled = tab[tab["fold"] == "pooled"].groupby(["arm", "fraction"])["recall"].mean().reset_index()
    fits = {arm: fit_curve(g["fraction"].to_numpy(), g["recall"].to_numpy())
            for arm, g in pooled.groupby("arm") if g["fraction"].nunique() >= 3}
    a0_full = pooled[(pooled["arm"] == "A0") & np.isclose(pooled["fraction"], 1.0)]["recall"]
    if len(a0_full) and "A0" in fits:
        tgt = 0.9 * float(a0_full.iloc[0])
        n0 = labels_to(tgt, fits["A0"])
        res["label_efficiency_ratio"] = {arm: (n0 / labels_to(tgt, ft) if np.isfinite(labels_to(tgt, ft)) else None)
                                         for arm, ft in fits.items() if arm != "A0"}
    res["curve_fits"] = fits
    figure(tab, figs / "ssl_label_efficiency_9t.png")
    (tables / "ssl_primary_decision_9t.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    return res


class AuditRefused(RuntimeError):
    """--audit-once cannot run (already opened, audit not frozen, or a decision is missing)."""


def audit_once(cfg, root: Path, primary: str | None, B: int, tables: Path, audit_csv: Path | None = None,
               prereg: dict | None = None, allow_unfrozen: bool = False) -> dict:
    """Review 7.1-02. Score the sealed audit blocks once. The lock is written before any score is computed."""
    import datetime as dt
    lock = tables / "ssl_audit_lock.json"
    if lock.exists():
        raise AuditRefused(f"refused. The audit set was already opened ({lock})")
    apath = Path(audit_csv) if audit_csv else ek.default_audit_path()
    try:                                                  # frozen file or refuse
        df = ek.require_audit(apath, allow_missing=False, allow_unfrozen=allow_unfrozen)
    except (FileNotFoundError, AssertionError) as e:
        raise AuditRefused(f"refused. {e}") from e
    aud = sorted(ek.audit_ids(df, ("audit",)))
    primary = primary or cfg["finetune"]["primary_arm"]
    G = cfg.get("G") if cfg.get("G") is not None else (prereg or {}).get("G")
    if G is None:
        raise GUnset("G is null in config_7_1.json and the preregistration. The user default is 0.02")
    fold = int(cfg["finetune"]["audit_model_fold"])          # user default 0 (2026-11-06)
    if primary is None:
        raise AuditRefused("refused. Set the primary arm before the audit is opened")
    cands, blocks = load_runs(root, "audit")
    f0 = cfg["finetune"]["primary_fraction"]
    keep = blocks["arm"].isin([primary, "A0"]) & np.isclose(blocks["fraction"], f0) & (blocks["fold"] == fold)
    blocks = blocks[keep]
    cands = cands[cands["arm"].isin([primary, "A0"]) & np.isclose(cands["fraction"], f0) & (cands["fold"] == fold)]
    if set(blocks["audit_sha256"]) != {df.attrs["sha256"]}:
        raise AuditRefused("audit predictions were made against a different audit file")
    for k, g in blocks.groupby(KEY):
        if sorted(g["block_id"].astype(int)) != aud:
            raise AuditRefused(f"audit predictions for {k} do not cover exactly the sealed audit blocks")
    lock.write_text(json.dumps({"audit_opened": True, "opened": dt.datetime.now().isoformat(timespec="seconds"),
                                "audit_file": str(apath), "audit_sha256": df.attrs["sha256"], "primary": primary,
                                "G": float(G), "model_fold": int(fold), "runs": str(root)}, indent=2), encoding="utf-8")
    pl = payloads(cands, blocks)
    seeds = sorted({k[2] for k in pl if k[0] == "A0"} & {k[2] for k in pl if k[0] == primary})
    stat = lambda bl: mean_over_seeds(pl, primary, f0, seeds, bl) - mean_over_seeds(pl, "A0", f0, seeds, bl)  # noqa: E731
    point, lo, hi, _ = ek.block_bootstrap(stat, aud, B=B, seed=cfg["master_seed"])
    res = {"evidence_level": "audit, scored once", "audit_opened": True, "arm": primary, "fraction": f0,
           "model_fold": int(fold), "diff": point, "lo": lo, "hi": hi, "G": float(G), "n_seeds": len(seeds),
           "n_blocks": len(aud), "decision": ek.decide(lo, hi, float(G), "superiority") if len(seeds) >= 3
           else "void (fewer than 3 matched seeds)"}
    out = tables / "audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ssl_audit_decision_9t.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.1 curves and primary decision.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--runs", default=str(ek.sub("7.1", "results")))
    ap.add_argument("--primary", default=None)
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--prereg", default=None, help="preregistration JSON with key G (used when config G is null)")
    ap.add_argument("--audit-once", action="store_true",
                    help="score the sealed audit blocks once (needs a frozen P2 audit). Refuses a second run")
    ap.add_argument("--audit", default=None, help="P2 audit CSV for --audit-once (default the frozen 9t file)")
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    prereg = None
    if a.prereg:
        prereg = {**json.loads(Path(a.prereg).read_text(encoding="utf-8")), "_path": a.prereg}
    tables, figs = ek.sub("7.1", "results/tables"), ek.sub("7.1", "results/figures")
    try:
        if a.audit_once:
            res = {"primary": audit_once(cfg, Path(a.runs), a.primary, a.B, tables,
                                         Path(a.audit) if a.audit else None, prereg)}
        else:
            res = analyse(cfg, Path(a.runs), a.primary, a.B, tables, figs, prereg)
    except AuditRefused as e:
        print(e, file=sys.stderr)
        return 3
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    print(json.dumps(res.get("primary"), indent=2, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
