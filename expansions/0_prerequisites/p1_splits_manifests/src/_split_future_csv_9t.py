"""P1 S2 companion. Flatten the frozen split JSON into one long CSV per task, the form other expansions read.

Inputs   data/9t/results/splits/cv_splits_future_9t_v<version>.json   (written by _split_future_write_9t.py)
Outputs  data/9t/results/splits/cv_splits_future_<task>_9t_v<version>.csv
         columns block_id, fold, role. Role is train, inner_val or held_out, the same words as the JSON
         (review P1-01). One row per block per fold. Blocks in the JSON role `buffer` (removed by the
         derived buffer) get no row, so a reader never trains or scores them.
Run      python expansions/0_prerequisites/p1_splits_manifests/src/_split_future_csv_9t.py [--json <file>] [--out-dir <dir>] [--force]

A CSV that exists is never overwritten with different content unless --force is given. Rewriting
identical content is allowed. Read it with ek.read_split_csv. This is the canonical split interface
listed in expansions/_shared/INTERFACES.md.
"""
import argparse
import csv
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

ROLES = ("train", "inner_val", "held_out")        # JSON role names, written unchanged


def flatten(split: dict) -> dict[str, list[tuple[int, int, str]]]:
    out = {}
    for task, t in split["tasks"].items():
        rows = []
        for fold, roles in sorted(t["folds"].items(), key=lambda kv: int(kv[0])):
            for role in ROLES:
                rows += [(int(b), int(fold), role) for b in roles.get(role, [])]
        ek.assert_no_nan([r[0] for r in rows], f"{task} block ids")
        per_fold = {}
        for b, f, _ in rows:
            per_fold.setdefault(f, []).append(b)
        for f, bl in per_fold.items():
            if len(bl) != len(set(bl)):
                raise AssertionError(f"{task} fold {f}: a block holds two roles")
        out[task] = rows
    return out


def csv_bytes(rows) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["block_id", "fold", "role"])
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def write_csvs(src: Path, out: Path, version: int, force: bool = False) -> list[Path]:
    """Write one CSV per task. Refuses to replace a file whose content differs, unless force."""
    import hashlib
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for task, rows in flatten(json.loads(Path(src).read_text(encoding="utf-8"))).items():
        dst = out / f"cv_splits_future_{task}_9t_v{version}.csv"
        new = csv_bytes(rows)
        if dst.exists() and not force:
            old = dst.read_bytes()
            if hashlib.sha256(old).hexdigest() != hashlib.sha256(new).hexdigest():
                raise FileExistsError(f"{dst} exists with different content (frozen split CSV). "
                                      "Write a new version, or pass --force if this is a dry run.")
        dst.write_bytes(new)
        written.append(dst)
        print(f"{task}: {len(rows)} rows -> {dst}")
    return written


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--force", action="store_true", help="replace a CSV whose content differs (dry runs only)")
    a = ap.parse_args(argv)
    splits = ek.path_for("results_9t") / "splits"
    src = a.json or splits / f"cv_splits_future_9t_v{a.version}.json"
    if not src.exists():
        sys.exit(f"MISSING INPUT split JSON: {src}. Run _split_future_write_9t.py first.")
    try:
        write_csvs(src, a.out_dir or src.parent, a.version, a.force)
    except FileExistsError as e:
        sys.exit(str(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
