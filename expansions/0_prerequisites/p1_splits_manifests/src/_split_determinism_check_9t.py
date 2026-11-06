"""P1 S1. Show the historical inner split is nondeterministic and the fixed one is not, in fresh processes.

Purpose
    Launch N fresh Python processes. Each computes the inner validation and train lists for every fold of
    the pit and pad CV splits, once with the historical code (NaN kept in the sorted set) and once with the
    fixed code (NaN dropped, ids cast to int). Each process prints the SHA-256 of every list. The parent
    compares the hashes across processes. Gate. The fixed code must be identical in every fold of every task.
    The historical code is expected to differ (seen in folds 0, 2 and 4 on 2026-11-04). It is reported, not
    gated, because a lucky run can repeat.

Inputs
    data/9t/derived/05/pit_dataset_manifest.csv, pad_dataset_manifest.csv (through the trainers), or
    --manifest-pit / --manifest-pad for a test.

Outputs
    <out-dir>/split_determinism_check_9t.json   per task, mode and fold the hash in every process, and a verdict
    Default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/splits/
    Run record under expansions/0_prerequisites/p1_splits_manifests/results/<run_id>/

Run
    python expansions/0_prerequisites/p1_splits_manifests/src/_split_determinism_check_9t.py [--procs 3] [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))


def worker(manifests: dict[str, str | None], k: int) -> dict:
    """Runs inside a fresh process. Returns {task: {mode: {fold: {role: hash}}}}."""
    import _split_core_lib_9t as sc
    out = {}
    for task, mpath in manifests.items():
        p = sc.task_params(task)
        man = sc.load_manifest(task, Path(mpath) if mpath else None)
        out[task] = {}
        for mode in ("historical", "fixed"):
            s = sc.make_splits(man, k, p["seed"], p["inner_val_frac"], p["assign_folds"], mode)
            out[task][mode] = sc.fold_hashes(s)
    return out


def compare(results: list[dict]) -> dict:
    """Per task, mode and fold, whether every process agrees."""
    verdict = {}
    for task in results[0]:
        verdict[task] = {}
        for mode in results[0][task]:
            folds = {}
            for f in results[0][task][mode]:
                same = all(r[task][mode][f] == results[0][task][mode][f] for r in results)
                folds[f] = same
            verdict[task][mode] = {"identical_by_fold": folds,
                                   "differing_folds": [int(f) for f, s in folds.items() if not s]}
    fixed_ok = all(all(v["fixed"]["identical_by_fold"].values()) for v in verdict.values())
    return {"by_task": verdict, "fixed_identical_all_folds": fixed_ok,
            "gate": "pass" if fixed_ok else "fail"}


def run_check(procs: int, manifests: dict, k: int = 5) -> dict:
    results = []
    for _ in range(procs):
        cmd = [sys.executable, str(HERE), "--worker", "--k", str(k),
               "--manifests", json.dumps(manifests)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"worker failed:\n{r.stderr[-2000:]}")
        results.append(json.loads(r.stdout.strip().splitlines()[-1]))
    return {"procs": procs, "hashes": results, **compare(results)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P1 S1 split determinism check across fresh processes")
    ap.add_argument("--procs", type=int, default=3)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--tasks", default="pit,pad")
    ap.add_argument("--manifest-pit", default=None)
    ap.add_argument("--manifest-pad", default=None)
    ap.add_argument("--manifests", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--out-dir", type=Path, default=None, help="default data/9t/results/splits/")
    a = ap.parse_args(argv)
    if a.worker:
        print(json.dumps(worker(json.loads(a.manifests), a.k)))
        return 0
    import _split_core_lib_9t as sc
    ek = sc.ek
    mans = {t: {"pit": a.manifest_pit, "pad": a.manifest_pad}[t] for t in a.tasks.split(",")}
    res = run_check(a.procs, mans, a.k)
    out = a.out_dir or (ek.path_for("results_9t") / "splits")
    out.mkdir(parents=True, exist_ok=True)
    js = out / "split_determinism_check_9t.json"
    js.write_text(json.dumps(res, indent=2), encoding="utf-8")
    run = ek.new_run("p1", "split_determinism", {"procs": a.procs, "tasks": a.tasks, "k": a.k},
                     why="S1 determinism of historical vs fixed inner split.")
    ek.write_provenance(run, outputs=[js], params={"procs": a.procs})
    for t, v in res["by_task"].items():
        print(f"{t}: historical differing folds {v['historical']['differing_folds']}  "
              f"fixed differing folds {v['fixed']['differing_folds']}")
    print(f"gate {res['gate']}\nwrote {js}\nrun record {run}")
    return 0 if res["gate"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
