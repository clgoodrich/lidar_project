"""Run the missing roaddrain arm of the 1 m architecture comparison.

WHY THIS ARM IS MISSING
-----------------------
`arch_compare_summary_9t_1m.csv` has 5 folds for every architecture on `pit`
and `pad` -- 40 completed runs. `roaddrain` has none. The unfinished record
says why:

    "roaddrain/unet": ["fold0 (1/40 epochs)"]

It started once and stopped after a single epoch, so the leaderboard carries no
roaddrain row at all.

WHAT IT COSTS
-------------
Measured, not guessed. `--time-one-epoch` on roaddrain/unet reports **339.2 s
per epoch**, against roughly 15 s for pit. The reason is sample count:

    pit        503 usable features
    pad        650
    roaddrain  7,825          -- 15.6x pit

At 40 epochs and 5 folds that is 18.8 h for unet alone. Scaling the other three
by their measured pit/pad ratios against unet:

    unet                  18.8 h
    r34_scratch          ~16.7 h
    r34_imagenet         ~16.4 h
    unetpp_r34_imagenet  ~26.0 h
    ------------------------------
    total                ~78 h     (~3.3 days of continuous GPU)

So this is a long job on one GTX 1070 Ti, and it is ordered deliberately: the
plain U-Net runs FIRST, because that single arm is what gives roaddrain a
leaderboard row and answers whether roads behave like pits (architecture makes
no difference) or like pads (it might). The three transfer-learning arms only
refine that answer.

Stopping after any arm leaves a usable, self-consistent result. Each arm writes
its own per-fold records, so nothing is lost by cutting it short.

ROBUSTNESS
----------
`pad/unetpp_r34_imagenet` fold2 died of an out-of-memory error in the original
sweep, and roaddrain's 3-class head on an 8.6 GB card is the same risk profile.
An arm that fails here is logged and the runner moves to the next one rather
than taking the whole sequence down with it.

Run:
    python notebooks/wellsight_v2/s3_train/_run_roaddrain_arch_compare.py
    python ..._run_roaddrain_arch_compare.py --archs unet      # just the first
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TRAINER = ROOT / "notebooks/wellsight_v2/s3_train/_arch_compare_9t_1m.py"
LOGDIR = ROOT / "data/9t/results/arch_compare_1m"
PROGRESS = LOGDIR / "roaddrain_run_progress.json"

#: plain U-Net first: it is the arm that fills the missing leaderboard row.
ORDER = ("unet", "r34_scratch", "r34_imagenet", "unetpp_r34_imagenet")
#: measured on pit and pad, used only to print an expected finish time
REL_COST = {"unet": 1.00, "r34_scratch": 0.89,
            "r34_imagenet": 0.87, "unetpp_r34_imagenet": 1.38}
UNET_HOURS = 18.8


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archs", nargs="*", default=list(ORDER))
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=40)
    args = ap.parse_args()

    archs = [a for a in ORDER if a in args.archs]
    total_h = sum(UNET_HOURS * REL_COST[a] for a in archs)
    scale = (args.folds / 5) * (args.epochs / 40)
    total_h *= scale

    LOGDIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    print(f"  roaddrain, {len(archs)} architecture(s), "
          f"{args.folds} folds x {args.epochs} epochs")
    print(f"  projected {total_h:.1f} h, finishing about "
          f"{(started + timedelta(hours=total_h)):%a %d %b %H:%M}")
    print(f"  order: {' -> '.join(archs)}\n")

    results = []
    for i, arch in enumerate(archs, 1):
        t0 = time.time()
        print(f"  [{i}/{len(archs)}] {arch} starting "
              f"{datetime.now():%H:%M:%S} ...", flush=True)
        log = LOGDIR / f"roaddrain_{arch}_train.log"
        with open(log, "w", encoding="utf-8") as fh:
            # -u so the log is readable while it runs rather than at the end
            proc = subprocess.run(
                [sys.executable, "-u", str(TRAINER),
                 "--target", "roaddrain", "--arch", arch,
                 "--folds", str(args.folds), "--epochs", str(args.epochs)],
                stdout=fh, stderr=subprocess.STDOUT, cwd=str(ROOT))
        mins = (time.time() - t0) / 60
        ok = proc.returncode == 0
        results.append(dict(arch=arch, ok=ok, returncode=proc.returncode,
                            minutes=round(mins, 1), log=str(log)))
        print(f"       {'done' if ok else 'FAILED rc=' + str(proc.returncode)}"
              f" in {mins/60:.1f} h", flush=True)
        PROGRESS.write_text(json.dumps(
            dict(started=started.isoformat(), target="roaddrain",
                 folds=args.folds, epochs=args.epochs, results=results),
            indent=2), encoding="utf-8")

    done = [r for r in results if r["ok"]]
    print(f"\n  {len(done)}/{len(results)} architectures completed in "
          f"{(time.time() - started.timestamp())/3600:.1f} h")
    for r in results:
        print(f"    {r['arch']:22s} {'ok' if r['ok'] else 'FAILED':7s} "
              f"{r['minutes']/60:5.1f} h")
    print(f"\n  {PROGRESS}")
    print("  aggregate with: python notebooks/wellsight_v2/s5_eval/"
          "_aggregate_arch_compare_1m.py")
    return 0 if len(done) == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
