"""5.1 S3. Retraining job manifest for pit, pad and road models on the shared fold scheme (tile 9t).

Purpose
    Turn the shared fold file (S1) into one explicit job per upstream model and outer fold. Each job lists
    held-out blocks (outer fold k), inner-validation blocks (fold (k + 1) mod K, a fixed rule, saved in the file)
    and training blocks (the rest). Audit blocks appear in no list. The manifest asserts the three lists are
    disjoint and cover every non-audit block. It prints the trainer command for each job. It does not train.
    GPU training is out of scope for the build. `--execute` runs the commands one by one through subprocess and is
    meant for the executor after epoch time has been measured (BACKLOG notes it was under-reported 1.8 times).

Inputs (config_5_1.json)
    inputs.shared_folds  -> expansions/5_tasks/5_1_context_features/results/tables/shared_folds_9t_v1.json (S1)
                            (--provisional reads shared_folds_9t_provisional.json and marks every job provisional)
    trainers.pit|pad|road  trainer scripts. The pit isolated trainer is P1 S3,
                           expansions/0_prerequisites/p1_splits_manifests/src/_pit_unet_iso_train_9t.py. The road copy is not built.
Outputs
    outputs.retrain_manifest -> expansions/5_tasks/5_1_context_features/results/tables/context_retrain_manifest_9t.json
    Trainers write to @exp:5.1/models/<role>/unet_shared_cv5/fold<k>/ (expansion models/, not in git)
    and must save training_blocks.json there, which the S6 leakage audit reads.
Run
    python expansions/5_tasks/5_1_context_features/src/_context_retrain_manifest_9t.py [--provisional] [--execute]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

ek = th.ek
ROLES = ("pit", "pad", "road")


def jobs_from_folds(block_to_fold: dict[int, int], k: int, audit: list[int]) -> list[dict]:
    blocks = sorted(block_to_fold)
    jobs = []
    for role in ROLES:
        for f in range(k):
            held = [b for b in blocks if block_to_fold[b] == f]
            val = [b for b in blocks if block_to_fold[b] == (f + 1) % k]
            train = [b for b in blocks if block_to_fold[b] not in (f, (f + 1) % k)]
            ek.assert_disjoint(held, train, f"{role} fold {f} held/train")
            ek.assert_disjoint(held, val, f"{role} fold {f} held/val")
            ek.assert_disjoint(val, train, f"{role} fold {f} val/train")
            ek.assert_disjoint(audit, held + val + train, f"{role} fold {f} audit")
            if sorted(held + val + train) != blocks:
                raise AssertionError(f"{role} fold {f}: lists do not cover every non-audit block")
            jobs.append(dict(role=role, fold=f, held_out=held, val=val, train=train,
                             out_dir=f"@exp:5.1/models/{role}/unet_shared_cv5/fold{f}"))
    return jobs


# P1-06. The pit isolated trainer is expansions/0_prerequisites/p1_splits_manifests/src/_pit_unet_iso_train_9t.py.
# It takes a P1 split JSON (--splits, --only-folds, --out-dir), not this manifest. Its jobs are printed with
# its real flags, and --execute refuses them until the shared folds are exported in the P1 split schema.
CLI_MISMATCH = {"pit": "the P1 isolated pit trainer reads a P1 split JSON (content-hashed), not the 5.1 manifest. "
                       "Export the shared folds in the P1 split schema first."}


def repo_rel(p) -> str:
    """Repo-relative POSIX path for outputs. Never an absolute path."""
    p = Path(p)
    try:
        return p.resolve().relative_to(ek.REPO.resolve()).as_posix()
    except ValueError:
        return p.name


def command(cfg: dict, job: dict, manifest: Path) -> list[str]:
    tr = repo_rel(th.resolve(cfg["trainers"][job["role"]]))
    out = repo_rel(th.resolve(job["out_dir"]))
    if job["role"] == "pit":
        return ["python", tr, "--splits", repo_rel(manifest), "--only-folds", str(job["fold"]), "--out-dir", out]
    return ["python", tr, "--split-file", repo_rel(manifest), "--role", job["role"], "--fold", str(job["fold"]),
            "--out", out]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--provisional", action="store_true", help="read the provisional fold file (pipeline test only)")
    ap.add_argument("--execute", action="store_true", help="run the trainers (GPU). Not for the build")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    src = th.outp(cfg, "shared_folds_provisional") if a.provisional else th.inp(cfg, "shared_folds")
    if not src.exists():
        raise th.MissingInput("shared_folds_provisional", src, "run _context_shared_folds_9t.py --allow-no-audit")
    sf = json.loads(src.read_text())
    m = {int(b): int(f) for b, f in sf["block_to_fold"].items()}
    jobs = jobs_from_folds(m, int(sf["k"]), [int(x) for x in sf.get("audit_blocks", [])])
    out = th.outp(cfg, "retrain_manifest")
    doc = dict(source=repo_rel(src), source_sha256=ek.sha256(src), provisional=bool(sf.get("provisional")),
               inner_val_rule="fold (k + 1) mod K", trainers=cfg["trainers"], jobs=jobs,
               requirement="trainer rejects any window touching held_out or val blocks, fits normalisation on "
                           "train blocks only, writes training_blocks.json beside best.pt")
    th.write_json(out, doc)
    missing = sorted({r for r in ROLES if not th.resolve(cfg["trainers"][r]).exists()})
    for j in jobs:
        print(" ".join(command(cfg, j, out)))
    print(f"wrote {out}  ({len(jobs)} jobs{', PROVISIONAL' if doc['provisional'] else ''})")
    if missing:
        print(f"trainers not on disk for roles {missing}. Build them before --execute.")
    if a.execute:
        if doc["provisional"]:
            raise SystemExit("refusing to train on a provisional fold file")
        if missing:
            raise th.MissingInput(f"trainer_{missing[0]}", th.resolve(cfg["trainers"][missing[0]]), cfg["trainers"]["note"])
        bad = sorted({j["role"] for j in jobs} & set(CLI_MISMATCH))
        if bad:
            raise SystemExit(f"refusing --execute for roles {bad}: " + " ".join(CLI_MISMATCH[r] for r in bad))
        for j in jobs:
            subprocess.run([sys.executable] + command(cfg, j, out)[1:], check=True, cwd=str(ek.REPO))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except th.MissingInput as e:
        print(e.args[0], file=sys.stderr)
        sys.exit(2)
