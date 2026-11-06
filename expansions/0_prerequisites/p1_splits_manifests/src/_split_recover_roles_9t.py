"""P1 S0. Recover which CV split roles of the trained 9t models can still be recovered.

Purpose
    For each fold of each trained CV model, read the held-out block list stored in the checkpoint
    (`checkpoint_extra["held_out_blocks"]`), parse the training log for the per-fold block and feature
    counts, and compare the held-out list with (a) the list the historical assign_folds gives today and
    (b) the exporter's saved list (`_save_cv_split_manifests_9t.py`). Inner validation and train roles are
    marked unrecoverable. The log counts also show whether the NaN block id sat inside the inner lists.
    Optional `--consistency` counts how many NaN positions in the historical sort agree with the logged
    counts. That count is exploratory. It never becomes a recovered role.

Inputs
    data/9t/models/pit/unet_cv5/fold{0..4}/best.pt, data/9t/models/pad/unet_cv5/fold{0..4}/best.pt,
    data/9t/models/pad/unet_cv5_iso/fold{0..4}/best.pt (if present)
    data/9t/models/pit/unet_cv5/_pit_cv5_ann712_train.log, data/9t/models/pad/unet_cv5/_pad_cv5_ann712_train.log,
    data/9t/models/pad/unet_cv5_iso/run_pad_unet_iso_cv5_9t.log
    data/9t/results/splits/cv_split_blocks_{pit,pad}_9t.csv (exporter), the manifests (through the trainers)

Outputs
    <out-dir>/cv_split_recovery_9t.csv  columns model, fold, role, recoverable, source, n_blocks, n_pits,
                                        n_blocks_logged, nan_in_inner_lists, matches_exporter, matches_assign_folds
    <out-dir>/cv_split_recovery_9t.md   plain statement of what is and is not recoverable
    Default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/splits/
    Run record under expansions/0_prerequisites/p1_splits_manifests/results/<run_id>/

Run
    python expansions/0_prerequisites/p1_splits_manifests/src/_split_recover_roles_9t.py [--out-dir DIR] [--consistency]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split_core_lib_9t as sc  # noqa: E402
ek = sc.ek

LOG_RE = re.compile(r"train (\d+) \w+ / (\d+) blocks\s+inner-val (\d+) / (\d+)\s+HELD-OUT (\d+) / (\d+)")
FOLD_RE = re.compile(r"^FOLD (\d+)")


def model_specs() -> list[dict]:
    m = ek.path_for("models")
    return [
        dict(model="pit_unet_cv5", task="pit", dir=m / "pit" / "unet_cv5", log="_pit_cv5_ann712_train.log"),
        dict(model="pad_unet_cv5", task="pad", dir=m / "pad" / "unet_cv5", log="_pad_cv5_ann712_train.log"),
        dict(model="pad_unet_cv5_iso", task="pad", dir=m / "pad" / "unet_cv5_iso", log="run_pad_unet_iso_cv5_9t.log"),
    ]


def parse_log(path: Path) -> dict[int, dict]:
    """Per-fold counts from a trainer log: train/val/held-out features and blocks. Last FOLD block wins."""
    out, fold = {}, None
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = FOLD_RE.match(line.strip())
        if m:
            fold = int(m.group(1))
            continue
        m = LOG_RE.search(line)
        if m and fold is not None:
            a = list(map(int, m.groups()))
            out[fold] = dict(train_feats=a[0], train_blocks=a[1], val_feats=a[2], val_blocks=a[3],
                             held_feats=a[4], held_blocks=a[5])
    return out


def checkpoint_held(path: Path):
    """held_out_blocks from a checkpoint, or None. CPU load, weights never used."""
    if not path.exists():
        return None
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=False)
    hb = ck.get("held_out_blocks") if isinstance(ck, dict) else None
    if hb is None and isinstance(ck, dict):
        hb = (ck.get("extra") or {}).get("held_out_blocks")
    return None if hb is None else sorted(int(b) for b in hb)


def exporter_lists(task: str) -> dict[int, dict[str, list[int]]]:
    p = ek.path_for("results_9t") / "splits" / f"cv_split_blocks_{task}_9t.csv"
    if not p.exists():
        return {}
    df = pd.read_csv(p)
    out: dict = {}
    for (f, role), g in df.groupby(["fold", "role"]):
        out.setdefault(int(f), {})[role] = sorted(g.block_id.astype(int))
    return out


def nan_positions_consistent(man, held, fold, seed, frac, logged) -> int:
    """Exploratory. How many insertion positions of NaN in sorted(rest) give the logged val and train counts."""
    rest = sorted(int(b) for b in set(man.block_id.dropna().astype(int)) - set(held))
    counts = man.dropna(subset=["block_id"]).groupby(man.block_id.dropna().astype(int)).size()
    hits = 0
    for pos in range(len(rest) + 1):
        arr = np.array(rest[:pos] + [np.nan] + rest[pos:], float)
        shuf = list(np.random.default_rng(ek.child_seed(seed, fold)).permutation(arr))
        nv = max(1, int(round(frac * len(shuf))))
        val = [b for b in shuf[:nv] if not np.isnan(b)]
        tr = [b for b in shuf[nv:] if not np.isnan(b)]
        nval_b = nv
        if (nval_b == logged["val_blocks"] and int(counts.reindex(val).fillna(0).sum()) == logged["val_feats"]
                and int(counts.reindex(tr).fillna(0).sum()) == logged["train_feats"]):
            hits += 1
    return hits


def recover(consistency: bool = False) -> tuple[pd.DataFrame, list[str]]:
    rows, notes = [], []
    for spec in model_specs():
        task = spec["task"]
        if not spec["dir"].exists():
            notes.append(f"{spec['model']}: model folder missing at {spec['dir']}, skipped")
            continue
        p = sc.task_params(task)
        man = sc.load_manifest(task)
        held_now = sc.held_out_folds(man, 5, p["seed"], p["assign_folds"])
        exp = exporter_lists(task)
        log = parse_log(spec["dir"] / spec["log"])
        n_feat = man.dropna(subset=["block_id"]).groupby(man.block_id.dropna().astype(int)).size()
        for f in range(5):
            ck_held = checkpoint_held(spec["dir"] / f"fold{f}" / "best.pt")
            src = "checkpoint" if ck_held is not None else "assign_folds (checkpoint lacks held_out_blocks)"
            held = ck_held if ck_held is not None else held_now[f]
            lg = log.get(f, {})
            rest_n = len(set(man.block_id.dropna().astype(int)) - set(held))
            nan_in = (lg.get("val_blocks", 0) + lg.get("train_blocks", 0) == rest_n + 1) if lg else None
            rows.append(dict(model=spec["model"], fold=f, role="held_out", recoverable=True, source=src,
                             n_blocks=len(held), n_pits=int(n_feat.reindex(held).fillna(0).sum()),
                             n_blocks_logged=lg.get("held_blocks"), nan_in_inner_lists=nan_in,
                             matches_exporter=(exp.get(f, {}).get("held_out") == held) if exp else None,
                             matches_assign_folds=held == held_now[f]))
            for role, kb, kf in (("inner_val", "val_blocks", "val_feats"), ("train", "train_blocks", "train_feats")):
                r = dict(model=spec["model"], fold=f, role=role, recoverable=False,
                         source="unrecoverable, treated as used (log counts only)", n_blocks=None,
                         n_pits=lg.get(kf), n_blocks_logged=lg.get(kb), nan_in_inner_lists=nan_in,
                         matches_exporter=None, matches_assign_folds=None)
                if consistency and role == "inner_val" and lg:
                    r["nan_positions_consistent_exploratory"] = nan_positions_consistent(
                        man, held, f, p["seed"], p["inner_val_frac"], lg)
                rows.append(r)
            if ck_held is not None and ck_held != held_now[f]:
                notes.append(f"{spec['model']} fold {f}: checkpoint held-out differs from assign_folds today")
    return pd.DataFrame(rows), notes


def write_md(df: pd.DataFrame, notes: list[str], path: Path) -> None:
    h = df[df.role == "held_out"]
    ok_exp = h.matches_exporter.dropna()
    lines = [
        "# CV split recovery on 9t", "",
        "Written by `expansions/0_prerequisites/p1_splits_manifests/src/_split_recover_roles_9t.py`.",
        "Every number below comes from `cv_split_recovery_9t.csv` in the same folder.", "",
        "## What is recoverable",
        f"- Held-out lists. {int(h.recoverable.sum())} of {len(h)} model folds were read. "
        f"{int((h.source == 'checkpoint').sum())} came from the checkpoint itself.",
        f"- Held-out lists equal the exporter lists in {int(ok_exp.sum())} of {len(ok_exp)} folds compared.",
        f"- Held-out lists equal assign_folds today in {int(h.matches_assign_folds.sum())} of {len(h)} folds.",
        "- Inner validation and train lists are unrecoverable. The code that drew them put a NaN block id at a",
        "  position that changed between processes. Only the logged counts survive.",
        f"- The logged inner counts include the NaN block in {int(h.nan_in_inner_lists.fillna(False).sum())} of "
        f"{int(h.nan_in_inner_lists.notna().sum())} folds with a log.",
        "", "## Audit consequence",
        "Every block that is not held out by model k counts as used by model k. This covers training,",
        "inner validation, epoch choice and threshold choice.", "",
    ]
    if notes:
        lines += ["## Notes"] + [f"- {n}" for n in notes] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-dir", type=Path, default=None, help="default data/9t/results/splits/")
    ap.add_argument("--consistency", action="store_true", help="exploratory NaN-position count per fold")
    a = ap.parse_args(argv)
    out = a.out_dir or (ek.path_for("results_9t") / "splits")
    out.mkdir(parents=True, exist_ok=True)
    df, notes = recover(a.consistency)
    if df.empty:
        raise SystemExit("no CV model folders found under path_for('models'). Nothing to recover.")
    csv, md = out / "cv_split_recovery_9t.csv", out / "cv_split_recovery_9t.md"
    df.to_csv(csv, index=False)
    write_md(df, notes, md)
    run = ek.new_run("p1", "split_recover", {"consistency": a.consistency, "out": str(out)},
                     why="S0 recover recoverable split roles.")
    ek.write_provenance(run, inputs=[s["dir"] / s["log"] for s in model_specs()], outputs=[csv, md])
    h = df[df.role == "held_out"]
    print(h[["model", "fold", "source", "n_blocks", "matches_exporter", "matches_assign_folds",
             "nan_in_inner_lists"]].to_string(index=False))
    for n in notes:
        print("NOTE", n)
    print(f"wrote {csv}\nwrote {md}\nrun record {run}")
    bad = h[(h.source == "checkpoint") & (h.matches_exporter == False)]  # noqa: E712
    return 1 if len(bad) else 0


if __name__ == "__main__":
    sys.exit(main())
