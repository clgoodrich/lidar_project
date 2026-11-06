"""4.2 primary gate. Holm over the two declared primaries T3 (contrast) and T4 (added value) (9t).

Purpose
    The user accepted the default on 2026-11-06 ("take defaults"). Holm correction runs over the declared
    PRIMARY gates only (framework section 7, T3 and T4). Secondaries and sensitivities are reported, never
    gated. Each stage writes its one-sided bootstrap shares at its margin (p_success, p_failure) and an
    unadjusted verdict. This script adjusts both families by Holm and gates on the adjusted values at
    alpha / 2. A primary that has not run, or a T4 that is not identifiable, keeps p 1. It counts in the
    family and cannot pass.
Inputs
    T3  latest <run>_thermal_contrast_*/thermal_contrast_summary_9t.json (or --t3)
    T4  latest <run>_thermal_added_*/thermal_added_value_9t.json (or --t4)
Outputs (expansions/4_modalities/4_2_thermal/results/<YYYYMMDD>_thermal_holm_<hash7>/)
    thermal_primary_holm_9t.json, provenance
Run
    python expansions/4_modalities/4_2_thermal/src/_thermal_primary_holm_9t.py [--t3 P] [--t4 P]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import _thermal_shared_io as io
from _thermal_shared_io import ek

SHORT = "thermal_holm"
PRIMARIES = {"T3": ("thermal_contrast", "thermal_contrast_summary_9t.json"),
             "T4": ("thermal_added", "thermal_added_value_9t.json")}


def _find(short: str, name: str, given):
    if given:
        return Path(given)
    try:
        return io.latest_run(io.EXP, short) / name
    except (FileNotFoundError, RuntimeError):
        return None


def stage_result(name: str, path: Path | None):
    """The p shares a primary contributes, or None with the reason."""
    if path is None or not Path(path).exists():
        return None, "not run"
    r = json.loads(Path(path).read_text(encoding="utf-8"))
    if name == "T4":
        if not r.get("identifiable", False):
            return None, "not identifiable"
        r = r["recall_at_k"]
    if "p_success" not in r:
        raise RuntimeError(f"{path} has no p_success. It was written before the Holm gate. Rerun {name}")
    return {"p_success": r["p_success"], "p_failure": r["p_failure"]}, "ok"


def run(cfg: dict, out_root: Path | None = None, t3=None, t4=None, alpha: float | None = None) -> dict:
    alpha = float(alpha if alpha is not None else cfg.get("primary_gate", {}).get("alpha", 0.05))
    paths = {"T3": _find(*PRIMARIES["T3"], t3), "T4": _find(*PRIMARIES["T4"], t4)}
    res, status = {}, {}
    for k, p in paths.items():
        res[k], status[k] = stage_result(k, p)
    g = io.holm_gate(res, alpha)
    for k in g["gates"]:
        g["gates"][k]["status"] = status[k]
        g["gates"][k]["source"] = str(paths[k]) if paths[k] else None
    g.update(stage="primary gate", primaries=list(PRIMARIES),
             note="Secondaries and sensitivities are reported in their stage outputs and never gated")
    run_dir = ek.new_run(io.EXP, SHORT, {"alpha": alpha, "primaries": list(PRIMARIES)}, base=out_root,
                         why="Holm over the 4.2 primaries T3 and T4.")
    out_j = run_dir / "thermal_primary_holm_9t.json"
    out_j.write_text(json.dumps(g, indent=2, default=str), encoding="utf-8")
    return io.finish(run_dir, g, inputs=[p for p in paths.values() if p and Path(p).exists()], outputs=[out_j],
                     params={"alpha": alpha}, seeds={"master": cfg["master_seed"]})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--t3", type=Path, default=None)
    ap.add_argument("--t4", type=Path, default=None)
    a = ap.parse_args()
    print(json.dumps(run(io.load_config(a.config), a.out_root, a.t3, a.t4), indent=1, default=str))


if __name__ == "__main__":
    main()
