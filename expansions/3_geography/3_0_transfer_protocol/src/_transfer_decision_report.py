"""3.0 decision report. Target minus 9t recall at K, block-bootstrap interval, preregistered verdict.

Purpose
    Read the per-block table of a target scoring run and of the 9t reference (a scoring run folder, or the
    archival per-block counts rebuilt from the sweep). Resample each area's blocks independently
    (`ek.bootstrap_diff`, B and seed from the preregistration) and take the 95% interval of the difference
    in pooled recall. Apply `ek.decide` with the preregistered margin (non-inferiority). Success if the lower
    bound is above minus the margin, failure if the upper bound is below it, inconclusive otherwise.
    Inconclusive is never written as no effect. The report also gives both feature densities, the
    density-scaled secondary when the target run has it, the 9t fold spread at K, and a warning under 15
    target blocks. Evidence level (a) drawn features only.

Inputs
    --target     scoring run folder holding transfer_score_<area>.json and transfer_blocks_<area>.csv
    --reference  9t scoring run folder, or the word `archival` (per-block counts from the sweep at K)
    --prereg     filled preregistration (margin, seed, B, task)

Outputs (in the target run folder)
    transfer_decision_<area>.json, transfer_decision_<area>.md
    Run record under expansions/3_geography/3_0_transfer_protocol/results/<run_id>/

Run
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_decision_report.py --target data/warren/results/transfer/<run_id> --reference archival --prereg docs/iterations/transfer_warren_prereg.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _transfer_score_lib as tl  # noqa: E402
ek = tl.ek


def load_run(folder: Path) -> tuple[dict, pd.DataFrame]:
    js = sorted(Path(folder).glob("transfer_score_*.json"))
    cs = sorted(Path(folder).glob("transfer_blocks_*.csv"))
    if not js or not cs:
        raise SystemExit(f"{folder} holds no transfer_score_*.json and transfer_blocks_*.csv")
    return json.loads(js[0].read_text(encoding="utf-8")), pd.read_csv(cs[0])


def ratio_stat(tab: pd.DataFrame):
    h, n = tab.hits.to_numpy(float), tab.n_truth.to_numpy(float)

    def stat(idx):
        idx = np.asarray(idx, int)
        d = n[idx].sum()
        return h[idx].sum() / d if d else np.nan
    return stat


def decision(target: pd.DataFrame, ref: pd.DataFrame, margin: float, B: int, seed: int, kind: str = "noninferiority") -> dict:
    st, sr = ratio_stat(target), ratio_stat(ref)
    d, lo, hi = ek.bootstrap_diff(st, range(len(target)), sr, range(len(ref)), B=B, seed=seed)
    return {"diff": d, "lo": lo, "hi": hi, "margin": margin, "kind": kind, "verdict": ek.decide(lo, hi, margin, kind),
            "target_recall": st(range(len(target))), "reference_recall": sr(range(len(ref))), "B": B, "seed": seed,
            "n_target_blocks": len(target), "n_reference_blocks": len(ref)}


def density(tab: pd.DataFrame) -> float:
    return float(tab.n_truth.sum() / tab.area_km2.sum())


def write_md(doc: dict, path: Path) -> None:
    r = doc["primary"]
    words = {"success": "The lower bound clears minus the margin. Transfer at this K is supported for drawn features.",
             "failure": "The upper bound lies below minus the margin. Do not claim transfer. Start the error review.",
             "inconclusive": "The interval spans minus the margin. The test cannot decide. It does not show no effect."}
    lines = [f"# Transfer decision, {doc['area']} ({doc['task']})", "",
             f"Evidence level (a) drawn feature. Preregistration `{doc['prereg']}`.", "",
             "## Primary",
             f"- Recall at K {doc['k_per_km2']} per km2. Target {r['target_recall']:.3f}. 9t reference {r['reference_recall']:.3f}.",
             f"- Difference {r['diff']:+.3f}. 95% block-bootstrap interval {r['lo']:+.3f} to {r['hi']:+.3f}.",
             f"- Margin {r['margin']}. Verdict **{r['verdict']}**. {words[r['verdict']]}", "",
             "## Context",
             f"- Feature density. Target {doc['density_target']:.1f} per km2. 9t {doc['density_reference']:.1f} per km2.",
             f"- Target blocks {r['n_target_blocks']}. Reference blocks {r['n_reference_blocks']}."]
    if doc.get("secondary"):
        s = doc["secondary"]
        lines.append(f"- Secondary at density-scaled K {s['k_per_km2']:.1f}. Target recall {s['recall']:.3f} "
                     f"({s['lo']:.3f} to {s['hi']:.3f}). Reported, not gated.")
    for w in doc.get("warnings", []):
        lines.append(f"- Warning. {w}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="3.0 decision report")
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--reference", required=True, help="9t run folder or 'archival'")
    ap.add_argument("--prereg", type=Path, required=True)
    a = ap.parse_args(argv)
    pr = tl.read_prereg(a.prereg)
    sc = pr.get("scoring", {})
    tsum, ttab = load_run(a.target)
    k = float(tsum["k_per_km2"])
    if float(sc.get("k", k)) != k:
        raise SystemExit(f"target run K {k} differs from the preregistered K {sc.get('k')}")
    if a.reference == "archival":
        from _transfer_ci_width_9t import archival_pool
        rtab = archival_pool(pr.get("task", "pit"), k)
        if "area_km2" not in rtab:
            raise AssertionError("archival pool lacks areas")
    else:
        rsum, rtab = load_run(Path(a.reference))
        if float(rsum["k_per_km2"]) != k:
            raise SystemExit("reference and target K differ")
    margin = float(pr["margin"])
    seed, B = int(sc.get("seed", 20261105)), int(sc.get("B", 2000))
    prim = decision(ttab, rtab, margin, B, ek.child_seed(seed, 0, 2))
    warns = []
    if len(ttab) < 15:
        warns.append("fewer than 15 target blocks. The bootstrap is unreliable. See the sign-flip interval in the score JSON.")
    if prim["hi"] - prim["lo"] > 2 * margin:
        warns.append(f"interval width {prim['hi'] - prim['lo']:.3f} exceeds twice the margin. The design was underpowered.")
    doc = {"area": tsum["settings"].get("area"), "task": tsum["settings"].get("task", pr.get("task")), "k_per_km2": k,
           "prereg": str(a.prereg), "prereg_sha256": ek.sha256(a.prereg), "primary": prim,
           "density_target": density(ttab), "density_reference": density(rtab),
           "secondary": tsum.get("secondary_density_scaled"), "warnings": warns, "evidence_level": "(a) drawn feature",
           "reference": a.reference}
    area = doc["area"]
    js, md = a.target / f"transfer_decision_{area}.json", a.target / f"transfer_decision_{area}.md"
    js.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    write_md(doc, md)
    run = ek.new_run("3.0", f"decision_{area}", {"target": str(a.target), "reference": a.reference}, why="3.0 decision.")
    ek.write_provenance(run, inputs=[a.prereg] + sorted(a.target.glob("transfer_*_*.csv")), outputs=[js, md])
    print(f"{area}: diff {prim['diff']:+.3f} [{prim['lo']:+.3f}, {prim['hi']:+.3f}] margin {margin} -> {prim['verdict']}")
    print(f"wrote {js}\nwrote {md}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
