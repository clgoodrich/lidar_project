"""4.3 primary gate. Holm over the two declared primaries V3 (question A) and V4 all labels (question B) (9t).

Purpose
    The user accepted the default on 2026-11-06 ("take defaults"). Holm correction runs over the declared
    PRIMARY gates only (framework section 7, primary A and primary B). V4 strong and weak subsets and every
    index, season and ring choice are secondary. They are reported and never gated. Each stage writes its
    one-sided bootstrap shares at its margin (p_success, p_failure) and an unadjusted verdict. This script
    adjusts both families by Holm (4.2 holm_gate) and gates on the adjusted values at alpha / 2. A primary
    that has not run, was skipped, or is not identifiable keeps p 1. It counts in the family and cannot pass.
    V4 runs only after a V0 success, so before that question B holds p 1 by design.
Inputs
    V3  latest <run>_vegstress_added_*/vegstress_added_value_9t.json (or --v3)
    V4  latest <run>_vegstress_leak_*/vegstress_leak_test_9t.json (or --v4)
Outputs (expansions/4_modalities/4_3_vegetation_stress/results/<YYYYMMDD>_vegstress_holm_<hash7>/)
    vegstress_primary_holm_9t.json, provenance
Run
    python expansions/4_modalities/4_3_vegetation_stress/src/_vegstress_primary_holm_9t.py [--v3 P] [--v4 P]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import _vegstress_shared_io as io
from _vegstress_shared_io import ek

SHORT = "vegstress_holm"
PRIMARIES = {"V3": ("vegstress_added", "vegstress_added_value_9t.json"),
             "V4:all": ("vegstress_leak", "vegstress_leak_test_9t.json")}


def _find(short: str, name: str, given):
    if given:
        return Path(given)
    try:
        return io.latest_run(short) / name
    except (FileNotFoundError, RuntimeError):
        return None


def stage_result(name: str, path: Path | None):
    """The p shares a primary contributes, or None with the reason."""
    if path is None or not Path(path).exists():
        return None, "not run"
    r = json.loads(Path(path).read_text(encoding="utf-8"))
    if name == "V3":
        if not r.get("identifiable", False):
            return None, "not identifiable"
        r = r["recall_at_k"]
    else:
        r = r["results"].get("all", {})
        if r.get("status") != "ok":
            return None, f"skipped ({r.get('reason', 'no all-labels row')})"
    if "p_success" not in r:
        raise RuntimeError(f"{path} has no p_success. It was written before the Holm gate. Rerun {name}")
    return {"p_success": r["p_success"], "p_failure": r["p_failure"]}, "ok"


def run(cfg: dict, out_root: Path | None = None, v3=None, v4=None, alpha: float | None = None) -> dict:
    alpha = float(alpha if alpha is not None else cfg.get("primary_gate", {}).get("alpha", 0.05))
    paths = {"V3": _find(*PRIMARIES["V3"], v3), "V4:all": _find(*PRIMARIES["V4:all"], v4)}
    res, status = {}, {}
    for k, p in paths.items():
        res[k], status[k] = stage_result(k, p)
    g = io._t.holm_gate(res, alpha)
    for k in g["gates"]:
        g["gates"][k]["status"] = status[k]
        g["gates"][k]["source"] = str(paths[k]) if paths[k] else None
    g.update(stage="primary gate", primaries=list(PRIMARIES),
             note="Secondaries (V4 strong, V4 weak, index, season, ring) are reported in their stage outputs and never gated")
    run_dir = ek.new_run(io.EXP, SHORT, {"alpha": alpha, "primaries": list(PRIMARIES)}, base=out_root,
                         why="Holm over the 4.3 primaries V3 and V4 all labels.")
    out_j = run_dir / "vegstress_primary_holm_9t.json"
    out_j.write_text(json.dumps(g, indent=2, default=str), encoding="utf-8")
    return io._t.finish(run_dir, g, inputs=[p for p in paths.values() if p and Path(p).exists()], outputs=[out_j],
                        params={"alpha": alpha}, seeds={"master": cfg["master_seed"]})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--v3", type=Path, default=None)
    ap.add_argument("--v4", type=Path, default=None)
    a = ap.parse_args()
    print(json.dumps(run(io.load_config(a.config), a.out_root, a.v3, a.v4), indent=1, default=str))


if __name__ == "__main__":
    main()
