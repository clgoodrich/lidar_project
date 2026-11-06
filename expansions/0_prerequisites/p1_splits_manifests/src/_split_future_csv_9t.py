"""P1 S2 companion. Flatten the frozen split JSON into one long CSV per task, the form other expansions read.

Inputs   data/9t/results/splits/cv_splits_future_9t_v<version>.json   (written by _split_future_write_9t.py)
Outputs  data/9t/results/splits/cv_splits_future_<task>_9t_v<version>.csv
         columns block_id, fold, role   (role is train, val or heldout; one row per block per fold)
Run      python expansions/0_prerequisites/p1_splits_manifests/src/_split_future_csv_9t.py [--json <file>] [--out-dir <dir>]

This is the canonical split interface listed in expansions/_shared/INTERFACES.md.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

ROLE = {"train": "train", "inner_val": "val", "held_out": "heldout"}


def flatten(split: dict) -> dict[str, list[tuple[int, int, str]]]:
    out = {}
    for task, t in split["tasks"].items():
        rows = []
        for fold, roles in sorted(t["folds"].items(), key=lambda kv: int(kv[0])):
            for key, role in ROLE.items():
                rows += [(int(b), int(fold), role) for b in roles.get(key, [])]
        ek.assert_no_nan([r[0] for r in rows], f"{task} block ids")
        per_fold = {}
        for b, f, _ in rows:
            per_fold.setdefault(f, []).append(b)
        for f, bl in per_fold.items():
            if len(bl) != len(set(bl)):
                raise AssertionError(f"{task} fold {f}: a block holds two roles")
        out[task] = rows
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    a = ap.parse_args()
    splits = ek.path_for("results_9t") / "splits"
    src = a.json or splits / f"cv_splits_future_9t_v{a.version}.json"
    if not src.exists():
        sys.exit(f"MISSING INPUT split JSON: {src}. Run _split_future_write_9t.py first.")
    out = a.out_dir or src.parent
    out.mkdir(parents=True, exist_ok=True)
    for task, rows in flatten(json.loads(src.read_text(encoding="utf-8"))).items():
        dst = out / f"cv_splits_future_{task}_9t_v{a.version}.csv"
        with open(dst, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["block_id", "fold", "role"])
            w.writerows(rows)
        print(f"{task}: {len(rows)} rows -> {dst}")


if __name__ == "__main__":
    main()
