"""P1 S2. Write the immutable future split file for the 9t pit and pad CV, or verify an existing one.

Purpose
    Build the deterministic split (P1 S2 algorithm) and save it as one JSON with explicit block lists per
    task, fold and role. Held-out lists come from the historical assign_folds and seed, so they do not
    change. Inner validation is drawn from `sorted(int ids not held out)` with
    `np.random.default_rng(seed + 1000 * k)` and the 20% rule. The file also records the seed, the dropped
    NaN row counts, the manifest SHA-256 and a SHA-256 of every list. A file that exists is never
    overwritten. A new version gets a new name (`--version 2`).
    `--verify FILE` recomputes everything from the manifests and checks the file. It fails on any
    difference, on a changed manifest hash, or on any QC problem.

QC (fail closed)
    No NaN id, no block in two roles within a fold, union of roles equals the feature-bearing block set,
    held-out lists equal the exporter lists in data/9t/results/splits/cv_split_blocks_<task>_9t.csv.

Inputs
    data/9t/derived/05/pit_dataset_manifest.csv, pad_dataset_manifest.csv (through the trainers)
    data/9t/results/splits/cv_split_blocks_{pit,pad}_9t.csv (exporter, held-out lists only)

Outputs
    <out-dir>/cv_splits_future_9t_v<version>.json
    Default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/splits/
    Run record under expansions/0_prerequisites/p1_splits_manifests/results/<run_id>/

Run
    python expansions/0_prerequisites/p1_splits_manifests/src/_split_future_write_9t.py [--out-dir DIR] [--version 1]
    python expansions/0_prerequisites/p1_splits_manifests/src/_split_future_write_9t.py --verify data/9t/results/splits/cv_splits_future_9t_v1.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split_core_lib_9t as sc  # noqa: E402
ek = sc.ek

K = 5


def build(manifests: dict[str, Path | None] | None = None, exporter_dir: Path | None = None,
          check_exporter: bool = True, exclude: set[int] | None = None, exclude_source: str = "") -> dict:
    """The split document for every task. Raises on any QC problem.

    exclude  block ids (P2 audit and buffer rows) removed from every role after the historical fold
             assignment. Held-out lists then become subsets of the historical ones. Fold assignment is not
             redone, so the folds stay comparable with the historical models.
    """
    exclude = set(exclude or ())
    manifests = manifests or {t: None for t in sc.TASKS}
    doc = {"schema": "wellsight.cv_splits.v1", "tile": "9t", "k": K, "label": "future",
           "note": "Immutable once committed. A new version gets a new file. Held-out lists equal the "
                   "historical ones. Inner lists are new and were never used by the historical models.",
           "tasks": {}}
    for task, mpath in manifests.items():
        p = sc.task_params(task)
        mp = Path(mpath) if mpath else p["manifest"]
        man = sc.load_manifest(task, mp)
        n_nan = int(man.block_id.isna().sum())
        splits = sc.make_splits(man, K, p["seed"], p["inner_val_frac"], p["assign_folds"], "fixed")
        blocks = set(int(b) for b in man.block_id.dropna().astype(int).unique())
        removed = sorted(blocks & exclude)
        if exclude:
            splits = {f: {r: [b for b in v if b not in exclude] for r, v in roles.items()} for f, roles in splits.items()}
            blocks -= exclude
        probs = sc.check_roles(splits, blocks)
        if check_exporter:
            ed = exporter_dir or (ek.path_for("results_9t") / "splits")
            exp = ed / f"cv_split_blocks_{task}_9t.csv"
            if not exp.exists():
                probs.append(f"exporter list missing at {exp}")
            else:
                import pandas as pd
                e = pd.read_csv(exp)
                for f in range(K):
                    eh = sorted(e[(e.fold == f) & (e.role == "held_out")].block_id.astype(int))
                    eh = [b for b in eh if b not in exclude]
                    if eh != splits[f]["held_out"]:
                        probs.append(f"{task} fold {f}: held-out differs from exporter")
        if probs:
            raise AssertionError(f"{task} split QC failed: " + "; ".join(probs))
        doc["tasks"][task] = {
            "manifest": str(mp), "manifest_sha256": ek.sha256(mp), "manifest_rows": int(len(man)),
            "rows_without_block_dropped": n_nan, "n_blocks": len(blocks), "seed": p["seed"],
            "excluded_audit_blocks": removed, "exclude_source": exclude_source,
            "inner_val_frac": p["inner_val_frac"], "child_seed_rule": "seed + 1000 * fold",
            "folds": {str(f): {r: splits[f][r] for r in sc.ROLES} for f in range(K)},
            "list_sha256": {str(f): v for f, v in sc.fold_hashes(splits).items()},
        }
    doc["content_sha256"] = sc.lists_hash(doc["tasks"])
    return doc


def verify(path: Path, manifests=None, exporter_dir=None, check_exporter=True) -> list[str]:
    """Recompute and compare. Returns a list of problems (empty means pass)."""
    saved = json.loads(Path(path).read_text(encoding="utf-8"))
    probs = []
    if sc.lists_hash(saved["tasks"]) != saved.get("content_sha256"):
        probs.append("content_sha256 does not match the file's own lists (file edited by hand?)")
    mans = manifests or {t: Path(saved["tasks"][t]["manifest"]) for t in saved["tasks"]}
    try:
        excl = set().union(*[set(v.get("excluded_audit_blocks", [])) for v in saved["tasks"].values()])
        src = next((v.get("exclude_source", "") for v in saved["tasks"].values()), "")
        now = build(mans, exporter_dir, check_exporter, exclude=excl, exclude_source=src)
    except AssertionError as e:
        return probs + [str(e)]
    for t in saved["tasks"]:
        a, b = saved["tasks"][t], now["tasks"].get(t)
        if b is None:
            probs.append(f"{t}: missing on recompute")
            continue
        if a["manifest_sha256"] != b["manifest_sha256"]:
            probs.append(f"{t}: manifest hash changed since the split file was written")
        if a["folds"] != b["folds"]:
            probs.append(f"{t}: recomputed lists differ")
    return probs


def split_file_for(task: str, path: Path) -> dict:
    """Reader used by trainers. Returns {fold(int): {role: [ids]}} and checks the file's own hash."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if sc.lists_hash(doc["tasks"]) != doc.get("content_sha256"):
        raise AssertionError(f"{path}: content hash mismatch")
    return {int(f): v for f, v in doc["tasks"][task]["folds"].items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P1 S2 write or verify the future split file")
    ap.add_argument("--out-dir", type=Path, default=None, help="default data/9t/results/splits/")
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--verify", type=Path, default=None)
    ap.add_argument("--no-exporter-check", action="store_true")
    ap.add_argument("--exclude-audit", type=Path, default=None,
                    help="frozen P2 audit file. Its audit and buffer blocks leave every role (write v2 or later)")
    a = ap.parse_args(argv)
    if a.verify:
        probs = verify(a.verify, check_exporter=not a.no_exporter_check)
        print("PASS" if not probs else "FAIL\n  " + "\n  ".join(probs))
        return 0 if not probs else 1
    out = a.out_dir or (ek.path_for("results_9t") / "splits")
    out.mkdir(parents=True, exist_ok=True)
    dst = out / f"cv_splits_future_9t_v{a.version}.json"
    if dst.exists():
        raise SystemExit(f"{dst} exists and is immutable. Use --version {a.version + 1} for a new split.")
    excl, src = set(), ""
    if a.exclude_audit:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "p2_audit_set" / "src"))
        import _audit_guard_lib as ag
        aud = ag.load_audit(a.exclude_audit)
        excl, src = set(aud.block_id.astype(int)), f"{a.exclude_audit} sha256 {aud.attrs['sha256']}"
    doc = build(check_exporter=not a.no_exporter_check, exclude=excl, exclude_source=src)
    doc["written"] = dt.datetime.now().isoformat(timespec="seconds")
    dst.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    run = ek.new_run("p1", "split_future", {"version": a.version, "out": str(out)},
                     why="S2 write the immutable future split file.")
    ek.write_provenance(run, inputs=[Path(v["manifest"]) for v in doc["tasks"].values()], outputs=[dst],
                        params={"content_sha256": doc["content_sha256"]})
    for t, v in doc["tasks"].items():
        sizes = {f: tuple(len(r[x]) for x in sc.ROLES) for f, r in v["folds"].items()}
        print(f"{t}: {v['n_blocks']} blocks, {v['rows_without_block_dropped']} rows without block dropped, "
              f"(held, val, train) per fold {sizes}")
    print(f"content_sha256 {doc['content_sha256']}\nfile sha256 {ek.sha256(dst)}\nwrote {dst}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
