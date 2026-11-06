"""5.1 S0. Upstream model inventory for context stacking (tile 9t).

Purpose
    List every upstream model (pit, pad, road) that could feed a stage-2 context model. For each model give the
    checkpoint path and SHA-256, the per-fold probability rasters, the block-to-fold assignment it used, whether
    that assignment can be read from a saved file, and whether its fold scheme matches the reference scheme.
    A model whose scheme differs from the reference, or whose scheme is unknown, is flagged "must retrain".
    Protocol section 8. Pit and pad folds are balanced on different counts, so they are expected to differ.

Inputs (config_5_1.json)
    upstream_models.*.dir      @models/pit/unet_cv5, @models/pad/unet_cv5_iso, @models/road/... (data/9t/models/...)
    upstream_models.*.assign   fold assignment CSV in that dir (pit_inside_id|pad_id, block_id, fold)
    inputs.shared_folds        optional. If present it is the reference scheme. Otherwise the pit_cv5 scheme is.
Outputs
    outputs.inventory_csv  -> expansions/5_tasks/5_1_context_features/results/tables/context_upstream_inventory_9t.csv
    outputs.inventory_md   -> expansions/5_tasks/5_1_context_features/results/tables/context_upstream_inventory_9t.md
    The md table is the draft of docs/iterations/context_upstream_inventory.md (the lead copies it there).
Run
    python expansions/5_tasks/5_1_context_features/src/_context_upstream_inventory_9t.py [--no-hash]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

ek = th.ek


def block_fold_map(assign_csv: Path) -> dict[int, int]:
    """block_id -> fold from a per-feature assignment CSV. Rows with no block id are off-tile and dropped.
    Raises if one block maps to two folds (the scheme would not be block-grouped)."""
    d = pd.read_csv(assign_csv).dropna(subset=["block_id", "fold"])
    d = d.astype({"block_id": int, "fold": int})
    n = d.groupby("block_id").fold.nunique()
    if (n > 1).any():
        raise AssertionError(f"{assign_csv}: blocks in two folds {list(n[n > 1].index[:5])}")
    return dict(d.drop_duplicates("block_id")[["block_id", "fold"]].itertuples(index=False, name=None))


def scheme_agreement(a: dict, b: dict) -> dict:
    """Compare two block->fold maps up to fold relabelling. Same partition means stackable as-is."""
    common = sorted(set(a) & set(b))
    if not common:
        return dict(n_common=0, same_partition=False, share_same_fold=float("nan"))
    ta = pd.Series({k: a[k] for k in common})
    tb = pd.Series({k: b[k] for k in common})
    ct = pd.crosstab(ta, tb)
    # a partition matches when every fold of a maps to exactly one fold of b and vice versa
    same = bool(((ct > 0).sum(axis=1) == 1).all() and ((ct > 0).sum(axis=0) == 1).all())
    best = ct.max(axis=1).sum() / len(common)
    return dict(n_common=len(common), same_partition=same, share_same_fold=float(best),
                only_in_a=len(set(a) - set(b)), only_in_b=len(set(b) - set(a)))


def inventory(cfg: dict, do_hash: bool = True) -> pd.DataFrame:
    models = cfg["upstream_models"]
    schemes = {}
    for name, m in models.items():
        d = th.resolve(m["dir"])
        if m.get("assign") and (d / m["assign"]).exists():
            schemes[name] = block_fold_map(d / m["assign"])
    ref_name = "shared_folds"
    if th.has(cfg, "shared_folds"):
        sf = json.loads(th.inp(cfg, "shared_folds").read_text())
        ref = {int(k): int(v) for k, v in sf["block_to_fold"].items()}
    else:
        ref_name = "pit_cv5"
        ref = schemes.get("pit_cv5", {})
    rows = []
    for name, m in models.items():
        d = th.resolve(m["dir"])
        r = dict(model=name, role=m["role"], dir=str(d), exists=d.exists())
        if not d.exists():
            r.update(status="absent", must_retrain=True)
            rows.append(r)
            continue
        ckpts = sorted(d.glob("fold*/best.pt")) or sorted(d.glob("best.pt"))
        probs = sorted(d.glob("fold*/*prob*.tif")) + sorted(d.glob("*prob*.tif"))
        r["n_checkpoints"] = len(ckpts)
        r["checkpoints"] = ";".join(str(c.relative_to(d)) for c in ckpts)
        if do_hash:
            r["checkpoint_sha256"] = ";".join(ek.sha256(c)[:16] for c in ckpts)
        r["prob_rasters"] = ";".join(str(p.relative_to(d)) for p in probs)
        r["per_fold"] = any("fold" in c.parent.name for c in ckpts)
        if name in schemes:
            s = schemes[name]
            agr = scheme_agreement(ref, s) if ref else {}
            r.update(n_blocks=len(s), folds=len(set(s.values())), assignment_file=m["assign"],
                     assignment_recoverable="held_out lists only (inner val unrecoverable, protocol section 3)",
                     reference=ref_name, **{f"vs_ref_{k}": v for k, v in agr.items()})
            r["must_retrain"] = not agr.get("same_partition", False)
        else:
            r.update(n_blocks=None, folds=None, assignment_file="",
                     assignment_recoverable="no fold assignment on disk; trained once, in-sample on 9t",
                     reference=ref_name, must_retrain=True)
        # historical models were never trained on the shared scheme, and only isolated trainers are allowed
        if ref_name == "shared_folds":
            r["must_retrain"] = True
        # protocol section 3. Only isolated trainers reject windows that touch held-out ground
        r["isolated_trainer"] = bool(m.get("isolated", False))
        reasons = []
        if r["must_retrain"]:
            reasons.append("scheme")
        if not r["isolated_trainer"]:
            reasons.append("not isolated")
        r["must_retrain"] = bool(reasons)
        r["status"] = ("must retrain (" + ", ".join(reasons) + ")") if reasons else "stackable"
        rows.append(r)
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame) -> str:
    cols = ["model", "role", "n_checkpoints", "per_fold", "n_blocks", "folds", "vs_ref_share_same_fold",
            "vs_ref_same_partition", "status"]
    cols = [c for c in cols if c in df.columns]
    lines = ["# Upstream inventory for context stacking (9t)", "",
             "Draft of `docs/iterations/context_upstream_inventory.md`. Written by "
             "`expansions/5_tasks/5_1_context_features/src/_context_upstream_inventory_9t.py`.",
             f"Reference scheme is `{df['reference'].dropna().iloc[0] if 'reference' in df and df['reference'].notna().any() else 'none'}`.",
             "Every number below comes from the CSV beside this file.", "",
             "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(r.get(c)) else (f"{r[c]:.3f}" if isinstance(r[c], float) else str(r[c]))
                                       for c in cols) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--no-hash", action="store_true", help="skip SHA-256 of checkpoints (faster)")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    df = inventory(cfg, do_hash=not a.no_hash)
    csv, md = th.outp(cfg, "inventory_csv"), th.outp(cfg, "inventory_md")
    df.to_csv(csv, index=False)
    md.write_text(to_markdown(df), encoding="utf-8")
    print(df[[c for c in ("model", "n_checkpoints", "n_blocks", "vs_ref_share_same_fold", "status") if c in df]].to_string(index=False))
    print(f"wrote {csv}\nwrote {md}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except th.MissingInput as e:
        print(e.args[0], file=sys.stderr)
        sys.exit(2)
